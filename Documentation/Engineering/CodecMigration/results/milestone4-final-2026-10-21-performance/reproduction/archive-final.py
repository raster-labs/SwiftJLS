#!/usr/bin/env python3
"""Archive the final promoted-source performance checkpoint after all validation.

All inputs are mandatory and matched to the measured original-Consumer candidate.
No builds, timings, CI queries or source edits are performed. Missing or changed
records abort. The immutable bee intermediate archive is linked, never relabelled.
Use --check-only first; publication is exclusive and verifies copied hashes.
"""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import os
import shutil
import tempfile
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path(__file__).resolve().parent
HISTORY = ROOT / 'Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21.json'
HISTORY_SHA256 = '85b7d8c2e564591b2c1ac2e4a78f38fbee4ddc7d1d59486302e453908339596a'
MODES = ('debug', 'release', 'asan', 'tsan')
FIXTURES = 'Tests/SwiftJLSTests/Fixtures'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read(path):
    require(path.is_file(), f'Missing mandatory evidence: {path}')
    return json.loads(path.read_text())


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def git(*args, binary=False):
    result = subprocess.check_output(['git', *args], cwd=ROOT)
    return result if binary else result.decode().strip()


def repo_path(relative):
    require(isinstance(relative, str) and relative, 'Expected a repository-relative evidence path')
    path = (ROOT / relative).resolve()
    require(path.is_relative_to(ROOT), f'Evidence path escapes repository: {relative}')
    return path


def commit_files(checkpoint):
    """Full Sources/Tests/Package/VERSION inventory, including fixture resources."""
    raw = git('ls-tree', '-r', '--name-only', '-z', checkpoint, '--',
              'Sources', 'Tests', 'Package.swift', 'VERSION', binary=True)
    names = [name.decode() for name in raw.split(b'\0') if name]
    return {name: hashlib.sha256(git('show', f'{checkpoint}:{name}', binary=True)).hexdigest()
            for name in names}


def check_source_bridge(plan):
    """Bridge the actual pre-promotion candidate build to the promoted commit.

    Retain the candidate's original base revision and patch identity. Do not edit
    its build record to pretend it was built at the later commit. No rebuild is
    required when the measured frozen binary and every source input match.
    """
    checkpoint = plan['source_commit']
    require(isinstance(checkpoint, str) and git('rev-parse', checkpoint) == checkpoint,
            'A full existing final source commit is required')
    require(not git('diff', '--name-only', checkpoint, '--', 'Sources', 'Tests', 'Package.swift', 'VERSION'),
            'Current source/test/package/version differs from final checkpoint')
    require(not git('ls-files', '--others', '--exclude-standard', '--', 'Sources', 'Tests'),
            'Untracked source/test input is outside the checkpoint')
    files = commit_files(checkpoint)
    require(files and all(sha(ROOT / name) == digest for name, digest in files.items()),
            'Working files differ from final committed bytes')
    candidate_path = repo_path(plan['measured_candidate_build'])
    build = read(candidate_path)
    require(build['command']['exit_code'] == 0 and build['source_unchanged'] is True
            and build['consumer_unchanged'] is True, 'Candidate build integrity is not established')
    measured = build['source']
    require(measured['developer_dir'] == '/Library/Developer/CommandLineTools', 'Wrong candidate toolchain selection')
    nonfixtures = {name: digest for name, digest in files.items() if not name.startswith(FIXTURES + '/')}
    require(nonfixtures == measured['source_files'],
            'Final source/test/package/version inventory or bytes differ from measured candidate')
    require(git('rev-parse', checkpoint + ':' + FIXTURES) == measured['fixtures_tree'],
            'Candidate fixture tree differs from final fixture tree')
    require(sha(repo_path(plan['measured_candidate_binary'])) == build['binary_sha256'],
            'Frozen measured candidate binary changed')
    require(sha(ROOT / 'Scripts/Benchmark/Consumer.swift') == measured['consumer_sha256'],
            'Measured consumer is not the unchanged original common Consumer')
    require(sha(candidate_path.parent / 'consumer/Sources/Benchmark/main.swift') == measured['consumer_sha256'] and
            sha(candidate_path.parent / 'consumer/Package.swift') == measured['consumer_package_sha256'],
            'Candidate Consumer/package differs from its measured build')
    # The fresh driver captures every Sources/Tests byte plus Package and VERSION.
    # Require that actual record; never retrofit VERSION into historical records.
    tested_files = files
    for relative in ('tests/source.json', 'qualification-source.json'):
        require(read(SCRATCH / relative)['files'] == tested_files,
                f'{relative}: tested source differs from the measured/promoted source')
    require(read(SCRATCH / 'consumer-builds.json')['source']['files'] == tested_files,
            'Qualified consumer build used different source')
    native = read(SCRATCH / 'native-payload/manifest.json')
    require(native['source_commit'] == checkpoint and
            native['sources_tree'] == git('rev-parse', checkpoint + ':Sources') and
            native['tests_tree'] == git('rev-parse', checkpoint + ':Tests'),
            'Native payload differs from promoted source/test trees')
    return dict(source_commit=checkpoint, source_files=files,
                measured_candidate_build=str(candidate_path.relative_to(ROOT)),
                measured_candidate_build_sha256=sha(candidate_path),
                measured_candidate_base=measured['base_source'],
                measured_candidate_patch_sha256=measured['patches']['combined.patch'],
                measured_binary_sha256=build['binary_sha256'],
                consumer_sha256=measured['consumer_sha256'],
                status='Exact byte bridge; original candidate provenance retained')


