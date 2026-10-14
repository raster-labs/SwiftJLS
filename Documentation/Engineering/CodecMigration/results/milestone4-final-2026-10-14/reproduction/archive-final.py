#!/usr/bin/env python3
"""Archive frozen M4 evidence without manufacturing outcomes or changing history.

Run from the repository root after all final campaigns and analysis finish:
  python3 work/m4-final-2026-10-14/archive-final.py --check-only
  python3 work/m4-final-2026-10-14/archive-final.py

No builds, benchmarks, CI queries, compression, or source edits are performed.
Missing/inconsistent mandatory evidence aborts before publishing an archive.
Complete failed validation records are retained with their actual failed status.
An existing final archive is never overwritten. The 059d97a archive is untouched.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path(__file__).resolve().parent
DEST = ROOT / 'Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-14'
MANIFEST = DEST.with_suffix('.json')
KEYS = ['width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave']
OPERATIONS = ['encode', 'decode', 'prepare', 'prepare_encode']
MODES = ['debug', 'release', 'asan', 'tsan']


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def needed(path):
    require(path.is_file(), f'Missing mandatory evidence: {path}')
    return path


def read(path):
    return json.loads(needed(path).read_text())


def lines(path):
    rows = [json.loads(line) for line in needed(path).read_text().splitlines() if line.strip()]
    require(bool(rows), f'Empty evidence: {path}')
    return rows


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT, text=True).strip()


def xml_counts(path):
    cases = ET.parse(needed(path)).findall('.//testcase')
    require(bool(cases), f'No test cases in {path}')
    return dict(declarations=len(cases),
                failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
                skipped=sum(c.find('skipped') is not None for c in cases))


def labelled(rows, labels, description):
    require(isinstance(rows, list), f'{description}: expected a list')
    result = {row['label']: row for row in rows}
    require(len(result) == len(rows) and set(result) == set(labels), f'{description}: incomplete/duplicate labels')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only', action='store_true', help='Verify evidence without writing an archive')
    parser.add_argument('--workspace', type=Path, help='Compact workspace-accounting-evidence directory')
    args = parser.parse_args()
    sources = {}

    def add(path, relative=None):
        needed(path)
        key = str(relative if relative is not None else path.relative_to(SCRATCH))
        require(key not in sources or sources[key] == path, f'Duplicate archive path: {key}')
        sources[key] = path

    native_payload = read(SCRATCH / 'native-payload/manifest.json')
    checkpoint = native_payload['source_commit']
    require(git('rev-parse', checkpoint) == checkpoint, 'Native source checkpoint is not a full local commit')
    trees = {name.lower() + '_tree': git('rev-parse', checkpoint + ':' + name) for name in ['Sources', 'Tests']}
    require(native_payload['sources_tree'] == trees['sources_tree'], 'Native payload source tree mismatch')
    require(not git('diff', '--name-only', checkpoint, '--', 'Sources', 'Tests', 'Package.swift'),
            'Current source/tests/package differ from the measured checkpoint')
    require(not git('ls-files', '--others', '--exclude-standard', '--', 'Sources', 'Tests'),
            'Uncommitted source/test files are outside the measured checkpoint')

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
              'benchmark-value', 'cli-payload-value', 'cli-process-value']
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

    powered = SCRATCH / 'powered'
    campaign_commands = labelled(read(powered / 'commands.json'), ['scalar', 'colour'], 'Powered campaigns')
    conditions = lines(powered / 'conditions.jsonl')
    analysis = read(powered / 'combined-analysis.json')
    colour_selection = ROOT / 'work/m4-2026-10-14/colour-cases.json'
    colour_cases = read(colour_selection)
    expected_cases = {
        'scalar': {(width, height, bits, pattern, 1, 0, 0)
                   for width, height in [(37, 23), (512, 512), (2048, 2048), (4096, 3073)]
                   for bits in [12, 16] for pattern in ['flat', 'ramp', 'noise']},
        'colour': {tuple(row) for row in colour_cases},
    }
    require(len(colour_cases) == len(expected_cases['colour']) == 39, 'Invalid prescribed 39-case colour selection')
    add(colour_selection, 'reproduction/colour-cases.json')
    harness_hashes = {
        'consumer_sha256': sha(needed(ROOT / 'Scripts/Benchmark/Consumer.swift')),
        'runner_sha256': sha(needed(ROOT / 'Scripts/Benchmark/compare.py')),
    }
    performance = {}
    benchmark_hashes = None
    predecessor = None
    for kind in ['scalar', 'colour']:
        folder = powered / kind
        environment = read(folder / 'environment.json')
        successor = environment['successor_sha']
        require(successor['exit_code'] == 0 and successor['output'].strip() == checkpoint,
                f'{kind} benchmark used a different source checkpoint')
        require(all(environment[key] == value for key, value in harness_hashes.items()),
                f'{kind}: measured consumer/runner differs from archived reproduction')
        if kind == 'colour':
            require(environment['case_selection_sha256'] == sha(colour_selection),
                    'Colour selection differs from the measured selection file')
        if benchmark_hashes is None:
            benchmark_hashes = environment['binary_sha256']
            predecessor = environment['predecessor_sha']
        require(environment['binary_sha256'] == benchmark_hashes and environment['predecessor_sha'] == predecessor,
                'Benchmark binary/baseline changed between campaigns')
        selected = {tuple(row) for row in environment['selected_cases']}
        require(selected == expected_cases[kind] and len(selected) == len(environment['selected_cases']),
                f'{kind}: expected the exact prescribed {len(expected_cases[kind])}-case selection')
        groups = collections.defaultdict(list)
        for row in lines(folder / 'raw.jsonl'):
            groups[tuple(row[k] for k in KEYS)].append(row)
        require(set(groups) == selected, f'{kind}: raw results do not match selected cases')
        records = analysis[kind]
        require(not records['excluded_cases'] and records['complete_cases'] == len(selected), f'{kind}: incomplete analysis')
        analysed = {tuple(row[k] for k in KEYS): row for row in records['cases']}
        require(set(analysed) == selected and len(records['cases']) == len(selected),
                f'{kind}: analysed cases differ from selection or contain duplicates')
        for case, rows in groups.items():
            # This is the recorded compare.py protocol, not a claimed outcome.
            expected = {(block, label) for block in range(4) for label in ['predecessor', 'successor']}
            require(len(rows) == len(expected) and {(r['block'], r['label']) for r in rows} == expected,
                    f'{kind}/{case}: missing alternating process block')
            require(all(r['warmups'] == r['iterations'] == 5 for r in rows),
                    f'{kind}/{case}: each process block must use five warmups and five observations')
            for operation in OPERATIONS:
                medians = {}
                block_medians = {}
                for label in ['predecessor', 'successor']:
                    runs = [r for r in rows if r['label'] == label]
                    require(all(len(r[operation + '_seconds']) == 5 for r in runs),
                            f'{kind}/{case}: incomplete {operation} samples')
                    values = [v for r in runs for v in r[operation + '_seconds']]
                    require(all(math.isfinite(v) and v > 0 for v in values), 'Invalid timing sample')
                    medians[label] = statistics.median(values)
                    block_medians[label] = {r['block']: statistics.median(r[operation + '_seconds']) for r in runs}
                    recorded = analysed[case]['producers'][label][operation]
                    require(recorded['samples'] == len(values) and math.isclose(recorded['median_seconds'], medians[label], rel_tol=1e-12),
                            f'{kind}/{case}: analysis/raw sample disagreement')
                comparison = analysed[case]['comparisons'][operation]
                require(math.isclose(comparison['median_ratio'], medians['successor'] / medians['predecessor'], rel_tol=1e-12),
                        f'{kind}/{case}: analysis/raw ratio disagreement')
                ratios = [block_medians['successor'][block] / block_medians['predecessor'][block]
                          for block in range(4)]
                require(len(comparison['paired_block_ratios']) == 4 and
                        all(math.isclose(recorded, actual, rel_tol=1e-12)
                            for recorded, actual in zip(comparison['paired_block_ratios'], ratios)),
                        f'{kind}/{case}/{operation}: analysis/raw paired block ratio disagreement')
                require(comparison['all_blocks_over_5_percent'] is all(ratio > 1.05 for ratio in ratios),
                        f'{kind}/{case}/{operation}: incorrect repeat-regression flag')
        summary = read(folder / 'summary.json')
        require(len(summary) == len(selected) and {tuple(row[k] for k in KEYS) for row in summary} == selected,
                f'{kind}: incomplete/duplicate runner summary')
        for filename in ['environment.json', 'summary.json', 'raw.jsonl', 'power-end.json', 'load-end.json', 'thermal-end.json']:
            add(folder / filename)
        add(powered / (kind + '.log'))
        performance[kind] = dict(cases=len(selected), command_exit_code=campaign_commands[kind]['exit_code'],
            methodology=environment['methodology'], runner_performance_qualified=environment['performance_qualified'],
            repeat_regressions={op: sum(c['comparisons'][op]['all_blocks_over_5_percent'] for c in records['cases']) for op in OPERATIONS})
    for filename in ['commands.json', 'conditions.jsonl', 'combined-analysis.json']:
        add(powered / filename)
    disposition = read(powered / 'performance-disposition.json')
    require(disposition['source_checkpoint'] == checkpoint and disposition['predecessor_checkpoint'] == predecessor and
            disposition['binary_sha256'] == benchmark_hashes, 'Performance disposition source/binary mismatch')
    require(disposition['main_campaign_cases'] == sum(len(cases) for cases in expected_cases.values()) == 63,
            'Performance disposition has the wrong main-campaign case count')
    for kind in ['scalar', 'colour']:
        cases = disposition['measurements'][kind]['cases']
        require(len(cases) == len(expected_cases[kind]) and
                {tuple(row[key] for key in KEYS) for row in cases} == expected_cases[kind],
                f'{kind}: performance disposition case selection differs')
    for suffix in ['json', 'md']:
        add(powered / ('performance-disposition.' + suffix))
    size_report_path = SCRATCH / 'diagnostics/rgb-size/summary.json'
    if size_report_path.is_file():
        size_report = read(size_report_path)
        require(size_report['source_checkpoint'] == size_report['reference_size_source_checkpoint'] == checkpoint and
                size_report['predecessor_checkpoint'] == predecessor and size_report['binary_sha256'] == benchmark_hashes,
                'RGB size diagnostic source/binary mismatch')
        size_cases = {tuple(row[key] for key in KEYS): row for row in size_report['cases']}
        expected_sizes = {tuple(row[key] for key in KEYS): row for row in disposition['measurements']['colour']['cases']
                          if row['encoded_size']['ratio'] > 1.01}
        require(size_report['complete'] is True and
                size_report['profile_count'] == len(size_report['cases']) == len(size_cases) == len(expected_sizes) == 13 and
                set(size_cases) == set(expected_sizes), 'RGB size diagnostic does not cover all 13 final outliers')
        require(size_report['parser_controls_passed'] is True and size_report['all_header_only_differences_verified'] is True and
                size_report['successful_cross_decodes'] == 26, 'Incomplete RGB size diagnostic checks')
        for case, row in size_cases.items():
            require(all(row[key] is True for key in ['matches_recorded_benchmark_sizes', 'exact_signalling_segments',
                    'entropy_identical', 'normalized_streams_identical', 'header_only_difference_verified']) and
                    row['cross_decodes'] == {'predecessor_decodes_successor': True, 'successor_decodes_predecessor': True} and
                    all(row['producers'][label]['bytes'] == expected_sizes[case]['encoded_size']['bytes'][label]
                        for label in ['predecessor', 'successor']), f'{case}: RGB size diagnostic verification differs')
        require(len(size_report['commands']) == 52 and all(row['exit_code'] == 0 for row in size_report['commands']),
                'RGB size diagnostic commands are incomplete or failed')
        require(size_report['script_sha256'] == sha(needed(SCRATCH / 'check-rgb-size-outliers.py')),
                'RGB size diagnostic script differs from archived reproduction')

    scripts = ['run-tests.py', 'qualify.py', 'prepare-native.py', 'apple-build-value.py',
               'apple-runtime-value.py', 'apple-resource-value.py', 'run-powered.py', 'analyse-powered.py',
               'replay-workspace.py', 'compare-small-steady.py', 'compare-small-long.py',
               'compare-small-worker.py', 'compare-small-deep-warm.py', 'performance-disposition.py', 'check-rgb-size-outliers.py',
               'small-flat-cases.json', 'small-cases.json', 'archive-final.py']
    for name in scripts:
        add(SCRATCH / name, 'reproduction/' + name)
    add(SCRATCH / 'native-payload/run-native.py', 'reproduction/run-native.py')
    for relative in ['Scripts/Benchmark/compare.py', 'Scripts/Benchmark/Consumer.swift',
                     'Scripts/test-cli.py', 'Scripts/test-payload-cli.py']:
        add(ROOT / relative, 'reproduction/' + relative)
    for name in ['qualify.log', 'tests-driver.log', 'native-ssh.log', 'native-vm.log', 'powered.log']:
        if (SCRATCH / name).is_file():
            add(SCRATCH / name)

    for path in sorted((SCRATCH / 'diagnostics').rglob('*')):
        if path.is_file():
            add(path)

    workspace = args.workspace
    if workspace is None:
        candidates = [SCRATCH / 'workspace-accounting-evidence',
                      ROOT / 'work/m4-closeout-2026-10-14/workspace-accounting-evidence']
        workspace = next((p for p in candidates if p.is_dir()), None)
    require(workspace is not None, 'The final 89-operation workspace evidence is mandatory')
    workspace = workspace.resolve()
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

    provenance = dict(source_commit=checkpoint, **trees,
        native_payload_manifest_sha256=sha(SCRATCH / 'native-payload/manifest.json'),
        native_payload_files={k: v for k, v in native_payload['files'].items()
                              if not k.startswith('repo/') and '/Resources/' not in k and '/_CodeSignature/' not in k},
        benchmark_binary_sha256=benchmark_hashes, source_files={})
    for name in git('ls-tree', '-r', '--name-only', checkpoint, '--', 'Sources', 'Tests', 'Package.swift', 'VERSION').splitlines():
        if name.startswith('Tests/') and not name.endswith('.swift'):
            continue  # The Tests Git tree identifies the complete fixture corpus.
        provenance['source_files'][name] = dict(git_blob=git('rev-parse', checkpoint + ':' + name), sha256=sha(ROOT / name))

    software_passed = (all(t['exit_code'] == t['failures'] == t['skipped'] == 0 for t in test_summary.values())
        and all(r['exit_code'] == 0 for r in qualification.values())
        and all(r['exit_code'] == 0 for r in builds)
        and all(r['all_commands_succeeded'] for r in simulator_summary)
        and all(r['exit_code'] == 0 for r in resource_commands)
        and process['status'] == 'passed' and native_process['status'] == 'passed'
        and native['success'] and native['exact_26_0_native_arm64']
        and all(c['exit_code'] == 0 for c in native['commands'])
        and all(c['failures'] == c['skipped'] == 0 for c in native_counts.values()))
    manifest = dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        production_checkpoint=checkpoint, **trees, predecessor=predecessor,
        archive_directory=DEST.name, software_validation_passed=bool(software_passed),
        local_tests=test_summary, cli=dict(payload_checks=len(payload), process_checks=process['checks'], status=process['status']),
        apple_simulators=simulator_summary, apple_resources=resource_summary,
        native_execution={k: v for k, v in native.items() if k != 'commands'},
        native_cli=dict(payload_checks=len(native_payload_cli), process_checks=native_process['checks'], status=native_process['status']),
        native_resource_frames=sum(r['frames'] for r in native_resources),
        performance=performance, condition_observations=len(conditions),
        performance_acceptance='Not determined by the archiver; preserve all case ratios and owner acceptance requirements.',
        workspace_included=workspace_summary is not None,
        workspace=workspace_summary,
        limitations=['Physical device testing remains pending; Milestone 5 remains deferred.',
                     'The owner verifies CI and merges; this archive makes no GitHub check-status claim.',
                     'Native OS 26.0 evidence is hardware-virtualised arm64 execution, not physical-device testing.',
                     'Workspace replay is required to match the final production checkpoint; its measured scope remains finite.',
                     'Requested heap, stack, allocator overhead and RSS remain distinct; unknown is not zero.'])
    inventory = {key: dict(bytes=path.stat().st_size, sha256=sha(path),
        source=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)) for key, path in sorted(sources.items())}
    require(inventory['reproduction/Scripts/Benchmark/Consumer.swift']['sha256'] == harness_hashes['consumer_sha256'] and
            inventory['reproduction/Scripts/Benchmark/compare.py']['sha256'] == harness_hashes['runner_sha256'],
            'Measured benchmark consumer/runner changed while preparing the archive')
    provenance_bytes = (json.dumps(provenance, indent=2) + '\n').encode()
    inventory['provenance.json'] = dict(bytes=len(provenance_bytes), sha256=hashlib.sha256(provenance_bytes).hexdigest(), source='Generated checkpoint and native payload provenance')
    manifest['files'] = inventory
    print(json.dumps(dict(checkpoint=checkpoint, local_declarations={k: v['declarations'] for k, v in test_summary.items()},
        software_validation_passed=bool(software_passed), performance_cases={k: v['cases'] for k, v in performance.items()},
        workspace_checkpoint=workspace_summary['source_checkpoint'] if workspace_summary else None,
        files=len(inventory), bytes=sum(v['bytes'] for v in inventory.values()), check_only=args.check_only)))
    if args.check_only:
        return
    require(not DEST.exists() and not MANIFEST.exists(), 'Final archive already exists; refusing to overwrite')
    DEST.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.milestone4-final-', dir=DEST.parent))
    try:
        for key, path in sources.items():
            target = stage / key
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            require(sha(target) == inventory[key]['sha256'], f'Evidence changed while copying: {path}')
        (stage / 'provenance.json').write_bytes(provenance_bytes)
        manifest_bytes = (json.dumps(manifest, indent=2) + '\n').encode()
        # Exclusive creation prevents accidental replacement of any existing manifest.
        with MANIFEST.open('xb') as stream:
            stream.write(manifest_bytes)
        stage.rename(DEST)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(f'Archived {DEST.relative_to(ROOT)} and {MANIFEST.relative_to(ROOT)}')


if __name__ == '__main__':
    main()
