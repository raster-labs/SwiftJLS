"""A/A and executor-policy records are diagnostics, never final production evidence."""
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def preceding(plan, root, bridge, build, benchmark, measurements, add, add_tree):
    """Keep an earlier measured candidate distinct from the selected final source.

    A/A and executor controls retain their original parent. If that parent is
    superseded, require all of its original short/deep/128 campaigns rather than
    assigning those observations to a later source or inventing a commit bridge.
    """
    require, sha, read = measurements.require, measurements.sha, measurements.read
    identity = (root / plan['diagnostic_basis_build']).resolve()
    require(identity.is_relative_to(root) and identity.is_file(), 'Missing/unsafe diagnostic basis identity')
    specs = plan['preceding_candidate_measurements']
    if identity == (root / bridge['measured_candidate_build']).resolve():
        require(not specs, 'Selected candidate cannot also be labelled preceding')
        return bridge, build, []

    prior = read(identity)
    folder, source = identity.parent, prior['source']
    require(prior['command']['exit_code'] == 0 and prior['source_unchanged'] is True and
            prior['consumer_unchanged'] is True and read(folder / 'source-identity.json') == source,
            'Preceding candidate build/source records differ or failed')
    require(source['developer_dir'] == build['source']['developer_dir'] == '/Library/Developer/CommandLineTools' and
            source['swift'] == build['source']['swift'] and
            source['consumer_sha256'] == bridge['consumer_sha256'], 'Preceding compiler/common Consumer differs')
    require(source['source_files'] and {'Package.swift', 'VERSION'} <= source['source_files'].keys(),
            'Incomplete preceding candidate source inventory')
    for name, digest in source['source_files'].items():
        path = (folder / 'codec' / name).resolve()
        require(path.is_relative_to(folder / 'codec') and path.is_file() and sha(path) == digest,
                'Preceding candidate source changed: ' + name)
        add(path, 'preceding-candidate/source/' + name)
    fixture_tree = subprocess.check_output(['git', 'rev-parse', source['base_source'] + ':Tests/SwiftJLSTests/Fixtures'], cwd=root).decode().strip()
    require(fixture_tree == source['fixtures_tree'], 'Preceding fixture provenance differs from its base')
    for name, digest in source['patches'].items():
        require(Path(name).name == name and sha(folder / name) == digest, 'Preceding candidate patch changed')
        add(folder / name, 'preceding-candidate/' + name)
    for name, digest in [('consumer/Sources/Benchmark/main.swift', source['consumer_sha256']),
                         ('consumer/Package.swift', source['consumer_package_sha256'])]:
        require(sha(folder / name) == digest, 'Preceding Consumer/package changed')
        add(folder / name, 'preceding-candidate/' + name)
    binary = Path(prior['binary']).resolve()
    require(binary.is_relative_to(folder) and sha(binary) == prior['binary_sha256'], 'Preceding measured binary changed')
    for mode in ('release', 'asan'):
        record = prior[mode]
        command = record['command']
        require(record['exit_code'] == 0 and command.count('--xunit-output') == 1, 'Preceding focused validation failed')
        xml = Path(command[command.index('--xunit-output') + 1]).resolve()
        require(xml.is_relative_to(folder) and sha(xml) == record['xml_sha256'], 'Preceding focused XML identity changed')
        cases = ET.parse(xml).findall('.//testcase')
        require(len(cases) == record['test_count'] > 0 and
                all(case.find('failure') is None and case.find('error') is None and case.find('skipped') is None for case in cases),
                'Preceding focused XML is incomplete/failed')
        add(xml, 'preceding-candidate/' + str(xml.relative_to(folder)))
    for pattern in ('*.py', '*.json', '*.log', '*.md'):
        for path in folder.glob(pattern): add(path, 'preceding-candidate/' + path.name)

    prior_bridge = dict(source_commit=None, measured_candidate_build=str(identity.relative_to(root)),
        measured_candidate_build_sha256=sha(identity), measured_candidate_base=source['base_source'],
        measured_candidate_patch_sha256=source['patches']['combined.patch'],
        measured_binary_sha256=prior['binary_sha256'], consumer_sha256=source['consumer_sha256'],
        status='Preceding candidate only; no final-source qualification or promotion identity inferred')
    kinds = {spec['kind'] for spec in specs}
    names = {spec['name'] for spec in specs}
    require(kinds == {'tiny-short', 'tiny-deep', 'tiny-confirmation128'} and len(specs) == len(kinds) == len(names) and
            not names.intersection(spec['name'] for spec in plan['measurements']),
            'Preceding candidate requires distinct original16 short/deep and128 campaigns')
    hashes = {'reference': benchmark['binary_sha256']['predecessor'], 'candidate': prior['binary_sha256']}

    def verify(schedule, environment, completion):
        require(schedule['producers']['reference']['source'] == benchmark['predecessor_commit'] and
                schedule['producers']['candidate']['base_revision'] == source['base_source'] and
                schedule['producers']['candidate']['patch_sha256'] == source['patches']['combined.patch'] and
                all(schedule['producers'][label]['sha256'] == digest for label, digest in hashes.items()),
                'Preceding comparison producer identity mismatch')
        for guards in (environment['source_guards'], completion['source_guards']):
            require(guards['candidate_source_hashes'] == source['source_files'] and
                    guards['candidate_build_identity_sha256'] == prior_bridge['measured_candidate_build_sha256'] and
                    guards['candidate_patch_sha256'] == source['patches']['combined.patch'] and
                    guards['candidate_binary_sha256'] == prior['binary_sha256'] and
                    guards['successor_head']['output'].strip() == source['base_source'] and
                    guards['predecessor_head']['output'].strip() == benchmark['predecessor_commit'] and
                    all(guards[key]['exit_code'] == 0 for key in ('successor_head', 'successor_diff', 'predecessor_head', 'predecessor_diff')),
                    'Preceding comparison source guards mismatch')

    results = [measurements.validate(spec, root, prior_bridge, prior, benchmark, {}, add, add_tree,
        diagnostic=dict(category='preceding_candidate', hashes=hashes, validate_identity=verify,
                        scope='Preceding candidate measurements retained at original source; not final-source qualification')) for spec in specs]
    return prior_bridge, prior, results


