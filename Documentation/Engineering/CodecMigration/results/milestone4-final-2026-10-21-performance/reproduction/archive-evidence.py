"""Fresh software, workspace and mutation adapters; imported by archive-final.py."""
from pathlib import Path
import collections
import gzip
import hashlib
import json
import xml.etree.ElementTree as ET
ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path(__file__).resolve().parent
MODES = ['debug', 'release', 'asan', 'tsan']

def require(condition, message):
    if not condition: raise ValueError(message)
def needed(path):
    require(path.is_file(), f'Missing mandatory evidence: {path}')
    return path
def read(path): return json.loads(needed(path).read_text())
def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''): digest.update(chunk)
    return digest.hexdigest()
def lines(path):
    with needed(path).open() as stream: rows = [json.loads(line) for line in stream if line.strip()]
    require(rows, f'Empty evidence: {path}')
    return rows
def xml_counts(path):
    cases = ET.parse(needed(path)).findall('.//testcase')
    require(cases, f'No test declarations: {path}')
    return dict(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
def labelled(rows, labels, description):
    require(isinstance(rows,list), description + ': expected list')
    result = {row['label']:row for row in rows}
    require(len(result)==len(rows) and set(result)==set(labels), description + ': missing/duplicate labels')
    return result

def validate_software(checkpoint, add):
    native_payload = read(SCRATCH / 'native-payload/manifest.json')
    tests = labelled(read(SCRATCH / 'tests/results.json'), MODES, 'Local tests')
    test_summary = {}
    for mode, record in tests.items():
        counts = xml_counts(SCRATCH / f'tests/{mode}.xml')
        require(all(record.get(k) == v for k, v in counts.items()), f'Local {mode} result/XML mismatch')
        test_summary[mode] = dict(counts, exit_code=record['exit_code'], seconds=record['seconds'],
                                 developer_dir=record['developer_dir'])
        add(SCRATCH / f'tests/{mode}.xml')
        add(SCRATCH / f'tests/{mode}.log')
    require(len({r['declarations'] for r in test_summary.values()}) == 1, 'Local suites used different test counts')
    add(SCRATCH / 'tests/results.json')

    labels = ['apple-build-value', 'apple-runtime-value', 'apple-resource-value',
              'native-AppleRuntimeConsumer-value', 'native-ResourceStress-value',
              'benchmark-reuse-value', 'host-AppleRuntimeConsumer-value', 'host-ResourceStress-value',
              'cli-payload-value', 'cli-process-value']
    qualification = labelled(read(SCRATCH / 'value-qualification-commands.json'), labels, 'Qualification commands')
    add(SCRATCH / 'value-qualification-commands.json')
    for label in labels:
        add(SCRATCH / (label + '.log'))
    payload = read(SCRATCH / 'cli-payload-value.json')
    require(isinstance(payload, list) and payload, 'Empty local CLI payload record')
    process = read(SCRATCH / 'cli-process-value/report.json')
    require(isinstance(process.get('checks'), int) and process['checks'] > 0, 'Missing local CLI process count')
    require(process['binary_sha256'] == native_payload['files']['swiftjls-cli'], 'CLI/native binary mismatch')
    add(SCRATCH / 'cli-payload-value.json')
    for path in sorted((SCRATCH / 'cli-process-value').rglob('*')):
        if path.is_file():
            add(path)

    builds = read(SCRATCH / 'apple-value/build-results.json')
    require(isinstance(builds, list) and builds, 'Empty Apple build commands')
    simulators = sorted((SCRATCH / 'apple-value').glob('*-26.0-*.json'))
    require(collections.Counter(p.name.split('-26.0-')[0] for p in simulators) ==
            {'iOS': 2, 'tvOS': 1, 'visionOS': 1, 'watchOS': 1}, 'Missing required exact-26.0 simulator profiles')
    simulator_summary = []
    for path in simulators:
        record = read(path)
        require(record['runtime']['version'] == '26.0', f'Wrong runtime in {path}')
        require(any('spawn' in c['command'] for c in record['commands']), f'Missing runtime execution in {path}')
        simulator_summary.append(dict(evidence=str(path.relative_to(SCRATCH)),
            runtime=record['runtime']['version'], device=record['device']['name'],
            all_commands_succeeded=all(c['exit_code'] == 0 for c in record['commands'])))
    for path in sorted((SCRATCH / 'apple-value').rglob('*')):
        if path.is_file() and (path.suffix == '.log' or path.suffix == '.json' and '.abi.' not in path.name):
            add(path)
    resource_commands = read(SCRATCH / 'resource26-value/commands.json')
    workloads = [r for r in resource_commands if r['label'].endswith('resource workload')]
    require(len(workloads) == 4, 'Missing non-Watch simulator resource workloads')
    resource_summary = []
    for record in workloads:
        output = json.loads(record['stdout'])
        require(bool(output), f'Empty resource workload: {record["label"]}')
        resource_summary.append(dict(label=record['label'], exit_code=record['exit_code'],
            frames=sum(r['frames'] for r in output), rows=output))
    add(SCRATCH / 'resource26-value/commands.json')

    native = read(SCRATCH / 'native-results/results.json')
    require(native['source'] == checkpoint, 'Native result source checkpoint mismatch')
    native_counts = {'release': xml_counts(SCRATCH / 'native-results/unit.xml')}
    for mode in ['debug', 'asan', 'tsan']:
        native_counts[mode] = xml_counts(SCRATCH / f'native-results/unit-{mode}.xml')
    for mode, counts in native_counts.items():
        reported = native['tests'] if mode == 'release' else native['extra_tests'][mode]
        require(reported == counts, f'Native {mode} result/XML mismatch')
        require(counts['declarations'] == test_summary[mode]['declarations'], f'Local/native {mode} count mismatch')
    native_payload_cli = read(SCRATCH / 'native-results/cli-payload.json')
    native_process = read(SCRATCH / 'native-results/cli-process/report.json')
    native_resources = json.loads(needed(SCRATCH / 'native-results/resources.stdout').read_text())
    require(bool(native_payload_cli) and native_process['checks'] > 0 and native_resources, 'Incomplete native consumer evidence')
    needed(SCRATCH / 'native-results/consumer.stdout')
    needed(SCRATCH / 'native-results/os.stdout')
    needed(SCRATCH / 'native-results/architecture.stdout')
    require(native_process['binary_sha256'] == process['binary_sha256'], 'Native CLI executable mismatch')
    for path in sorted((SCRATCH / 'native-results').rglob('*')):
        if path.is_file():
            add(path)

    expected_targets = {'arm64-apple-ios26.0-simulator', 'arm64-apple-tvos26.0-simulator', 'arm64-apple-xros26.0-simulator', 'arm64-apple-watchos26.0-simulator', 'arm64_32-apple-watchos26.0'}
    actual_targets = {row['command'][row['command'].index('-target') + 1] for row in builds if '-target' in row['command']}
    require(actual_targets == expected_targets, 'Incomplete Apple target matrix')
    require(collections.Counter(row['command'][row['command'].index('-target') + 1] for row in builds if '-target' in row['command']) ==
            {target: (1 if target.startswith('arm64_32-') else 2) for target in expected_targets} and
            sum(row['command'][0] == 'codesign' for row in builds) == 8, 'Incomplete library/consumer/signing commands')
    require(all(row['exit_code'] == 0 for row in builds + resource_commands + list(qualification.values())), 'Qualification/build/resource command failed')
    require(all(row['all_commands_succeeded'] for row in simulator_summary), 'Simulator execution failed')
    require(all(row['exit_code'] == row['failures'] == row['skipped'] == 0 for row in test_summary.values()), 'Host test failure')
    require(native['source'] == checkpoint and native['success'] is True and native['exact_26_0_native_arm64'] is True and all(row['exit_code'] == 0 for row in native['commands']), 'Native validation failed')
    require(all(row['failures'] == row['skipped'] == 0 for row in native_counts.values()), 'Native test failure')
    require(process['status'] == native_process['status'] == 'passed', 'CLI process validation failed')
    for name in ['tests/source.json', 'tests/toolchain.json', 'qualification-source.json', 'consumer-builds.json', 'benchmark-reuse.json', 'benchmark-build.json', 'native-driver-commands.json']:
        add(SCRATCH / name)
    add(SCRATCH / 'native-payload/manifest.json', 'native-payload-manifest.json')
    return dict(passed=True, local_tests=test_summary, native_tests=native_counts, cli=dict(payload_checks=len(payload),process_checks=process['checks']), native_cli=dict(payload_checks=len(native_payload_cli),process_checks=native_process['checks']), apple_simulators=simulator_summary, apple_resources=resource_summary, native_resource_frames=sum(row['frames'] for row in native_resources), native_execution={k:v for k,v in native.items() if k!='commands'})

def validate_mutation(checkpoint, add):
    mutation_root = SCRATCH / 'mutation'
    mutation_source = read(mutation_root / 'source.json')
    require(mutation_source['revision'] == mutation_source['run_head_sha'] == checkpoint and mutation_source['run_id'] and
            mutation_source['run_url'] and mutation_source['artifact_hashes'], 'Mutation run provenance mismatch')
    run = read(mutation_root / 'run.json')
    require(run['headSha'] == checkpoint and run['databaseId'] == mutation_source['run_id'] and
            run['url'] == mutation_source['run_url'] and run['status'] == 'completed' and run['conclusion'] == 'success' and
            len(run['jobs']) == 3 and all(row['conclusion'] == 'success' for row in run['jobs']), 'Mutation measurement-run completion differs')
    require(set(mutation_source['artifact_hashes']) == set(mutation_source['entries']) == {'owned', 'into', 'inspect'} and
            mutation_source['status'] == 'passed', 'Mutation entry provenance incomplete')
    mutation_results = {}
    for entry in ['owned', 'into', 'inspect']:
        folder = mutation_root / entry
        outcome = read(folder / 'campaign-result.json')
        events = lines(folder / 'campaign.jsonl')
        final = events[-1]
        require(outcome['exit_code'] == 0 and outcome['failure'] is None and
                outcome['wall_seconds'] >= 3600 and final.get('complete') is True and
                final['seconds'] >= 3600 and final['entry'] == entry and final['iterations'] > 0,
                f'Incomplete/failed final mutation campaign: {entry}')
        require(final['accepted'] + final['rejected'] == final['iterations'] and
                mutation_source['entries'][entry]['supervisor'] == outcome and mutation_source['entries'][entry]['final'] == final,
                f'Mutation summary/counts differ: {entry}')
        hashes = mutation_source['artifact_hashes'][entry]
        require(hashes == mutation_source['entries'][entry]['files'] and
                set(hashes) == {path.name for path in folder.iterdir() if path.is_file()}, 'Mutation downloaded-file inventory differs')
        for name, evidence in hashes.items():
            require(Path(name).name == name and needed(folder / name).stat().st_size == evidence['bytes'] and
                    sha(folder / name) == evidence['sha256'], 'Mutation artifact content changed: ' + entry + '/' + name)
        require(needed(folder / 'campaign-stderr.log').stat().st_size == 0,
                f'Nonempty mutation sanitizer stderr: {entry}')
        mutation_results[entry] = dict(outcome=outcome, final=final)
    for path in sorted(mutation_root.rglob('*')):
        if path.is_file():
            require(path.stat().st_size < 20 * 1024 * 1024, f'Mutation evidence needs compact packaging: {path}')
            add(path)
    return dict(source=mutation_source, results=mutation_results)

def validate_workspace(checkpoint, add):
    workspace = SCRATCH / 'workspace-accounting-evidence'
    workspace_summary = read(workspace / 'summary.json')
    ledger = read(workspace / 'manifest.json')
    matrix = read(workspace / 'matrix.json')
    require(ledger['source_checkpoint'] == workspace_summary['source_checkpoint'] == matrix['revision'] == checkpoint,
            'Final workspace checkpoint mismatch')
    require(ledger['binary_sha256'] == workspace_summary['binary_sha256'], 'Workspace binary identity mismatch')
    workspace_operations = ['encode', 'owned', 'into', 'inspect']
    expected_workspace = {
        f'{size}-{components}-{near}-{operation}'
        for size in [17, 512] for components in [1, 3] for near in [0, 3] for operation in workspace_operations
    } | {
        f'{profile}-{components}-{near}-{operation}'
        for profile, components, near in [('line', 3, 0), ('line', 3, 3), ('planar', 3, 0), ('planar', 3, 3),
                ('p16', 1, 0), ('p16', 3, 3), ('preset', 1, 3), ('preset', 3, 0),
                ('restart', 3, 3), ('hp1', 3, 0), ('hp2', 3, 0), ('hp3', 3, 0)]
        for operation in workspace_operations
    } | {
        f'{fixture}-{operation}'
        for fixture in ['subsampled-zero-n0', 'map-p16-c3-i0-w1-n0', 'extended-p12-65537x2']
        for operation in ['owned', 'into', 'inspect']
    }
    require(workspace_summary['profile_count'] == len(workspace_summary['rows']) == len(matrix['cases']) == 89 and
            {row['case'] for row in workspace_summary['rows']} == {row[0] for row in matrix['cases']} == expected_workspace,
            'Missing/duplicate cases in the final 89-operation workspace matrix')
    require(all(workspace_summary[key] is True for key in ['all_consumers_verified', 'all_recorded_commands_succeeded',
            'all_ledgers_reconcile', 'all_codec_heap_attributed']), 'Incomplete final workspace replay')
    require(workspace_summary['pure_algorithm_workspace_complete'] is False and
            all(workspace_summary[key] is None for key in ['stack_peak_bytes', 'allocator_overhead_bytes', 'production_peakWorkspaceBytes']),
            'Finite workspace profile evidence was relabelled as a universal total')
    require(all(row['observation']['samples_verified'] is True and row['codec_heap_attribution_complete'] is True
                for row in workspace_summary['rows']), 'Incomplete workspace case verification/attribution')
    require(collections.Counter(row['observation']['operation'] for row in workspace_summary['rows']) ==
            workspace_summary['operation_counts'] == {'encode': 20, 'owned': 23, 'into': 23, 'inspect': 23},
            'Workspace operation counts differ')
    required_workspace_files = {'summary.json', 'matrix.json', 'measure-operation.py', 'replay-workspace.py', 'classifier-controls.txt'} | {
        f'{case}/{name}' for case in expected_workspace
        for name in ['allocations.gz', 'commands.json', 'consumer.stdout', 'operation.json.gz', 'summary.json']
    }
    ledger_paths = {entry['path'] for entry in ledger['files']}
    require(len(ledger_paths) == len(ledger['files']) and required_workspace_files <= ledger_paths,
            'Final workspace manifest omits required case evidence or duplicates paths')
    require(sha(needed(workspace / 'measure-operation.py')) == workspace_summary['classifier_sha256'],
            'Workspace classifier identity mismatch')
    for entry in ledger['files']:
        path = (workspace / entry['path']).resolve()
        require(path.is_relative_to(workspace), 'Workspace manifest path escapes its directory')
        require(needed(path).stat().st_size == entry['bytes'] and sha(path) == entry['sha256'], f'Workspace hash mismatch: {path}')
        add(path, 'workspace/' + entry['path'])
    add(workspace / 'summary.json', 'workspace/summary.json')
    add(workspace / 'manifest.json', 'workspace/manifest.json')
    workspace_run = read(SCRATCH / 'workspace-measurement-run.json')
    require(workspace_run['headSha'] == checkpoint and workspace_run['status'] == 'completed' and workspace_run['conclusion'] == 'success', 'Workspace measurement run is incomplete or mismatched')
    require(sum(row['owned_pixel_allocation_calls'] == 1 and row['observation']['operation'] == 'owned' for row in workspace_summary['rows']) == 23 and sum(row['owned_pixel_allocation_calls'] == 0 for row in workspace_summary['rows']) == 66, 'Owned-pixel allocation controls differ')
    add(SCRATCH / 'workspace-measurement-run.json')
    artifact_root = SCRATCH / 'workspace-artifact'
    artifact, download, query = (read(artifact_root / name) for name in
        ['artifact-metadata.json', 'download.json', 'artifact-metadata-command.json'])
    require(query['exit_code'] == download['exit_code'] == 0 and artifact['workflow_run']['id'] == workspace_run['databaseId'] and
            artifact['workflow_run']['head_sha'] == download['revision'] == checkpoint and download['run'] == workspace_run['url'] and
            artifact['id'] == download['artifact_id'] and artifact['digest'] == 'sha256:' + download['archive_sha256'] and
            artifact['size_in_bytes'] == download['archive_bytes'], 'Workspace artifact download/source provenance differs')
    for name in ['artifact-metadata.json', 'download.json', 'artifact-metadata-command.json']:
        add(artifact_root / name, 'workspace-artifact/' + name)
    add(SCRATCH / 'workspace-replay.log')

    comparison_path = SCRATCH / 'workspace-comparison-bee.json'
    comparison = read(comparison_path)
    historical = ROOT / 'Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21'
    historical_manifest = read(historical.with_suffix('.json'))
    before_summary_path = historical / 'workspace/summary.json'
    before_summary = read(before_summary_path)
    require(comparison['before_source'] == before_summary['source_checkpoint'] and comparison['after_source'] == checkpoint and
            comparison['before_summary_sha256'] == sha(before_summary_path) == historical_manifest['files']['workspace/summary.json']['sha256'] and
            comparison['after_summary_sha256'] == sha(workspace / 'summary.json') and comparison['profiles'] == len(comparison['rows']) == 89 and
            {row['case'] for row in comparison['rows']} == expected_workspace, 'Workspace before/after comparison provenance differs')
    for row in comparison['rows']:
        name = row['case']
        before_path = historical / 'workspace' / name / 'operation.json.gz'
        require(sha(before_path) == historical_manifest['files']['workspace/' + name + '/operation.json.gz']['sha256'],
                'Historical comparison ledger changed: ' + name)
        with gzip.open(before_path, 'rt') as stream: before = json.load(stream)
        with gzip.open(workspace / name / 'operation.json.gz', 'rt') as stream: after = json.load(stream)
        for label, observed in [('before', before), ('after', after)]:
            require(all(value == observed[key] for key, value in row[label].items()), 'Workspace comparison total differs: ' + name)
        require(row['delta'] == {key: row['after'][key] - row['before'][key] for key in row['before']},
                'Workspace comparison total delta differs: ' + name)
        require(set(row['groups']) == set(before['groups']) | set(after['groups']), 'Workspace comparison group inventory differs: ' + name)
        for group, values in row['groups'].items():
            for label, observed in [('before', before), ('after', after)]:
                require(all(value == observed['groups'].get(group, {}).get(key, 0) for key, value in values[label].items()),
                        'Workspace comparison group differs: ' + name + '/' + group)
            require(values['delta'] == {key: values['after'][key] - values['before'][key] for key in values['before']},
                    'Workspace comparison group delta differs: ' + name + '/' + group)
    add(comparison_path)
    supplemental = SCRATCH / 'workspace-native-descriptors.json'
    if supplemental.is_file():
        details=read(supplemental)
        require(details['source_checkpoint'] == checkpoint and details['binary_sha256'] == workspace_summary['binary_sha256'] and details['classifier_sha256'] == workspace_summary['classifier_sha256'], 'Supplemental workspace identity mismatch')
        add(supplemental)
    require(ledger_paths == {str(path.relative_to(workspace)) for path in workspace.rglob('*') if path.is_file() and path.name != 'manifest.json'}, 'Workspace inventory differs from its manifest')
    return workspace_summary


def validate_size(checkpoint, benchmark, performance, add, add_tree):
    """Validate the retained44-byte signalling proof without running a decoder.

    Exports and cross-decoder commands used frozen original-Consumer binaries.
    This proof is correctness-only; neither independent-oracle nor timing
    qualification is inferred from those incidental command outputs.
    """
    folder = SCRATCH / 'size-validation'
    report = read(folder / 'summary.json')
    check = read(folder / 'independent-check.json')
    command = read(folder / 'command.json')
    case = report['case']
    require(case == dict(id='4096x3073-p12-flat-c3-n0-i2', width=4096, height=3073, bits=12,
                        pattern='flat', components=3, near=0, interleave=2), 'Size proof case differs')
    larger = [row for campaign in performance if campaign['kind'] == 'larger' for row in campaign['cases'] if row['case'] == case]
    require(len(larger) == 1, 'Size proof is not a selected measured larger case')
    require(report['source_checkpoint'] == checkpoint and report['predecessor_checkpoint'] == benchmark['predecessor_commit'] and
            report['binary_sha256'] == benchmark['binary_sha256'] and report['consumer_sha256'] == benchmark['consumer_sha256'] and
            report['build_record_sha256'] == sha(SCRATCH / 'benchmark-build.json') and
            report['measured_summary_sha256'] == sha(SCRATCH / 'larger-guard-summary.json'), 'Size proof source/build/measurement differs')
    require(report['independent_oracle_run'] is False and command['exit_code'] == 0 and
            all(report[key] is True for key in ['complete', 'parser_controls_passed', 'start_source_binary_guards_passed',
                'end_source_binary_guards_passed', 'matches_recorded_benchmark_sizes', 'exact_signalling_segments',
                'entropy_identical', 'header_normalised_streams_identical', 'header_only_difference_verified']),
            'Size proof incomplete or incorrectly scoped')
    require(sha(folder / 'Consumer.swift') == report['consumer_sha256'], 'Size proof common Consumer changed')
    require(set(report['scripts']) == {'verify.py', 'rgb-size-helper.py'} and
            report['binaries'] == {label: str((ROOT / value).resolve()) for label, value in benchmark['binaries'].items()},
            'Size proof script/binary inventory differs')
    for name, digest in report['scripts'].items():
        require(Path(name).name == name and sha(folder / name) == digest, 'Size proof script changed')
    streams = {label: needed(folder / (label + '.jls')).read_bytes() for label in ['predecessor', 'successor']}
    expected_spiff = (bytes.fromhex('ffe8002053504946460002000003') + case['height'].to_bytes(4, 'big') +
        case['width'].to_bytes(4, 'big') + bytes([10, case['bits'], 6, 0]) + (1).to_bytes(4, 'big') * 2)
    directory_end = bytes.fromhex('ffe8000800000001ffd8')
    before, after = streams['predecessor'], streams['successor']
    require(after[2:36] == expected_spiff and after[36:46] == directory_end and
            after[:2] + after[46:] == before and len(after) - len(before) == report['delta_bytes'] == 44 and
            report['signalling_segment_bytes'] == [34, 10], 'Direct APP8 range removal does not prove44-byte difference')
    sof = (bytes.fromhex('fff70011') + bytes([case['bits']]) + case['height'].to_bytes(2, 'big') +
        case['width'].to_bytes(2, 'big') + bytes.fromhex('03011100021100031100'))
    sos = bytes.fromhex('ffda000c03010002000300000200')
    prefix = b'\xff\xd8' + sof + sos
    require(before.startswith(prefix) and before.endswith(b'\xff\xd9') and after.endswith(b'\xff\xd9'),
            'Size proof frame/scan geometry differs')
    entropy = before[len(prefix):-2]
    require(len(entropy) == 2078 and after[len(prefix) + 44:-2] == entropy and
            report['normalised_sha256'] == hashlib.sha256(before).hexdigest(), 'Size proof entropy/normalised bytes differ')
    for label, producer in [('predecessor', 'reference'), ('successor', 'candidate')]:
        data, recorded = streams[label], report['producers'][label]
        require(len(data) == recorded['bytes'] == larger[0]['encoded_bytes']['median'][producer] and
                hashlib.sha256(data).hexdigest() == recorded['sha256'] and recorded['full_consumer_sample_check'] is True and
                recorded['entropy_bytes'] == len(entropy) and recorded['entropy_sha256'] == hashlib.sha256(entropy).hexdigest(),
                'Size proof stream/entropy identity mismatch: ' + label)
        shift = 44 if label == 'successor' else 0
        framing = [(0, 2)] + ([(2, 34), (36, 10)] if shift else []) + [(2 + shift, 19), (21 + shift, 14), (len(data) - 2, 2)]
        require(recorded['markers'] == [dict(marker=data[offset:offset + 2].hex().upper(), offset=offset, bytes=size,
            raw_hex=data[offset:offset + size].hex(), payload_hex=data[offset + 4:offset + size].hex() if size > 2 else '')
            for offset, size in framing], 'Size proof marker table differs from retained bytes')
    expected_commands = [('predecessor', 'export'), ('successor', 'export'),
                         ('predecessor', 'cross-decode'), ('successor', 'cross-decode')]
    require([(row['producer'], row['action']) for row in report['commands']] == expected_commands, 'Size proof command matrix incomplete')
    for row in report['commands']:
        label, action = row['producer'], row['action']
        expected = [str((ROOT / benchmark['binaries'][label]).resolve()), '4096', '3073', '12', 'flat', '0', '1', label, '3', '0', '2']
        require(row['command'] == expected and row['exit_code'] == 0 and row['developer_dir'] == benchmark['developer_dir'],
                'Size proof command differs from frozen original Consumer')
        target_label = label if action == 'export' else 'successor' if label == 'predecessor' else 'predecessor'
        variable = 'SWIFTJLS_BENCHMARK_EXPORT' if action == 'export' else 'SWIFTJLS_BENCHMARK_DECODE'
        require(row['environment'] == {variable: str(folder / (target_label + '.jls'))}, 'Size proof export/cross-decode direction differs')
        for stream in ['stdout', 'stderr']:
            evidence = row[stream]; path = folder / evidence['path']
            require(Path(evidence['path']).name == evidence['path'] and needed(path).stat().st_size == evidence['bytes'] and
                    sha(path) == evidence['sha256'], 'Size proof command output changed')
        require(row['stderr']['bytes'] == 0, 'Size proof command has stderr')
        output = read(folder / row['stdout']['path'])
        require(all(output[key] == value for key, value in case.items() if key != 'id') and output['label'] == label and
                output['warmups'] == 0 and output['iterations'] == 1 and output['end_to_end'] is False and
                output['encoded_bytes'] == len(streams[label]), 'Size proof Consumer profile differs')
    count = case['width'] * case['height'] * case['components']
    require(report['required_samples_per_decode'] == count and report['cross_decodes'] == {
        'predecessor_decodes_successor': dict(passed=True, samples=count, maximum_error=0),
        'successor_decodes_predecessor': dict(passed=True, samples=count, maximum_error=0)}, 'Size proof sample verification incomplete')
    require(check == dict(all_four_command_exits_zero=True, direct_two_range_removal_matches_complete_predecessor=True,
        removed_segment_offsets=[2, 36], removed_segment_bytes=[34, 10], all_command_stdout_stderr_hashes_match=True,
        all_stream_hashes_match=True), 'Independent byte comparison receipt differs')
    add_tree(folder, 'size-validation')
    return dict(case=case, delta_bytes=44, entropy_bytes=len(entropy), samples_per_cross_decode=count,
                maximum_cross_decode_error=0, direct_byte_removal_verified=True,
                independent_oracle_run=False, performance_qualification=False,
                scope='Correctness-only retained exports and bidirectional Swift cross-decodes')
