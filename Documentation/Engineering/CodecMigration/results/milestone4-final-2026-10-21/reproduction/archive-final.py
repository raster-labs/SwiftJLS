#!/usr/bin/env python3
"""Archive frozen M4 evidence without manufacturing outcomes or changing history.

Run from the repository root after all final campaigns and analysis finish:
  python3 work/m4-final-2026-10-21/archive-final.py --check-only
  python3 work/m4-final-2026-10-21/archive-final.py

No builds, benchmarks, CI queries, compression, or source edits are performed.
Missing/inconsistent mandatory evidence aborts before publishing an archive.
Complete failed validation records are retained with their actual failed status.
An existing final archive is never overwritten. The 14 October archive is linked as history and is never copied or overwritten.
"""
from __future__ import annotations

import argparse
import collections
import datetime
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[2]
SCRATCH = Path(__file__).resolve().parent
DEST = ROOT / 'Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21'
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
        with path.open('rb') as stream:
            magic = stream.read(4)
        require(magic not in [b'\x7fELF', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\xca\xfe\xba\xbe'],
                f'Executable is not compact archival evidence: {path}')
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
              'benchmark-value', 'host-AppleRuntimeConsumer-value', 'host-ResourceStress-value',
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

    powered = SCRATCH / 'powered'
    build_identity = read(SCRATCH / 'benchmark-build.json')
    require(build_identity['source_commit'] == checkpoint and build_identity['builds_verified'] is True and
            build_identity['developer_dir'] == '/Library/Developer/CommandLineTools', 'Invalid final benchmark build identity')
    require(read(powered / 'build-identity.json') == build_identity, 'Powered/build identity mismatch')
    guard_status = read(powered / 'status.json')
    require(guard_status['completed'] and not guard_status['power_guard_failed'] and
            guard_status['source_commit'] == checkpoint, 'Powered campaign incomplete or power guard failed')
    campaign_commands = labelled(read(powered / 'commands.json'), ['scalar', 'colour'], 'Powered campaigns')
    require(all(row['exit_code'] == 0 and not row['power_guard_failed'] for row in campaign_commands.values()),
            'Powered comparison command failed')
    conditions = lines(powered / 'conditions.jsonl')
    require(all(row['power']['exit_code'] == 0 and 'AC Power' in row['power']['stdout'] for row in conditions),
            'Powered campaign has a non-AC/unknown observation')
    analysis = read(powered / 'combined-analysis.json')
    colour_selection = SCRATCH / 'colour-cases.json'
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
        'runner_sha256': sha(needed(SCRATCH / 'compare-full.py')),
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
        require(environment['binary_sha256'] == benchmark_hashes == build_identity['binary_sha256'] and environment['predecessor_sha'] == predecessor,
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
    for filename in ['commands.json', 'conditions.jsonl', 'conditions-initial.json', 'combined-analysis.json', 'build-identity.json', 'driver.json', 'status.json']:
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

    # Automated ratios only identify observations; the separate authored review
    # retains each decision (including unresolved findings) without an inferred pass.
    reviewed_performance = read(SCRATCH / 'reviewed-performance-disposition.json')
    require(reviewed_performance['source_commit'] == checkpoint and
            isinstance(reviewed_performance['reviewed_status'], str) and reviewed_performance['reviewed_status'] and
            isinstance(reviewed_performance['findings'], list) and reviewed_performance['findings'] and
            all(row.get('id') and row.get('status') and row.get('evidence')
                for row in reviewed_performance['findings']), 'Missing current-source reviewed performance disposition')
    require(len({row['id'] for row in reviewed_performance['findings']}) == len(reviewed_performance['findings']),
            'Reviewed performance finding IDs are not unique')
    add(SCRATCH / 'reviewed-performance-disposition.json')
    # Recompute the entire six-case deep repeat from raw samples; a stale summary
    # or an omitted pattern must not be accepted as current tiny-image evidence.
    tiny_root = SCRATCH / 'diagnostics/final-tiny-deep-warm'
    tiny_status = read(tiny_root / 'status.json')
    require(tiny_status['completed'] and not tiny_status['power_guard_failed'] and
            tiny_status['source_commit'] == checkpoint, 'Tiny repeat incomplete or power guard failed')
    require(read(tiny_root / 'build-identity.json') == build_identity, 'Tiny/build identity mismatch')
    tiny_commands = labelled(read(tiny_root / 'commands.json'), ['tiny'], 'Tiny repeat')
    require(tiny_commands['tiny']['exit_code'] == 0 and not tiny_commands['tiny']['power_guard_failed'],
            'Tiny comparison command failed')
    require(all(row['power']['exit_code'] == 0 and 'AC Power' in row['power']['stdout']
                for row in lines(tiny_root / 'conditions.jsonl')), 'Tiny non-AC/unknown observation')
    spec = importlib.util.spec_from_file_location('final_performance_disposition', SCRATCH / 'performance-disposition.py')
    verifier = importlib.util.module_from_spec(spec); spec.loader.exec_module(verifier)
    tiny, _ = verifier.analyse(tiny_root / 'tiny', checkpoint, benchmark_hashes,
                              read(tiny_root / 'analysis.json')['tiny'])
    expected_tiny = {(37, 23, bits, pattern, 1, 0, 0)
                     for bits in [12, 16] for pattern in ['flat', 'ramp', 'noise']}
    require({tuple(row[key] for key in KEYS) for row in tiny['cases']} == expected_tiny and
            len(tiny['cases']) == 6 and all(row['warmups_per_process'] == [20000] and
            row['iterations_per_process'] == [1000] for row in tiny['cases']), 'Wrong tiny-repeat protocol')
    require(tiny['cases'] == disposition['measurements']['final-tiny-deep-warm']['cases'],
            'Tiny disposition differs from raw results')
    require(tiny['consumer_sha256'] == harness_hashes['consumer_sha256'] and
            tiny['runner_sha256'] == sha(SCRATCH / 'compare-small-deep-warm.py'), 'Tiny reproduction mismatch')

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
                size_report['profile_count'] == len(size_report['cases']) == len(size_cases) == len(expected_sizes) and
                set(size_cases) == set(expected_sizes), 'RGB size diagnostic does not cover all final size outliers')
        require(size_report['parser_controls_passed'] is True and size_report['all_header_only_differences_verified'] is True and
                size_report['successful_cross_decodes'] == 2 * len(expected_sizes), 'Incomplete RGB size diagnostic checks')
        for case, row in size_cases.items():
            require(all(row[key] is True for key in ['matches_recorded_benchmark_sizes', 'exact_signalling_segments',
                    'entropy_identical', 'normalized_streams_identical', 'header_only_difference_verified']) and
                    row['cross_decodes'] == {'predecessor_decodes_successor': True, 'successor_decodes_predecessor': True} and
                    all(row['producers'][label]['bytes'] == expected_sizes[case]['encoded_size']['bytes'][label]
                        for label in ['predecessor', 'successor']), f'{case}: RGB size diagnostic verification differs')
        require(len(size_report['commands']) == 4 * len(expected_sizes) and all(row['exit_code'] == 0 for row in size_report['commands']),
                'RGB size diagnostic commands are incomplete or failed')
        require(size_report['script_sha256'] == sha(needed(SCRATCH / 'check-rgb-size-outliers.py')),
                'RGB size diagnostic script differs from archived reproduction')

    scripts = ['run-tests.py', 'qualify.py', 'qualification-source.py', 'prepare-native.py',
               'run-native-template.py', 'apple-build-value.py', 'apple-runtime-value.py',
               'apple-resource-value.py', 'run-powered.py', 'analyse-powered.py',
               'compare-full.py', 'compare-small-deep-warm.py', 'performance-disposition.py',
               'write-benchmark-build.py', 'Consumer.swift', 'small-cases.json', 'archive-final.py']
    for name in scripts:
        add(SCRATCH / name, 'reproduction/' + name)
    for name in ['qualification-source.json', 'consumer-builds.json', 'benchmark-build.json',
                 'ARCHIVE-PLAN.md', 'preparation.json', 'native-driver-commands.json',
                 'preexisting-simulator-state.json']:
        add(SCRATCH / name)
    if (SCRATCH / 'check-rgb-size-outliers.py').is_file():
        add(SCRATCH / 'check-rgb-size-outliers.py', 'reproduction/check-rgb-size-outliers.py')
    add(SCRATCH / 'native-payload/run-native.py', 'reproduction/run-native.py')
    for relative in ['Scripts/Benchmark/compare.py', 'Scripts/Benchmark/Consumer.swift',
                     'Scripts/test-cli.py', 'Scripts/test-payload-cli.py']:
        add(ROOT / relative, 'reproduction/' + relative)
    for name in ['qualify.log', 'tests-driver.log', 'native-ssh.log', 'native-vm.log', 'powered.log', 'tiny-driver.log',
                 'simulator-restore.json']:
        if (SCRATCH / name).is_file():
            add(SCRATCH / name)

    for path in sorted(SCRATCH.glob('archive-preflight-*.log')):
        add(path)

    for required_diagnostic in ['candidate-abc-2026-10-21/manifest.json',
                                'same-process-2026-10-21/manifest.json']:
        diagnostic_manifest = SCRATCH / 'diagnostics' / required_diagnostic
        diagnostic_files = read(diagnostic_manifest)['files']
        folder = diagnostic_manifest.parent.resolve()
        require(set(diagnostic_files) == {str(path.relative_to(folder)) for path in folder.rglob('*')
                    if path.is_file() and path != diagnostic_manifest}, 'Diagnostic manifest inventory mismatch')
        for relative, entry in diagnostic_files.items():
            path = (folder / relative).resolve()
            require(path.is_relative_to(folder) and needed(path).stat().st_size == entry['bytes'] and
                    sha(path) == entry['sha256'], f'Diagnostic manifest hash mismatch: {relative}')
    same_process_root = SCRATCH / 'diagnostics/final-same-process'
    same_process = read(same_process_root / 'completion.json')
    same_build = read(same_process_root / 'build.json')
    require(same_process['status'] == 'completed' and same_process['source'] == checkpoint and
            same_process['predecessor'] == predecessor and same_process['preflight_cases'] == 6 and
            same_process['timed_processes'] == 24 and len(same_process['stages']) == 4 and
            all(row['exit_code'] == 0 for row in same_process['stages']),
            'Incomplete final same-process diagnostic')
    require(same_build['exit_code'] == 0 and same_build['source_unchanged'] and
            same_build['source_before'] == same_build['source_after'] and
            same_build['binary_sha256'] == same_process['binary_sha256'],
            'Final same-process diagnostic build identity mismatch')
    for identity_file in ['identity-check.json', 'results/post-run-identity.json']:
        identity = read(same_process_root / identity_file)
        require(identity['source'] == same_build['source_before'] and
                identity['source']['successor']['head'] == checkpoint and
                identity['source']['predecessor']['head'] == predecessor and
                all(identity['source'][producer]['diff'] == '' for producer in ['predecessor', 'successor']) and
                identity['binary_sha256'] == same_build['binary_sha256'],
                'Final same-process diagnostic source/binary changed')
    controls = read(SCRATCH / 'diagnostics/tiny-process-controls/results-1/complete.json')
    require(controls['completed'] is True and len(controls['controls']) == 3 and
            {row['control'] for row in controls['controls']} == {'binary', 'canonical-self', 'pinned-self'} and
            all({row['bits'] for row in control['cases']} == {12, 16} and len(control['cases']) == 2
                for control in controls['controls']), 'Incomplete tiny process controls')
    confirmatory_repeats = []
    for confirmation_phase, confirmation_warmups, confirmation_observations in [
            ('tiny-confirmatory', 20000, 1000), ('tiny-short-confirmatory', 5, 5)]:
        confirmation_root = SCRATCH / 'diagnostics' / confirmation_phase
        confirmation = read(confirmation_root / 'results-1/complete.json')
        confirmation_environment = read(confirmation_root / 'results-1/environment.json')
        schedule = read(confirmation_root / 'schedule.json')
        schedule_sha256 = sha(confirmation_root / 'schedule.json')
        require(confirmation['completed'] is True and confirmation['processes'] == 192 and
                confirmation['performance_qualified'] is False and schedule['expected_processes'] == 192 and
                schedule['blocks_per_case'] == 16 and schedule['warmups'] == confirmation_warmups and
                schedule['observations_per_process'] == confirmation_observations and len(schedule['cases']) == 6 and
                confirmation['schedule_sha256'] == confirmation_environment['schedule_sha256'] == schedule_sha256 and
                confirmation['runner_sha256'] == confirmation_environment['runner_sha256'] == sha(confirmation_root / 'run.py') and
                confirmation_environment['plan'] == schedule,
                'Incomplete or changed fixed confirmatory schedule')
        require(schedule['producers']['successor']['source'] == checkpoint and
                schedule['producers']['predecessor']['source'] == predecessor and
                all(schedule['producers'][producer]['sha256'] == benchmark_hashes[producer]
                    for producer in ['predecessor', 'successor']), 'Confirmatory source/binary mismatch')
        confirmation_raw = lines(confirmation_root / 'results-1/raw.jsonl')
        expected_order = [(entry, producer) for entry in schedule['schedule'] for producer in entry['order']]
        require(len(expected_order) == len(confirmation_raw) == 192, 'Missing confirmatory processes')
        for (entry, producer), row in zip(expected_order, confirmation_raw):
            require(row['exit_code'] == 0 and row['block'] == entry['block'] and row['case_id'] == entry['case']['id'] and
                    row['producer'] == producer and row['order'] == entry['order'] and row['warmups'] == confirmation_warmups and
                    row['iterations'] == confirmation_observations and row['binary_sha256'] == benchmark_hashes[producer] and
                    all(len(row[operation + '_seconds']) == confirmation_observations for operation in OPERATIONS),
                    'Confirmatory process differs from its predeclared schedule')
        confirmation_summary = read(confirmation_root / 'results-1/summary.json')
        require(len(confirmation_summary) == 6 and {row['case']['id'] for row in confirmation_summary} ==
                {row['id'] for row in schedule['cases']} and
                all(set(row['operations']) == set(OPERATIONS) and
                    all(len(op['pairs']) == 16 and op['observations_per_producer'] == 16 * confirmation_observations for op in row['operations'].values())
                    for row in confirmation_summary), 'Incomplete confirmatory interval/paired analysis')
        confirmation_conditions = lines(confirmation_root / 'results-1/conditions.jsonl')
        confirmation_conditions += [confirmation_environment['conditions'], confirmation['end_conditions']]
        require(confirmation_conditions and all(row['power']['exit_code'] == 0 and
                "Now drawing from 'AC Power'" in row['power']['output'] for row in confirmation_conditions),
                'Confirmatory campaign has a non-AC or unknown condition')
        confirmatory_repeats.append(dict(phase=confirmation_phase, cases=6, paired_blocks_per_case=16,
            processes=192, warmups=confirmation_warmups, observations_per_process=confirmation_observations,
            source_checkpoint=checkpoint, schedule_sha256=schedule_sha256, acceptance='Not determined by archive'))

    coverage = read(SCRATCH / 'diagnostics/independent-fixture-coverage.json')
    require(coverage['source_commit'] == checkpoint and
            coverage['native_independent_coverage']['count'] == 15 and
            coverage['fallback_independent_coverage']['count_charls_sample'] == 66 and
            coverage['fallback_independent_coverage']['count_hp_sample'] == 18 and
            len(coverage['xml_observations']) == 8, 'Missing affected independent-fixture coverage review')

    boundary_root = SCRATCH / 'diagnostics/decode-report-boundary'
    boundary_complete = read(boundary_root / 'results-3/complete.json')
    require(boundary_complete['completed'] is True and boundary_complete['performance_qualified'] is False and
            boundary_complete['decode_processes'] == 128 and boundary_complete['micro_processes'] == 96,
            'Incomplete decode/report boundary diagnostic')
    # Preserve the stopped battery admissions and zero-duration validator failure
    # alongside the resumed logical records; never replace them with a success stub.
    for name in ['results-1/interrupted.json', 'results-2/interrupted.json', 'results-3/interrupted.json',
                 'results-3/micro-raw.jsonl', 'results-3/micro-raw-complete.jsonl',
                 'results-3/micro-resume.json', 'results-3/validator-correction.json',
                 'run-before-zero-correction.py', 'resume-micro.py', 'RESULTS.md']:
        needed(boundary_root / name)

    # These diagnostics deliberately build beside their source. Prune only known
    # build tree without traversing or copying it; build.json preserves its hash.
    # Unexpected caches/build trees elsewhere remain an archival error.
    excluded_diagnostic_build_trees = ['diagnostics/final-same-process/.build',
        'diagnostics/decode-report-boundary/.build']
    excluded_diagnostic_caches = []
    for directory, directories, filenames in os.walk(SCRATCH / 'diagnostics'):
        directory = Path(directory)
        if str((directory / '.build').relative_to(SCRATCH)) in excluded_diagnostic_build_trees and '.build' in directories:
            directories.remove('.build')
        if '__pycache__' in directories:
            directories.remove('__pycache__')
            excluded_diagnostic_caches.append(str((directory / '__pycache__').relative_to(SCRATCH)))
        require(not set(directories) & {'.build', 'test-build', 'native-payload', '__pycache__'},
                f'Unexpected build/cache tree in diagnostics: {directory}')
        for filename in sorted(filenames):
            path = directory / filename
            require(not path.is_symlink(), f'Diagnostic symlink requires explicit handling: {path}')
            require(path.stat().st_size < 20 * 1024 * 1024, f'Noncompact diagnostic: {path}')
            add(path)

    mutation_root = SCRATCH / 'mutation'
    mutation_source = read(mutation_root / 'source.json')
    require(mutation_source['revision'] == mutation_source['run_head_sha'] == checkpoint and mutation_source['run_id'] and
            mutation_source['run_url'] and mutation_source['artifact_hashes'], 'Mutation run provenance mismatch')
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
        require(needed(folder / 'campaign-stderr.log').stat().st_size == 0,
                f'Nonempty mutation sanitizer stderr: {entry}')
        mutation_results[entry] = dict(outcome=outcome, final=final)
    for path in sorted(mutation_root.rglob('*')):
        if path.is_file():
            require(path.stat().st_size < 20 * 1024 * 1024, f'Mutation evidence needs compact packaging: {path}')
            add(path)


    workspace = args.workspace
    if workspace is None:
        candidates = [SCRATCH / 'workspace-accounting-evidence']
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
    native_descriptors = read(SCRATCH / 'workspace-native-descriptors.json')
    workspace_run = read(SCRATCH / 'workspace-measurement-run.json')
    require(native_descriptors['source_checkpoint'] == workspace_run['headSha'] == checkpoint and
            native_descriptors['binary_sha256'] == workspace_summary['binary_sha256'] and
            native_descriptors['classifier_sha256'] == workspace_summary['classifier_sha256'],
            'Supplemental workspace source/binary/classifier mismatch')
    require(workspace_run['status'] == 'completed' and workspace_run['conclusion'] == 'success',
            'Workspace measurement run is incomplete or unsuccessful')
    for name in ['workspace-native-descriptors.json', 'workspace-measurement-run.json']:
        add(SCRATCH / name)

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
        checkpoint_status='intermediate', milestone4_complete=False,
        archive_directory=DEST.name, software_validation_passed=bool(software_passed),
        local_tests=test_summary, cli=dict(payload_checks=len(payload), process_checks=process['checks'], status=process['status']),
        apple_simulators=simulator_summary, apple_resources=resource_summary,
        native_execution={k: v for k, v in native.items() if k != 'commands'},
        native_cli=dict(payload_checks=len(native_payload_cli), process_checks=native_process['checks'], status=native_process['status']),
        native_resource_frames=sum(r['frames'] for r in native_resources),
        performance=performance, condition_observations=len(conditions),
        performance_acceptance='Not determined by the archiver; see the separately authored reviewed disposition and preserve all original ratios.',
        reviewed_performance_disposition=reviewed_performance,
        workspace_included=workspace_summary is not None,
        workspace=workspace_summary, mutation=dict(source=mutation_source, results=mutation_results),
        historical_evidence=dict(manifest='milestone4-final-2026-10-14.json',
            sha256=sha(needed(DEST.parent / 'milestone4-final-2026-10-14.json')),
            scope='Historical source c330 and earlier diagnostic failures remain there; not copied or relabelled'),
        tiny_repeat=dict(cases=6, source_checkpoint=checkpoint, binary_sha256=benchmark_hashes),
        confirmatory_repeats=confirmatory_repeats,
        excluded_build_trees=excluded_diagnostic_build_trees,
        excluded_generated_python_caches=sorted(excluded_diagnostic_caches),
        limitations=['Physical device testing remains pending; Milestone 5 remains deferred.',
                     'The owner verifies CI and merges; this archive makes no GitHub check-status claim.',
                     'Native OS 26.0 evidence is hardware-virtualised arm64 execution, not physical-device testing.',
                     'Workspace replay is required to match the final production checkpoint; its measured scope remains finite.',
                     'Requested heap, stack, allocator overhead and RSS remain distinct; unknown is not zero.'])
    for finding in reviewed_performance['findings']:
        for reference in finding['evidence']:
            require(reference in sources, f'Reviewed performance evidence link is not archived: {reference}')

    inventory = {key: dict(bytes=path.stat().st_size, sha256=sha(path),
        source=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path)) for key, path in sorted(sources.items())}
    require(inventory['reproduction/Scripts/Benchmark/Consumer.swift']['sha256'] == harness_hashes['consumer_sha256'] and
            inventory['reproduction/compare-full.py']['sha256'] == harness_hashes['runner_sha256'],
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
