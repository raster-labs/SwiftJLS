#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# SPDX/CycloneDX correction and offline validation rules adapted from SwiftJLI's
# Apache-2.0 derive-prepared.py; exact upstream digest is in adaptation.json.
"""Preserve raw SwiftPM defects and qualify separately labelled derived SBOMs."""
import argparse
import copy
import gzip
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re
import socket
import uuid
from urllib.parse import urlparse
from jsonschema.validators import validator_for
from referencing import Registry, Resource
from rdflib import Graph
from pyshacl import validate as shacl_validate
from packageurl import PackageURL

URL = 'https://github.com/raster-labs/SwiftJLS'
SPECS = {'spdx': 'spdx-json-schema.json', 'cyclonedx': 'bom-1.7.schema.json'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def emit(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x') as stream:
        stream.write(json.dumps(value, indent=2, sort_keys=True) + '\n')


def require(value, message):
    if not value:
        raise ValueError(message)


def block_network(*args, **kwargs):
    raise RuntimeError('Validation permits recorded local inputs only')


class Validation:
    def __init__(self, inputs):
        self.inputs = inputs
        self.receipt = read(inputs / 'receipt.json')
        for entry in self.receipt['files']:
            require(sha(inputs / entry['path']) == entry['sha256'], 'Validation input digest mismatch: ' + entry['path'])
        socket.socket.connect = block_network
        socket.create_connection = block_network
        self.registry = Registry(retrieve=self.retrieve)

    def bytes(self, name):
        require(name in {*SPECS.values(), 'spdx.schema.json', 'jsf-0.82.schema.json', 'spdx-context.jsonld', 'spdx-model.ttl'}, 'Unrecorded input')
        return gzip.decompress((self.inputs / (name + '.gz')).read_bytes())

    def retrieve(self, uri):
        return Resource.from_contents(json.loads(self.bytes(urlparse(uri).path.rsplit('/', 1)[-1])))

    def schema(self, spec, document):
        data = self.bytes(SPECS[spec])
        schema = json.loads(data)
        cls = validator_for(schema)
        cls.check_schema(schema)
        errors = list(cls(schema, registry=self.registry, format_checker=cls.FORMAT_CHECKER).iter_errors(document))
        return {'passed': not errors, 'schemaSHA256': hashlib.sha256(data).hexdigest(),
                'errors': [{'path': list(x.path), 'message': x.message} for x in errors]}

    def shacl(self, document):
        require(document.get('@context') == 'https://spdx.org/rdf/3.0.1/spdx-context.jsonld', 'Unexpected SPDX JSON-LD context')
        data = copy.deepcopy(document)
        data['@context'] = json.loads(self.bytes('spdx-context.jsonld'))['@context']
        graph = Graph().parse(data=json.dumps(data), format='json-ld')
        model = Graph().parse(data=self.bytes('spdx-model.ttl'), format='turtle')
        conforms, result, text = shacl_validate(graph, shacl_graph=model, ont_graph=model,
            inference='none', allow_infos=False, allow_warnings=False, advanced=True)
        return bool(conforms), text, result.serialize(format='turtle')


def semantic_findings(spdx, cdx, revision, product):
    findings = []
    def check(ok, message):
        if not ok:
            findings.append(message)
    graph = spdx['@graph']
    ids = [x.get('spdxId', x.get('@id')) for x in graph]
    check(None not in ids and len(ids) == len(set(ids)), 'SPDX identifiers are absent or duplicated')
    for item in graph:
        if item['type'] == 'CreationInfo':
            check(item['specVersion'] == '3.0.1', 'SPDX specification version mismatch')
        for key in ['from', 'to', 'rootElement', 'creationInfo', 'createdBy', 'createdUsing']:
            if key in item:
                refs = item[key] if isinstance(item[key], list) else [item[key]]
                check(all(x in ids for x in refs), 'Unresolved SPDX ' + key)
    packages = [x for x in graph if x['type'] == 'software_Package' and x.get('summary') in ['swift-package', 'swift-product']]
    check(len(packages) == 2, 'Expected exactly package and product')
    purl = 'pkg:swift/github.com/raster-labs/SwiftJLS@' + revision
    for item in packages:
        check(item.get('software_packageVersion', item.get('software_internalVersion')) == revision, 'SPDX source revision differs')
        if item.get('summary') == 'swift-package':
            check(item.get('software_packageUrl') == purl, 'SPDX canonical package URL differs')
        else:
            check(item.get('name') == product and 'software_packageUrl' not in item, 'SPDX product identity differs')
        check(any(x.get('relationshipType') == 'hasDeclaredLicense' and x.get('from') == item['spdxId']
                  and x.get('to') == ['urn:spdx:Apache-2.0'] for x in graph), 'SPDX source licence missing')
    refs = []
    def visit(value):
        if isinstance(value, dict):
            if 'bom-ref' in value:
                refs.append(value['bom-ref'])
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for child in value:
                visit(child)
    visit(cdx)
    check(len(refs) == len(set(refs)), 'CycloneDX references duplicated')
    check(all(x['ref'] in refs and all(y in refs for y in x.get('dependsOn', [])) for x in cdx['dependencies']), 'Unresolved CycloneDX dependency')
    subject = cdx['metadata']['component']
    check(subject['name'] == product, 'CycloneDX selected product differs')
    for item in [subject, *cdx['components']]:
        check(item.get('version') == revision, 'CycloneDX source revision differs')
        check(item.get('licenses') == [{'license': {'id': 'Apache-2.0'}}], 'CycloneDX source licence missing')
        kind = next((x['value'] for x in item.get('properties', []) if x['name'] == 'swift-entity'), None)
        check(item.get('purl') == purl if kind == 'swift-package' else 'purl' not in item, 'CycloneDX package/product URL differs')
    parsed = PackageURL.from_string(purl)
    check((parsed.type, parsed.namespace, parsed.name, parsed.version) == ('swift', 'github.com/raster-labs', 'SwiftJLS', revision), 'Invalid Swift package URL')
    return findings


def derive(originals, revision, product, timestamp, helper_hash):
    spdx, cdx = copy.deepcopy(originals['spdx']), copy.deepcopy(originals['cyclonedx'])
    graph = spdx['@graph']
    packages = [x for x in graph if x['type'] == 'software_Package']
    require(len(packages) == 2, 'Unexpected raw package graph')
    require({x.get('summary') for x in packages} == {'swift-package', 'swift-product'}, 'Unexpected raw package identities')
    purl = 'pkg:swift/github.com/raster-labs/SwiftJLS@' + revision
    for item in packages:
        require(item['software_internalVersion'] == revision, 'Raw package revision differs')
        item['software_packageVersion'] = item.pop('software_internalVersion')
        item['comment'] = 'Derived correction; original SwiftPM URL: ' + item.pop('externalUrl')
        item['software_homePage'] = URL
        if item['summary'] == 'swift-package':
            item['software_packageUrl'] = purl
        else:
            require(item['name'] == product, 'Wrong raw selected product')
            item['software_sourceInfo'] = product + ' product from ' + URL + '/tree/' + revision
    for item in graph:
        if item['type'] == 'CreationInfo' and item['specVersion'] != '3.0.1':
            require(item['specVersion'] == '6.4.2', 'Unrecognised producer version defect')
            item['comment'] = 'Derived correction: producer wrote SwiftPM 6.4.2 in SPDX specVersion.'
            item['specVersion'] = '3.0.1'
    ci = '_:derivedCreationInfo'
    agent = 'urn:swiftjls:milestone5:sbom-qualification-agent'
    tool = 'urn:swiftjls:milestone5:derive:' + helper_hash
    software_tool = 'urn:swiftjls:build-tool:swift-package-manager:6.4.2'
    def element(kind, id_, **values):
        return {'type': kind, 'spdxId': id_, 'creationInfo': ci, **values}
    graph.extend([
        {'type': 'CreationInfo', '@id': ci, 'created': timestamp, 'createdBy': [agent], 'createdUsing': [tool], 'specVersion': '3.0.1'},
        element('Agent', agent, name='SwiftJLS Milestone 5 SBOM qualification'),
        element('Tool', tool, name='qualify.py', comment='SHA-256 ' + helper_hash),
        element('software_Package', software_tool, name='swift-package-manager', software_packageVersion='6.4.2',
                software_primaryPurpose='application', comment='Build tool; not a runtime dependency.')])
    relation = graph[0]
    require(relation['relationshipType'] == 'hasDeclaredLicense', 'Unexpected producer licence relationship')
    require(any(x.get('spdxId') == relation['from'] and x['type'] == 'Agent' and x.get('name') == 'swift-package-manager' for x in graph), 'Unexpected producer licence subject')
    relation.update({'from': software_tool, 'creationInfo': ci,
                     'comment': 'Corrected licence subject from creator Agent to represented software tool; original assertion retained.'})
    for item in packages:
        item['creationInfo'] = ci
        graph.append(element('Relationship', item['spdxId'] + '-declared-apache2-derived',
            **{'from': item['spdxId'], 'to': ['urn:spdx:Apache-2.0'], 'relationshipType': 'hasDeclaredLicense',
               'comment': 'Source LICENSE and NOTICE are hash-bound in generation.json; development fixtures are outside this product inventory.'}))
    for item in graph:
        if 'profileConformance' in item:
            item['profileConformance'] = ['core', 'software', 'simpleLicensing']
        if item['type'] == 'SpdxDocument':
            item['spdxId'] = 'urn:uuid:' + str(uuid.uuid5(uuid.NAMESPACE_URL, item['spdxId'] + helper_hash))
            item['creationInfo'] = ci
            item['comment'] = 'Separately derived SwiftJLS build-associated SBOM; raw documents and transformation receipt retained.'
    subject = cdx['metadata']['component']
    require([x for x in cdx['components'] if x['bom-ref'] == subject['bom-ref']] == [subject], 'Unexpected duplicated product')
    cdx['components'] = [x for x in cdx['components'] if x['bom-ref'] != subject['bom-ref']]
    cdx['version'] += 1
    cdx['serialNumber'] = 'urn:uuid:' + str(uuid.uuid5(uuid.NAMESPACE_URL, cdx['serialNumber'] + helper_hash))
    cdx['metadata']['timestamp'] = timestamp
    cdx['metadata']['tools']['components'].append({'type': 'application', 'name': 'SwiftJLS derived SBOM helper',
        'version': helper_hash, 'bom-ref': tool, 'scope': 'excluded', 'licenses': [{'license': {'id': 'Apache-2.0'}}]})
    cdx['metadata']['properties'] = [{'name': 'swiftjls:derivation', 'value': 'Separately derived; exact transformations and raw hashes are in receipt.json.'},
        {'name': 'swiftjls:scope', 'value': 'SwiftPM package and selected product. SDK/runtime inventory and development fixtures excluded; see supplement.json.'}]
    for item in [subject, *cdx['components']]:
        require(item['version'] == revision, 'Raw CycloneDX revision differs')
        old = item.pop('purl')
        item.setdefault('properties', []).append({'name': 'swiftjls:original-generator-purl', 'value': old})
        item['licenses'] = [{'license': {'id': 'Apache-2.0'}}]
        item['externalReferences'] = [{'type': 'vcs', 'url': URL + '/tree/' + revision}]
        if any(x == {'name': 'swift-entity', 'value': 'swift-package'} for x in item['properties']):
            item['purl'] = purl
    return {'spdx': spdx, 'cyclonedx': cdx}


def diff(before, after, path=''):
    if isinstance(before, dict) and isinstance(after, dict):
        changes = []
        for key in sorted(before.keys() | after.keys()):
            pointer = path + '/' + key.replace('~', '~0').replace('/', '~1')
            if key not in after:
                changes.append({'op': 'remove', 'path': pointer, 'before': before[key]})
            elif key not in before:
                changes.append({'op': 'add', 'path': pointer, 'value': after[key]})
            else:
                changes.extend(diff(before[key], after[key], pointer))
        return changes
    return [] if before == after else [{'op': 'replace', 'path': path, 'before': before, 'value': after}]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--raw', required=True, type=Path)
    p.add_argument('--inputs', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        p.error('Existing evidence must be preserved; select a fresh output')
    generation = read(a.raw / 'generation.json')
    revision = generation['revision']
    require(re.fullmatch('[0-9a-f]{40}', revision) and generation['status'] == 'passed' and generation['sourceUnchanged'], 'Unqualified generation inputs')
    require((a.raw / 'LICENSE').read_text().lstrip().startswith('Apache License'), 'Expected repository licence')
    require('Copyright 2026 Raster Images Private Limited' in (a.raw / 'NOTICE').read_text(), 'Expected repository notice')
    for name in ['LICENSE', 'NOTICE', 'Package.swift', 'VERSION']:
        require(sha(a.raw / name) == generation['sourceSHA256'][name], 'Source receipt mismatch: ' + name)
    require(set(generation['products']) == {'library', 'cli'}, 'Both product builds are required')
    require(generation['products']['library']['product'] == 'SwiftJLS' and generation['products']['cli']['product'] == 'swiftjls-cli', 'Wrong selected product builds')
    validation = Validation(a.inputs)
    a.output.mkdir(parents=True)
    helper_hash = sha(Path(__file__))
    status = []
    for name, record in generation['products'].items():
        originals = {}
        for spec, entry in record['raw'].items():
            require(sha(a.raw / entry['path']) == entry['sha256'], 'Raw SBOM changed')
            originals[spec] = read(a.raw / entry['path'])
        out = a.output / name
        raw_schema = {spec: validation.schema(spec, doc) for spec, doc in originals.items()}
        raw_findings = semantic_findings(originals['spdx'], originals['cyclonedx'], revision, record['product'])
        emit(out / 'raw-validation.json', {'jsonSchema': raw_schema, 'semanticFindings': raw_findings,
            'scope': 'Raw schema plus explicit field/reference checks. Raw SPDX SHACL is run separately below.'})
        conforms, text, turtle = validation.shacl(originals['spdx'])
        (out / 'raw-spdx-shacl.txt').write_text(text)
        (out / 'raw-spdx-shacl.ttl').write_text(turtle)
        derived = derive(originals, revision, record['product'], generation['finishedUTC'].split('.')[0] + 'Z', helper_hash)
        original_ids = {x['spdxId'] for x in originals['spdx']['@graph'] if x['type'] == 'software_Package'}
        derived_ids = {x['spdxId'] for x in derived['spdx']['@graph'] if x.get('summary') in ['swift-package', 'swift-product']}
        require(original_ids == derived_ids, 'Original package/product identities changed')
        for spec, doc in derived.items():
            emit(out / (spec + '.derived.json'), doc)
        emit(out / 'transformations.json', {spec: diff(originals[spec], derived[spec]) for spec in derived})
        schemas = {spec: validation.schema(spec, doc) for spec, doc in derived.items()}
        findings = semantic_findings(derived['spdx'], derived['cyclonedx'], revision, record['product'])
        derived_conforms, text, turtle = validation.shacl(derived['spdx'])
        (out / 'spdx-shacl.txt').write_text(text)
        (out / 'spdx-shacl.ttl').write_text(turtle)
        passed = derived_conforms and all(x['passed'] for x in schemas.values()) and not findings
        receipt = {'status': 'passed' if passed else 'failed', 'revision': revision, 'product': record['product'],
            'helperSHA256': helper_hash, 'generationSHA256': sha(a.raw / 'generation.json'),
            'validationInputsSHA256': sha(a.inputs / 'receipt.json'), 'rawFiles': record['raw'],
            'rawSPDXSHACLConforms': conforms, 'derivedSPDXSHACLConforms': derived_conforms,
            'derivedJSONSchema': schemas, 'derivedSemanticFindings': findings,
            'derivedSHA256': {spec: sha(out / (spec + '.derived.json')) for spec in derived},
            'validatorVersions': {n: importlib.metadata.version(n) for n in ['jsonschema', 'referencing', 'pyshacl', 'rdflib', 'packageurl-python']}}
        emit(out / 'receipt.json', receipt)
        status.append(passed)
        for entry in record['raw'].values():
            require(sha(a.raw / entry['path']) == entry['sha256'], 'Raw output changed during qualification')
    emit(a.output / 'supplement.json', {'revision': revision, 'packageManifestSHA256': generation['sourceSHA256']['Package.swift'],
        'sourceLicenceSHA256': generation['sourceSHA256']['LICENSE'], 'noticeSHA256': generation['sourceSHA256']['NOTICE'],
        'swiftPMRuntimeDependencies': [], 'sourceReceipt': '../results/generation.json',
        'nativeLinkage': '../results/cli-linkage.log', 'artifacts': {k: v['artifacts'] for k,v in generation['products'].items()},
        'limits': ['Library build emits an object; it has no standalone dynamic linkage inventory.',
            'CLI otool load commands are observed platform linkage, not complete transitive SDK/runtime inventory or runtime versions.',
            'Platform component licences are not inferred from load commands.',
            'Third-party development fixtures, oracle containers and validation schemas retain separate notices; they are not linked runtime dependencies.',
            'Raw local package identifiers reflect the clean checkout directory. Original identities are retained; canonical source purl is explicitly derived from the repository URL and commit.',
            'No stable tag, release publication, vulnerability-free assertion or DICOMKit integration is established.']})
    emit(a.output / 'summary.json', {'status': 'passed' if all(status) else 'failed', 'revision': revision,
        'rawPreserved': True, 'products': list(generation['products'])})
    require(all(status), 'Derived validation failed')


if __name__ == '__main__':
    main()