def xml_counts(path):
    cases = ET.parse(path).findall('.//testcase')
    require(cases, f'No test declarations in {path}')
    return dict(declarations=len(cases),
                failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases))


def check_guard_plan(plan, bridge):
    """Identify the predeclared selection; this does not claim it was executed."""
    path = repo_path(plan['measurement_plan'])
    selection = read(path)
    require(sha(path) == 'e53e2e11ff679398dbb5de160e72c08a53ca5809fb2117e42777510158048bef',
            'The predeclared 15-case larger selection changed')
    keys = ('width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave')
    cases = [tuple(row[k] for k in keys) for row in selection['cases']]
    require(cases and len(cases) == len(set(cases)), 'Empty/duplicate larger guard selection')
    require(selection['consumer_sha256'] == bridge['consumer_sha256'], 'Guard plan uses a different Consumer')
    require(selection['blocks_per_case'] == 4 and selection['warmups'] == 5 and
            selection['observations_per_process'] == 5, 'Predeclared larger guard protocol changed')
    require(selection['operations'] == ['encode', 'decode', 'prepare', 'prepare_encode'],
            'Predeclared guard operations are incomplete')
    return dict(plan=str(path.relative_to(ROOT)), plan_sha256=sha(path), cases=len(cases),
                expected_processes=len(cases) * selection['blocks_per_case'] * 2,
                prepared_utc=selection['prepared_utc'], execution_verified=False)


def check_unit_results(checkpoint):
    """Derive counts from all eight XML records, never a planned test count."""
    host = read(SCRATCH / 'tests/results.json')
    require(len(host) == 4 and {r['label'] for r in host} == set(MODES), 'Missing/duplicate host modes')
    native = read(SCRATCH / 'native-results/results.json')
    require(native['source'] == checkpoint and native['success'] is True and
            native['exact_26_0_native_arm64'] is True and
            all(row['exit_code'] == 0 for row in native['commands']), 'Incomplete/failed exact native qualification')
    counts = {}
    for record in host:
        mode = record['label']
        actual = xml_counts(SCRATCH / f'tests/{mode}.xml')
        require(record['exit_code'] == 0 and all(record.get(k) == v for k, v in actual.items()) and
                actual['failures'] == actual['skipped'] == 0, f'Host {mode} failed or XML differs')
        filename = 'unit.xml' if mode == 'release' else f'unit-{mode}.xml'
        native_actual = xml_counts(SCRATCH / 'native-results' / filename)
        reported = native['tests'] if mode == 'release' else native['extra_tests'][mode]
        require(native_actual == reported == actual, f'Native/host {mode} count/result mismatch')
        counts[mode] = actual
    require(len({row['declarations'] for row in counts.values()}) == 1, 'Configuration declaration counts differ')
    return counts