def incremental(spec, root, bridge, build, prior_bridge, benchmark, measurements, add, add_tree):
    require, read = measurements.require, measurements.read
    require(spec['kind'] == 'diagnostic-short' and spec['identity_schema'] == 'owned-admission-v1',
            'Incremental candidate comparison requires its recorded owned-admission schema')
    path = (root / spec['frozen_plan']).resolve()
    require(path.is_relative_to(root), 'Unsafe incremental plan path')
    frozen = read(path)
    require(frozen['three_change']['build_identity_sha256'] == prior_bridge['measured_candidate_build_sha256'] and
            frozen['three_change']['binary_sha256'] == prior_bridge['measured_binary_sha256'],
            'Incremental reference is not the archived preceding candidate')
    return measurements.validate(spec, root, bridge, build, benchmark, {}, add, add_tree,
        diagnostic=dict(category='incremental_candidate',
            hashes={'reference': prior_bridge['measured_binary_sha256'], 'candidate': bridge['measured_binary_sha256']},
            scope='Selected fourth candidate versus preceding three-change candidate; incremental diagnostic, not pinned-baseline qualification'))


def validate(config, root, bridge, build, benchmark, measurements, add, add_tree):
    require, sha, read = measurements.require, measurements.sha, measurements.read
    source = build['source']
    parent_hash = bridge['measured_candidate_build_sha256']
    parent_binary = bridge['measured_binary_sha256']
    pinned_binary = benchmark['binary_sha256']['predecessor']

    def directory(key):
        folder = (root / config[key]).resolve()
        require(folder.is_relative_to(root) and folder.is_dir(), 'Missing/unsafe diagnostic root: ' + key)
        return folder

    def parent_guards(guards):
        require(guards['candidate_build_identity_sha256'] == parent_hash and
                guards['candidate_source_hashes'] == source['source_files'] and
                guards['candidate_patch_sha256'] == source['patches']['combined.patch'] and
                guards['candidate_binary_sha256'] == parent_binary, 'Diagnostic parent identity mismatch')
        require(guards['successor_head']['output'].strip() == source['base_source'] and
                guards['predecessor_head']['output'].strip() == benchmark['predecessor_commit'] and
                all(guards[k]['exit_code'] == 0 for k in ('successor_head', 'successor_diff', 'predecessor_head', 'predecessor_diff')),
                'Diagnostic parent head/diff guards failed')

    def compact_metadata(folder, prefix):
        for pattern in ('*.py', '*.json', '*.log', '*.md', '*.patch'):
            for path in folder.glob(pattern): add(path, prefix + '/' + path.name)
        add_tree(folder / 'schedules', prefix + '/schedules')

    controls = directory('same_producer_controls')
    results = []
    for control, binary in [('candidate-self', parent_binary), ('pinned-self', pinned_binary)]:
        def verify(plan, environment, completion, control=control, binary=binary):
            require(plan['control'] == control and plan['producers']['reference'] == plan['producers']['candidate'] and
                    all(row['sha256'] == binary for row in plan['producers'].values()), 'A/A producers are not identical')
            if control == 'candidate-self':
                require(plan['producers']['candidate']['base_revision'] == source['base_source'] and
                        plan['producers']['candidate']['patch_sha256'] == source['patches']['combined.patch'], 'A/A candidate source mismatch')
            else:
                require(plan['producers']['candidate']['source'] == benchmark['predecessor_commit'], 'A/A pinned source mismatch')
            parent_guards(environment['source_guards']); parent_guards(completion['source_guards'])
        spec = dict(kind='diagnostic-short', name='aa-' + control,
                    root=str((controls / 'results' / control).relative_to(root)),
                    schedule=str((controls / 'schedules' / (control + '.json')).relative_to(root)),
                    runner=str((controls / 'run.py').relative_to(root)))
        results.append(measurements.validate(spec, root, bridge, build, benchmark, {}, add, add_tree,
            diagnostic=dict(hashes={'reference': binary, 'candidate': binary}, validate_identity=verify,
                            scope='Identical-binary A/A control; not a cross-producer performance result or automatic waiver')))
    compact_metadata(controls, 'diagnostics/same-producer-controls')

    executor = directory('executor_counterfactual')
    identity_path = executor / 'build-identity.json'
    diagnostic_build = read(identity_path)
    diagnostic_source = diagnostic_build['source']
    # The frozen build uses a scope string here; measurement guards use the
    # Boolean diagnostic_only below. Preserve both schemas without rewriting
    # the historical build or weakening any parent/source/binary identity check.
    require(diagnostic_build['diagnostic_only'] == 'Removing required executor policy is forbidden in production; ABI/optimisation/layout may also differ.' and
            diagnostic_build['promoted'] is False and diagnostic_source['promoted'] is False and
            diagnostic_build['source_unchanged'] is True and diagnostic_build['consumer_unchanged'] is True and
            diagnostic_build['command']['exit_code'] == 0 and diagnostic_source['parent_build_identity_sha256'] == parent_hash and
            diagnostic_source['parent_patch_sha256'] == source['patches']['combined.patch'] and
            diagnostic_source['parent_binary_sha256'] == parent_binary, 'Executor counterfactual provenance mismatch')
    require(diagnostic_source['source_files'].keys() == source['source_files'].keys() and
            [name for name, digest in diagnostic_source['source_files'].items() if digest != source['source_files'][name]] == ['Sources/SwiftJLS/CodecAPI.swift'],
            'Executor diagnostic changed more than the API signature file')
    original = (root / bridge['measured_candidate_build']).parent / 'codec/Sources/SwiftJLS/CodecAPI.swift'
    changed = executor / 'codec/Sources/SwiftJLS/CodecAPI.swift'
    old = b'@concurrent public func decode(_ data: Data, options: DecodeOptions = .init()) async throws -> DecodedImage {'
    new = b'public func decode(_ data: Data, options: DecodeOptions = .init()) throws -> DecodedImage {'
    original_bytes, changed_bytes = original.read_bytes(), changed.read_bytes()
    require(original_bytes.count(old) == 1 and changed_bytes.count(new) == 1 and original_bytes.replace(old, new) == changed_bytes,
            'Executor counterfactual no longer has the exact signature-only change')
    require(diagnostic_source['fixtures_tree'] == source['fixtures_tree'] and
            diagnostic_source['developer_dir'] == source['developer_dir'] and diagnostic_source['swift'] == source['swift'],
            'Executor diagnostic fixture/compiler mismatch')
    for name, digest in diagnostic_source['source_files'].items():
        require(sha(executor / 'codec' / name) == digest, 'Executor diagnostic source changed: ' + name)
    for name, digest in diagnostic_source['patches'].items():
        require(Path(name).name == name and sha(executor / name) == digest, 'Executor patch changed')
    require(sha(executor / 'consumer/Sources/Benchmark/main.swift') == diagnostic_source['consumer_sha256'] == bridge['consumer_sha256'] and
            sha(executor / 'consumer/Package.swift') == diagnostic_source['consumer_package_sha256'], 'Executor Consumer/package changed')
    require(sha(Path(diagnostic_build['binary'])) == diagnostic_build['binary_sha256'], 'Executor binary changed')
    preflight = diagnostic_build['preflight']
    require(preflight['all_six_passed'] is True and len(preflight['cases']) == 6 and
            {row['case'] for row in preflight['cases']} == {f'37x23-{pattern}-p{bits}' for bits in (12, 16) for pattern in ('flat', 'ramp', 'noise')} and
            all(row['exit_code'] == 0 and row['full_sample_verification'] == 'passed' for row in preflight['cases']),
            'Executor diagnostic correctness preflight incomplete')
    for reference, reference_binary in [('production', parent_binary), ('pinned', pinned_binary)]:
        def verify(plan, environment, completion, reference=reference, reference_binary=reference_binary):
            require(plan['reference'] == reference and plan['producers']['reference']['sha256'] == reference_binary and
                    plan['producers']['candidate']['sha256'] == diagnostic_build['binary_sha256'] and
                    plan['producers']['candidate']['patch_sha256'] == diagnostic_source['patches']['diagnostic.patch'] and
                    plan['producers']['candidate']['base_revision'] == source['base_source'], 'Executor comparison identity mismatch')
            for guards in (environment['source_guards'], completion['source_guards']):
                parent_guards(guards['parent_guards'])
                require(guards['candidate_build_identity_sha256'] == sha(identity_path) and
                        guards['candidate_source_hashes'] == diagnostic_source['source_files'] and
                        guards['candidate_patch_sha256'] == diagnostic_source['patches']['diagnostic.patch'] and
                        guards['candidate_binary_sha256'] == diagnostic_build['binary_sha256'] and
                        guards['exact_signature_only_difference'] is True and guards['diagnostic_only'] is True and guards['preflight'] == preflight,
                        'Executor diagnostic input guards differ')
        spec = dict(kind='diagnostic-short', name='executor-' + reference,
                    root=str((executor / 'timings' / ('short-' + reference)).relative_to(root)),
                    schedule=str((executor / 'schedules' / ('short-' + reference + '.json')).relative_to(root)),
                    runner=str((executor / 'run-comparisons.py').relative_to(root)))
        results.append(measurements.validate(spec, root, bridge, diagnostic_build, benchmark, {}, add, add_tree,
            diagnostic=dict(hashes={'reference': reference_binary, 'candidate': diagnostic_build['binary_sha256']}, validate_identity=verify,
                            scope='Signature-only synchronous owned-decode counterfactual; forbidden for production, not final qualification')))
    compact_metadata(executor, 'diagnostics/executor-counterfactual')
    add_tree(executor / 'preflight-correctness-only', 'diagnostics/executor-counterfactual/preflight-correctness-only')
    for name in ['codec/Sources/SwiftJLS/CodecAPI.swift', 'consumer/Sources/Benchmark/main.swift', 'consumer/Package.swift']:
        add(executor / name, 'diagnostics/executor-counterfactual/' + name)
    return results
