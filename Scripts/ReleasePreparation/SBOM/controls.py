#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Negative controls for SBOM schema, semantic, provenance and output guards."""
import argparse
import copy
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import qualify


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--evidence', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    a = p.parse_args()
    if a.output.exists():
        p.error('Refusing to overwrite controls evidence')
    a.output.mkdir(parents=True)
    root = a.evidence.resolve()
    raw = root / 'results'
    inputs = root / 'validation-inputs'
    generation = qualify.read(raw / 'generation.json')
    revision = generation['revision']
    validate = qualify.Validation(inputs)
    original = {s: qualify.read(root / 'derived/library' / (s + '.derived.json')) for s in ['spdx', 'cyclonedx']}
    protected = {str(x.relative_to(root)): qualify.sha(x) for x in root.rglob('*') if x.is_file() and not x.is_relative_to(a.output.resolve())}
    records = []

    def record(name, observed, expected=True, details=None):
        passed = observed == expected
        records.append({'name': name, 'passed': passed, 'observed': observed, 'expected': expected, 'details': details})
        qualify.emit(a.output / 'partial' / (str(len(records)) + '.json'), records[-1])
        qualify.require(passed, 'Control failed: ' + name)

    record('valid-derived-schema-and-semantic-baseline',
           all(validate.schema(s, d)['passed'] for s,d in original.items()) and
           not qualify.semantic_findings(original['spdx'], original['cyclonedx'], revision, 'SwiftJLS'))

    def mutate(name, action, stage):
        docs = copy.deepcopy(original)
        action(docs)
        if stage == 'schema':
            rejected = not validate.schema('spdx', docs['spdx'])['passed']
        else:
            rejected = bool(qualify.semantic_findings(docs['spdx'], docs['cyclonedx'], revision, 'SwiftJLS'))
            # These semantic controls remain structurally conformant: they
            # prove checks beyond JSON Schema, not duplicate schema failures.
            qualify.require(all(validate.schema(s,d)['passed'] for s,d in docs.items()), name + ' unexpectedly failed schema')
        record(name, rejected)

    mutate('unknown-SPDX-property-rejected', lambda d: d['spdx']['@graph'][-1].update(externalUrl='unsupported'), 'schema')
    mutate('duplicate-CycloneDX-reference-rejected', lambda d: d['cyclonedx']['components'].append(copy.deepcopy(d['cyclonedx']['metadata']['component'])), 'semantic')
    mutate('unresolved-CycloneDX-reference-rejected', lambda d: d['cyclonedx']['dependencies'][0]['dependsOn'].append('urn:missing'), 'semantic')
    mutate('stale-SPDX-revision-rejected', lambda d: next(x for x in d['spdx']['@graph'] if x.get('summary') == 'swift-package').update(software_packageVersion='0' * 40), 'semantic')
    mutate('wrong-product-rejected', lambda d: d['cyclonedx']['metadata']['component'].update(name='SwiftJLI'), 'semantic')
    mutate('missing-product-licence-rejected', lambda d: d['cyclonedx']['metadata']['component'].pop('licenses'), 'semantic')
    mutate('wrong-SPDX-specification-version-rejected', lambda d: next(x for x in d['spdx']['@graph'] if x['type'] == 'CreationInfo').update(specVersion='6.4.2'), 'semantic')
    mutate('unresolved-SPDX-reference-rejected', lambda d: next(x for x in d['spdx']['@graph'] if x['type'] == 'Relationship').update(to=['urn:missing']), 'semantic')
    mutate('wrong-package-URL-rejected', lambda d: next(x for x in d['spdx']['@graph'] if x.get('summary') == 'swift-package').update(software_packageUrl='pkg:swift/github.com/raster-labs/SwiftJLI@' + revision), 'semantic')
    docs = copy.deepcopy(original['spdx'])
    next(x for x in docs['@graph'] if x['type'] == 'CreationInfo').pop('createdBy')
    conforms, text, _ = validate.shacl(docs)
    (a.output / 'shacl-negative.txt').write_text(text)
    record('official-SHACL-missing-creator-rejected', not conforms)
    docs = copy.deepcopy(original['spdx'])
    docs['@context'] = 'https://example.invalid/unrecorded-context'
    try:
        validate.shacl(docs)
    except ValueError:
        record('unrecorded-JSONLD-context-rejected', True)
    else:
        record('unrecorded-JSONLD-context-rejected', False)

    def command(name, args, expected, message=None):
        result = subprocess.run([str(x) for x in args], capture_output=True, timeout=60)
        (a.output / (name + '.stdout')).write_bytes(result.stdout)
        (a.output / (name + '.stderr')).write_bytes(result.stderr)
        if message is not None:
            qualify.require(message.encode() in result.stderr, 'Wrong rejection reason: ' + name)
        record(name, result.returncode, expected, {'argv': list(map(str, args)), 'timeoutSeconds': 60})

    helper = Path(__file__).parent
    command('derived-output-preservation', [sys.executable, helper / 'qualify.py', '--raw', raw,
        '--inputs', inputs, '--output', root / 'derived'], 2)
    command('generation-output-preservation', [sys.executable, helper / 'generate.py', '--repository', root,
        '--revision', revision, '--output', raw, '--scratch', '/unused-control-scratch'], 2)
    with tempfile.TemporaryDirectory(prefix='swiftjls-sbom-controls-') as temp:
        temp = Path(temp)
        changed_inputs = temp / 'inputs'
        shutil.copytree(inputs, changed_inputs)
        with (changed_inputs / 'spdx-model.ttl.gz').open('ab') as stream:
            stream.write(b'tamper')
        command('tampered-validation-input-rejected', [sys.executable, helper / 'qualify.py', '--raw', raw,
            '--inputs', changed_inputs, '--output', temp / 'tampered-input-output'], 1)
        changed_raw = temp / 'raw'
        shutil.copytree(raw, changed_raw)
        target = changed_raw / generation['products']['library']['raw']['spdx']['path']
        target.write_bytes(target.read_bytes() + b' ')
        command('tampered-raw-SBOM-rejected', [sys.executable, helper / 'qualify.py', '--raw', changed_raw,
            '--inputs', inputs, '--output', temp / 'tampered-raw-output'], 1)
        target.write_bytes((raw / generation['products']['library']['raw']['spdx']['path']).read_bytes())
        for label, products, message in [
            ('empty-product-set-rejected', {}, 'Both product builds are required'),
            ('missing-CLI-product-rejected', {'library': generation['products']['library']}, 'Both product builds are required'),
            ('wrong-product-name-rejected', {**generation['products'], 'cli': {**generation['products']['cli'], 'product': 'swiftjli-cli'}}, 'Wrong selected product builds')]:
            (changed_raw / 'generation.json').write_text(json.dumps({**generation, 'products': products}))
            command(label, [sys.executable, helper / 'qualify.py', '--raw', changed_raw,
                '--inputs', inputs, '--output', temp / label], 1, message)
    record('all-original-evidence-preserved', all(qualify.sha(root / name) == digest for name,digest in protected.items()),
           details={'protectedFileCount': len(protected)})
    qualify.emit(a.output / 'receipt.json', {'status': 'passed', 'helperSHA256': qualify.sha(Path(__file__)),
        'qualificationHelperSHA256': qualify.sha(helper / 'qualify.py'), 'controls': records, 'count': len(records)})
    print(json.dumps({'status': 'passed', 'controls': len(records)}))


if __name__ == '__main__':
    main()