def module(name):
    path = SCRATCH / (name + '.py')
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--prepare-review', action='store_true', help='Write independently recomputed performance and coverage inputs; do not publish an archive or require the remote workspace/mutation jobs to have finished')
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--candidate-build-identity', type=Path, required=True)
    args = parser.parse_args()
    require(not (args.check_only and args.prepare_review), 'Select check-only or prepare-review, not both')
    plan = read(args.plan)
    require(plan.get('review_status') == 'approved_for_validation', 'Final evidence plan has not been reviewed')
    require(args.candidate_build_identity.resolve() == repo_path(plan['measured_candidate_build']), 'Explicit candidate identity differs from reviewed archive plan')
    require(sha(HISTORY) == HISTORY_SHA256, 'Immutable bee intermediate manifest changed')
    require(repo_path(plan['historical_manifest']) == HISTORY and plan['historical_manifest_sha256'] == HISTORY_SHA256 and
            repo_path(plan['workspace_directory']) == SCRATCH / 'workspace-accounting-evidence' and
            repo_path(plan['mutation_directory']) == SCRATCH / 'mutation', 'Reviewed plan evidence roots differ from the selected adapters')
    historical = read(HISTORY)
    require(historical['checkpoint_status'] == 'intermediate' and historical['milestone4_complete'] is False,
            'Historical checkpoint classification changed')
    bridge = check_source_bridge(plan)
    checkpoint = bridge['source_commit']
    build = read(args.candidate_build_identity)
    guard_identity = check_guard_plan(plan, bridge)
    larger_plan_path = repo_path(plan['measurement_plan'])
    larger_plan = read(larger_plan_path)
    benchmark = read(SCRATCH / 'benchmark-build.json')
    reuse = read(SCRATCH / 'benchmark-reuse.json')
    require(benchmark['source_commit'] == checkpoint and benchmark['builds_verified'] is True and
            benchmark['binary_sha256']['successor'] == bridge['measured_binary_sha256'] and
            benchmark['consumer_sha256'] == bridge['consumer_sha256'] and
            benchmark['original_candidate_build_identity_sha256'] == bridge['measured_candidate_build_sha256'],
            'Final benchmark/source bridge mismatch')
    require(reuse['source_commit'] == checkpoint and reuse['verified'] is True and reuse['rebuilt'] is False and
            reuse['original_build_record'] == build and reuse['build_identity_sha256'] == bridge['measured_candidate_build_sha256'] and
            reuse['binary']['sha256'] == bridge['measured_binary_sha256'], 'Frozen reuse record differs from measured candidate')
    require(sha(repo_path(benchmark['binaries']['predecessor'])) == benchmark['binary_sha256']['predecessor'], 'Frozen predecessor binary changed')
    sources, generated, exclusions = {}, {}, []
    destination = ROOT / 'Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance'
    manifest_path = destination.with_suffix('.json')

    def add(path, relative=None):
        path = Path(path)
        require(path.is_file() and not path.is_symlink(), 'Missing/nonregular evidence: ' + str(path))
        key = str(relative) if relative is not None else str(path.relative_to(SCRATCH))
        require(not Path(key).is_absolute() and '..' not in Path(key).parts, 'Unsafe archive path: ' + key)
        require(key not in generated and (key not in sources or sources[key] == path), 'Duplicate archive path: ' + key)
        require(path.stat().st_size < 64 * 1024 * 1024, 'Evidence needs explicit compact packaging: ' + str(path))
        with path.open('rb') as stream: magic = stream.read(4)
        require(magic not in [b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'], 'Executable must not enter compact archive: ' + str(path))
        sources[key] = path

    def add_tree(folder, prefix):
        require(folder.is_dir(), 'Missing evidence directory: ' + str(folder))
        for current, directories, filenames in os.walk(folder):
            current = Path(current)
            for name in list(directories):
                path = current / name
                require(not path.is_symlink(), 'Evidence directory symlink: ' + str(path))
                if name in {'.build', '__pycache__', 'test-build', 'native-payload', '.git'}:
                    exclusions.append(str(path.relative_to(ROOT)))
                    directories.remove(name)
            for filename in sorted(filenames):
                path = current / filename
                add(path, str(Path(prefix) / path.relative_to(folder)))

    evidence = module('archive-evidence')
    software = evidence.validate_software(checkpoint, add)
    workspace = None if args.prepare_review else evidence.validate_workspace(checkpoint, add)
    mutation = None if args.prepare_review else evidence.validate_mutation(checkpoint, add)
    specs = plan['measurements']
    required_kinds = {'tiny-deep', 'larger', 'tiny-confirmation128'}
    selected_kinds = {spec['kind'] for spec in specs}
    require(selected_kinds in (required_kinds, required_kinds | {'tiny-short'}) and
            len(specs) == len(selected_kinds) == len({spec['name'] for spec in specs}),
            'Selected source requires fixed128 short,16-pair deep and larger guards; preserve an existing selected-source16-pair short campaign without requiring a redundant new one')
    measurements = module('archive-measurements')
    performance = []
    for spec in specs:
        if spec['kind'] == 'larger':
            require(repo_path(spec['larger_guard_plan']) == larger_plan_path, 'Different larger plan selected')
        performance.append(measurements.validate(spec, ROOT, bridge, build, benchmark, larger_plan, add, add_tree))
    size_validation = evidence.validate_size(checkpoint, benchmark, performance, add, add_tree)
    generated['size-validation/recomputed.json'] = size_validation
    diagnostic_adapter = module('archive-diagnostics')
    diagnostic_bridge, diagnostic_build, preceding_results = diagnostic_adapter.preceding(
        plan, ROOT, bridge, build, benchmark, measurements, add, add_tree)
    diagnostic_results = preceding_results + diagnostic_adapter.validate(plan['diagnostic_sources'], ROOT,
        diagnostic_bridge, diagnostic_build, benchmark, measurements, add, add_tree)
    incremental = plan.get('incremental_diagnostic')
    require(bool(incremental) == any(spec.get('identity_schema') == 'owned-admission-v1' for spec in specs),
            'Selected owned-admission measurements must retain their incremental diagnostic')
    if incremental:
        require(incremental['name'] not in {row['name'] for row in performance + diagnostic_results}, 'Duplicate incremental campaign name')
        diagnostic_results.append(diagnostic_adapter.incremental(incremental, ROOT, bridge, build,
            diagnostic_bridge, benchmark, measurements, add, add_tree))
    generated['diagnostic-measurements-recomputed.json'] = dict(parent_source_commit=checkpoint,
        campaigns=diagnostic_results, production_qualification=False,
        scope='Preceding candidates, A/A controls and synchronous executor counterfactual retain original identities and remain separate from selected-source production campaigns')
    threshold_findings = []
    review_campaigns = performance + [row for row in diagnostic_results if row.get('diagnostic_category') == 'incremental_candidate']
    for campaign in review_campaigns:
        scope = campaign.get('diagnostic_scope') or 'Selected-source pinned-baseline comparison'
        for row in campaign['cases']:
            case = row['case']['id']
            for operation, metric in row['operations'].items():
                if metric['pooled_ratio'] > 1.05 or metric.get('interpretation') in ('unresolved', 'confirmed_regression'):
                    threshold_findings.append(dict(key=f"{campaign['name']}/{case}/{operation}", campaign=campaign['name'], case=case, metric=operation,
                        pooled_ratio=metric['pooled_ratio'], absolute_delta_microseconds=1e6 * (metric['pooled_median_seconds']['candidate'] - metric['pooled_median_seconds']['reference']), paired_ratios=[p['ratio'] for p in metric['pairs']], comparison_scope=scope))
                    threshold_findings[-1]['familywise_interpretation'] = metric.get('interpretation')
                    threshold_findings[-1]['familywise_bonferroni_95'] = metric.get('familywise_bonferroni_95')
            for metric, threshold in [('encoded_bytes', 1.01), ('peak_process_rss_bytes', 1.05)]:
                if row[metric]['ratio'] > threshold:
                    threshold_findings.append(dict(key=f"{campaign['name']}/{case}/{metric}", campaign=campaign['name'], case=case, metric=metric, pooled_ratio=row[metric]['ratio'], scope='RSS is not algorithm workspace' if metric.startswith('peak_') else 'Encoded stream size', comparison_scope=scope))
    generated['performance-recomputed.json'] = dict(source_commit=checkpoint, binary_sha256=benchmark['binary_sha256'],
        measurements=performance, threshold_findings=threshold_findings, acceptance='Not determined by automatic thresholds')
    if args.prepare_review:
        # This is a drafting aid, not an authored disposition, archive or waiver.
        # Fresh source/software/performance identities have passed; remote ledger
        # and mutation evidence remain unexamined in this mode and are mandatory
        # again in check-only/publication modes.
        review = SCRATCH / 'review-inputs'
        require(not review.exists(), 'Review input directory exists; refusing overwrite')
        review.mkdir()
        draft = dict(source_commit=checkpoint, binary_sha256=benchmark['binary_sha256'], reviewed_status='PENDING AUTHOR REVIEW',
            findings=[dict(id='observation-' + str(index + 1), status='unreviewed', explanation='', covers=[row['key']],
                           evidence=['performance-recomputed.json']) for index, row in enumerate(threshold_findings)],
            scope='Coverage template only; unresolved remains unresolved until an explicit authored decision. Workspace/mutation were not checked in this mode.')
        for name, value in {**generated, 'source-bridge.json': bridge, 'coverage-template.json': draft}.items():
            target = review / name
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open('x') as stream: json.dump(value, stream, indent=2); stream.write('\n')
        print(json.dumps(dict(review_inputs=str(review.relative_to(ROOT)), findings_requiring_review=len(threshold_findings),
                              archive_published=False, performance_accepted=False, workspace_and_mutation_checked=False)))
        return
    disposition_path = repo_path(plan['reviewed_performance_disposition'])
    disposition = read(disposition_path)
    require(disposition['source_commit'] == checkpoint and disposition['binary_sha256'] == benchmark['binary_sha256'] and
            isinstance(disposition['reviewed_status'], str) and disposition['reviewed_status'] and
            isinstance(disposition['findings'], list) and disposition['findings'], 'Missing authored current-source performance review')
    require(len({row['id'] for row in disposition['findings']}) == len(disposition['findings']) and
            all(row.get('status') and row.get('evidence') and (row.get('explanation') or row.get('reason')) for row in disposition['findings']),
            'Incomplete or duplicate authored disposition findings')
    require(disposition['reviewed_status'] != 'PENDING AUTHOR REVIEW' and
            all(row['status'] != 'unreviewed' for row in disposition['findings']), 'Draft coverage template is not an authored review')
    expected_coverage = {row['key'] for row in threshold_findings}
    coverage = []
    for finding in disposition['findings']:
        keys = finding.get('covers', [])
        require(isinstance(keys, list) and all(isinstance(key, str) for key in keys),
                'Disposition covers must be a list of threshold finding keys')
        coverage.extend(keys)
    require(len(coverage) == len(set(coverage)) and set(coverage) == expected_coverage,
            'Every recomputed threshold finding must be covered exactly once; missing=' +
            repr(sorted(expected_coverage - set(coverage))) + '; unknown=' + repr(sorted(set(coverage) - expected_coverage)))
    add(disposition_path, 'reviewed-performance-disposition.json')
    add(larger_plan_path, 'performance/larger-guard-plan.json')
    add(args.plan.resolve(), 'archive-plan.json')
    add(args.candidate_build_identity.resolve(), 'measured-candidate/build-identity.json')
    candidate_root = args.candidate_build_identity.resolve().parent
    require(read(candidate_root / 'source-identity.json') == build['source'], 'Candidate source/build identity records differ')
    for name in build['source']['patches']:
        path = candidate_root / name
        require(sha(path) == build['source']['patches'][name], 'Candidate patch changed: ' + name)
        add(path, 'measured-candidate/' + name)
    require(sha(candidate_root / 'consumer/Sources/Benchmark/main.swift') == build['source']['consumer_sha256'] == bridge['consumer_sha256'],
            'Candidate Consumer bytes changed after build/reuse validation')
    require(sha(candidate_root / 'consumer/Package.swift') == build['source']['consumer_package_sha256'],
            'Candidate Consumer package bytes changed after build/reuse validation')
    for name in ['source-identity.json', 'consumer/Package.swift', 'consumer/Sources/Benchmark/main.swift']:
        add(candidate_root / name, 'measured-candidate/' + name)
    for name in build['source']['source_files']:
        add(ROOT / name, 'source/' + name)
    for mode in ('release', 'asan'):
        record = build[mode]
        command = record['command']
        require(record['exit_code'] == 0 and command.count('--xunit-output') == 1, 'Candidate focused validation failed or XML path missing')
        xml = Path(command[command.index('--xunit-output') + 1]).resolve()
        require(xml.is_relative_to(candidate_root) and sha(xml) == record['xml_sha256'], 'Candidate focused validation record changed')
        count = xml_counts(xml)
        require(count['declarations'] == record['test_count'] and count['failures'] == count['skipped'] == 0,
                'Candidate focused validation XML is incomplete/failed')
        add(xml, 'measured-candidate/' + str(xml.relative_to(candidate_root)))
    for path in candidate_root.glob('*.log'):
        add(path, 'measured-candidate/' + path.name)
    for pattern in ('*.py', '*.json', '*.md'):
        for path in candidate_root.glob(pattern):
            add(path, 'measured-candidate/' + path.name)
    add_tree(SCRATCH / 'diagnostics', 'diagnostics')
    superseded_guards = SCRATCH / 'larger-guard-preparation-three-change'
    if incremental:
        require(read(superseded_guards / 'status.json')['status'].startswith('Unexecuted preparation preserved'),
                'Superseded larger-guard preparation lost its unexecuted status')
        add_tree(superseded_guards, 'diagnostics/larger-guard-preparation-three-change')
    failed_candidate = SCRATCH / 'diagnostics/singleton-parser/manifest.json'
    candidate_manifest = read(failed_candidate)
    entries = candidate_manifest['files']
    require(isinstance(entries, list) and entries, 'Missing intermediate two-change candidate archive')
    listed = set()
    for entry in entries:
        relative = entry['path']; path = (failed_candidate.parent / relative).resolve()
        require(path.is_relative_to(failed_candidate.parent.resolve()) and path.is_file() and path.stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], 'Intermediate candidate manifest mismatch: ' + relative)
        require(relative not in listed, 'Duplicate intermediate candidate file')
        listed.add(relative)
    require(listed == {str(path.relative_to(failed_candidate.parent)) for path in failed_candidate.parent.rglob('*') if path.is_file() and path != failed_candidate}, 'Intermediate candidate inventory mismatch')
    for path in SCRATCH.glob('*.py'):
        add(path, 'reproduction/' + path.name)
    generated['validation-driver-identities.json'] = dict(
        scope='Current final driver hashes; the initial prepared-validation-drivers.json is retained as historical preparation, not rewritten',
        scripts={path.name: sha(path) for path in sorted(SCRATCH.glob('*.py'))})
    for name in ['prepared-validation-drivers.json', 'ARCHIVE-CHECKLIST.md', 'archive-static-review.json']:
        add(SCRATCH / name, 'reproduction/' + name)
    for name in ['Scripts/Benchmark/Consumer.swift', 'Scripts/Benchmark/compare.py', 'Scripts/test-cli.py', 'Scripts/test-payload-cli.py']:
        add(ROOT / name, 'reproduction/' + name)
    add(SCRATCH / 'native-payload/run-native.py', 'reproduction/run-native.py')
    for path in SCRATCH.glob('*.log'):
        if not path.name.startswith('archive-publish'):
            add(path)
    for name in ['preexisting-simulator-state.json', 'simulator-restore.json']:
        if (SCRATCH / name).is_file(): add(SCRATCH / name)
    for name in ['benchmark-build-record-command.json', 'larger-guard-preflight-attempt-1.json',
                 'larger-guard-command.json', 'larger-guard-summary.json',
                 'mutation-status-attempt-1.json', 'mutation-collection-command.json']:
        if (SCRATCH / name).is_file(): add(SCRATCH / name)
    # Preserve these receipts verbatim. Their recorded source-review and
    # historical PR-selection scope is not general CI or merge verification.
    for name in ['source-review.json', 'github-handoff-context.json']:
        add(SCRATCH / name)
    if (SCRATCH / 'precommit-source-bridge.json').is_file():
        receipt = read(SCRATCH / 'precommit-source-bridge.json')
        require(receipt.get('source_commit') is None, 'Precommit receipt must retain its original uncommitted status')
        add(SCRATCH / 'precommit-source-bridge.json')
    if (SCRATCH / 'source-handoff.json').is_file():
        handoff = read(SCRATCH / 'source-handoff.json')
        require(handoff['source_commit'] == handoff['remote_head'] == checkpoint and
                handoff['source_matches_measured_candidate'] is True and
                handoff['build_identity_sha256'] == bridge['measured_candidate_build_sha256'] and
                handoff['host_modes'] == read(SCRATCH / 'tests/results.json'), 'Source push/host handoff receipt differs')
        add(SCRATCH / 'source-handoff.json')
    generated['source-bridge.json'] = bridge
    for finding in disposition['findings']:
        for reference in finding['evidence']:
            if reference.startswith('historical:'):
                prefix = 'historical:milestone4-final-2026-10-21/'
                require(reference.startswith(prefix) and reference[len(prefix):] in historical['files'], 'Unanchored historical reference: ' + reference)
            else:
                require(reference in sources or reference in generated, 'Disposition evidence is not archived: ' + reference)
    inventory = {key: dict(bytes=path.stat().st_size, sha256=sha(path), source=str(path.relative_to(ROOT))) for key, path in sorted(sources.items())}
    generated_bytes = {key: (json.dumps(value, indent=2) + '\n').encode() for key, value in generated.items()}
    for key, value in generated_bytes.items():
        inventory[key] = dict(bytes=len(value), sha256=hashlib.sha256(value).hexdigest(), source='Generated from validated evidence')
    manifest = dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        production_checkpoint=checkpoint, checkpoint_status='final software/performance evidence; see authored disposition',
        archive_directory=destination.name, source_bridge=bridge, software_validation_passed=software['passed'],
        software=software, workspace=workspace, mutation=mutation, performance=performance, size_validation=size_validation, diagnostic_campaigns=diagnostic_results,
        predeclared_larger_plan=guard_identity, reviewed_performance_disposition=disposition,
        automatic_performance_acceptance=False, milestone4_complete=False,
        historical_evidence=dict(manifest=HISTORY.name, sha256=HISTORY_SHA256, scope='Immutable intermediate bee checkpoint; its 63-case data is not relabelled as final source'),
        diagnostic_classification={'diagnostics/singleton-parser': 'Intermediate unpromoted two-change candidate; short-mode performance regressions retained',
                                   'diagnostics/three-change-host-validation': 'Earlier source host validation and precommit receipt; not selected-source qualification',
                                   'diagnostics/larger-guard-preparation-three-change': 'Superseded unexecuted preparation; not measured larger-case evidence'},
        exclusions=sorted(set(exclusions)), files=inventory,
        limitations=['Physical device testing remains pending; Milestone 5 is deferred.',
                     'User verifies CI and merges; no general CI acceptance is asserted.',
                     'Exact native OS 26.0 uses a hardware-virtualised arm64 environment.',
                     'Requested heap, stack, allocator overhead and RSS remain distinct; finite workspace evidence does not turn unknown into zero.',
                     'Performance acceptance is the authored finding-by-finding decision, never an automatic ratio waiver.'])
    print(json.dumps(dict(checkpoint=checkpoint, files=len(inventory), bytes=sum(row['bytes'] for row in inventory.values()),
        local_test_declarations={key: row['declarations'] for key, row in software['local_tests'].items()},
        performance_processes={row['kind']: row['processes'] for row in performance}, check_only=args.check_only)))
    if args.check_only: return
    require(not destination.exists() and not manifest_path.exists(), 'Archive already exists; refusing overwrite')
    stage = Path(tempfile.mkdtemp(prefix='.milestone4-performance-', dir=destination.parent))
    try:
        for key, path in sources.items():
            target = stage / key; target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            require(sha(target) == inventory[key]['sha256'], 'Evidence changed while copying: ' + str(path))
        for key, value in generated_bytes.items():
            target = stage / key; target.parent.mkdir(parents=True, exist_ok=True); target.write_bytes(value)
        with manifest_path.open('x') as stream: json.dump(manifest, stream, indent=2); stream.write('\n')
        stage.rename(destination)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    actual = {str(path.relative_to(destination)) for path in destination.rglob('*') if path.is_file()}
    require(actual == set(inventory), 'Published archive inventory mismatch')
    for key, entry in inventory.items():
        require((destination / key).stat().st_size == entry['bytes'] and sha(destination / key) == entry['sha256'], 'Published archive integrity mismatch: ' + key)
    print(json.dumps(dict(archived=str(destination.relative_to(ROOT)), manifest=str(manifest_path.relative_to(ROOT)), manifest_sha256=sha(manifest_path), verified_files=len(actual))))


if __name__ == '__main__':
    main()
