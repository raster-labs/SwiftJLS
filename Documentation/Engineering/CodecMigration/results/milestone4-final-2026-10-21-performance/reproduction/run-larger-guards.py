#!/usr/bin/env python3
"""One predeclared15-case larger guard campaign, four balanced pairs; no automatic acceptance."""
import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import random
import signal
import statistics
import subprocess
import time
import xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'
BASELINE = '15aa75164145414f3d5ffb801401c52d40cc5bcc'
REFERENCES = {
    'pinned': {'path': 'work/m4-benchmark/predecessor/.build/release/Benchmark',
        'sha256': 'b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45', 'source': BASELINE},
}
PARENT = ROOT / 'work/m4-owned-admission-diagnostic'
BUILD_IDENTITY = json.loads((PARENT / 'build-identity.json').read_text())
LARGER_PLAN_PATH = HERE / 'larger-guard-plan.json'
LARGER_PLAN = json.loads(LARGER_PLAN_PATH.read_text())
CANDIDATE = {'path': str(pathlib.Path(BUILD_IDENTITY['binary']).relative_to(ROOT)),
    'sha256': BUILD_IDENTITY['binary_sha256'], 'base_revision': BUILD_IDENTITY['source']['base_source'],
    'patch_sha256': BUILD_IDENTITY['source']['patches']['combined.patch']}
MODES = {'guard': (5, 5)}
PRODUCERS = {}
OPERATIONS = ['encode', 'decode', 'prepare', 'prepare_encode']
CONSUMER_SHA = '27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def record(command, env, cwd=ROOT):
    r = subprocess.run(command, capture_output=True, text=True, env=env, cwd=cwd)
    return dict(command=command, exit_code=r.returncode, output=r.stdout + r.stderr, stdout=r.stdout, stderr=r.stderr)


def conditions(env):
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        power=record(['pmset', '-g', 'batt'], env), thermal=record(['pmset', '-g', 'therm'], env),
        load=record(['sysctl', '-n', 'vm.loadavg'], env))


def admit_conditions(value):
    require(value['power']['exit_code'] == 0 and "Now drawing from 'AC Power'" in value['power']['output'], 'AC power required; partial evidence retained')
    require(value['thermal']['exit_code'] == 0 and 'No thermal warning level has been recorded' in value['thermal']['output'] and 'No performance warning level has been recorded' in value['thermal']['output'], 'Thermal/performance admission failed; partial evidence retained')


def inventory(folder):
    paths = [folder / 'Package.swift', folder / 'VERSION']
    paths += [p for p in (folder / 'Sources').rglob('*') if p.is_file()]
    paths += [p for p in (folder / 'Tests').rglob('*.swift') if p.is_file()]
    require(all(not p.is_symlink() for p in paths), 'Source inventory includes a symlink')
    return {str(p.relative_to(folder)): sha(p) for p in sorted(paths)}


def source_guards(env):
    frozen = json.loads((HERE / 'larger-guard-readiness.json').read_text())
    require(sha(pathlib.Path(__file__)) == frozen['runner_sha256'], 'Frozen guard runner changed')
    require(sha(LARGER_PLAN_PATH) == frozen['larger_guard_plan_sha256'], 'Frozen15-case selection changed')
    require(sha(HERE / 'larger-guard-schedule.json') == frozen['schedule_sha256'], 'Frozen guard schedule changed')
    identity = json.loads((PARENT / 'build-identity.json').read_text()); source = identity['source']
    require(sha(PARENT / 'build-identity.json') == frozen['candidate_build_identity_sha256'], 'Candidate build identity changed')
    require(source == json.loads((PARENT / 'source-identity.json').read_text()), 'Candidate source/build records differ')
    require(identity['source_unchanged'] and identity['consumer_unchanged'] and identity['command']['exit_code'] == 0, 'Candidate build failed or changed')
    require(source['base_source'] == SOURCE, 'Candidate original base changed')
    require(inventory(PARENT / 'codec') == source['source_files'] == inventory(ROOT), 'Promoted/candidate source inventories differ')
    for name, expected in source['patches'].items():
        require(sha(PARENT / name) == expected, 'Candidate patch changed: ' + name)
    for key, name in [('release', 'focused-release.xml'), ('asan', 'focused-asan.xml')]:
        require(identity[key]['exit_code'] == 0 and sha(PARENT / name) == identity[key]['xml_sha256'], 'Candidate test evidence changed')
        cases = ET.parse(PARENT / name).findall('.//testcase')
        require(len(cases) == identity[key]['test_count'] and cases and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases), 'Candidate focused tests incomplete')
    reuse = json.loads((HERE / 'benchmark-reuse.json').read_text())
    benchmark = json.loads((HERE / 'benchmark-build.json').read_text())
    checkpoint = reuse['source_commit']
    require(reuse['verified'] is True and reuse['rebuilt'] is False, 'Verified frozen binary reuse required')
    require(reuse['original_build_record'] == identity and reuse['build_identity_sha256'] == frozen['candidate_build_identity_sha256'], 'Reuse provenance differs')
    require(reuse['binary']['sha256'] == CANDIDATE['sha256'] == identity['binary_sha256'], 'Reuse binary identity differs')
    require(reuse['source_files'] == source['source_files'], 'Reuse source inventory differs')
    require(benchmark['source_commit'] == checkpoint and benchmark['builds_verified'] is True and benchmark['binary_sha256']['successor'] == CANDIDATE['sha256'], 'Final benchmark bridge differs')
    require(benchmark['original_candidate_build_identity_sha256'] == frozen['candidate_build_identity_sha256'], 'Final benchmark origin differs')
    guards = dict(successor_head=record(['git', 'rev-parse', 'HEAD'], env),
        successor_status=record(['git', 'status', '--porcelain', '--untracked-files=all', '--', 'Sources', 'Tests', 'Package.swift', 'VERSION', 'Scripts/Benchmark'], env),
        predecessor_head=record(['git', 'rev-parse', 'HEAD'], env, ROOT.parent / 'JLSwift'),
        predecessor_diff=record(['git', 'diff', '--exit-code', BASELINE, '--', 'Sources', 'Package.swift'], env, ROOT.parent / 'JLSwift'),
        fixtures=record(['git', 'rev-parse', checkpoint + ':Tests/SwiftJLSTests/Fixtures'], env),
        swift=record(['swift', '--version'], env))
    require(guards['successor_head']['output'].strip() == checkpoint, 'Final source HEAD changed')
    require(guards['successor_status']['exit_code'] == 0 and not guards['successor_status']['output'].strip(), 'Final source tree dirty')
    require(guards['predecessor_head']['output'].strip() == BASELINE and guards['predecessor_diff']['exit_code'] == 0, 'Predecessor source changed')
    require(guards['fixtures']['output'].strip() == source['fixtures_tree'], 'Final fixtures differ')
    require(guards['swift']['exit_code'] == 0 and guards['swift']['stdout'] == source['swift'] and source['developer_dir'] == '/Library/Developer/CommandLineTools', 'Compiler differs from candidate build')
    for path in [ROOT/'Scripts/Benchmark/Consumer.swift', ROOT/'work/m4-benchmark/predecessor/Sources/Benchmark/main.swift', PARENT/'consumer/Sources/Benchmark/main.swift']:
        require(sha(path) == CONSUMER_SHA, 'Original consumer changed')
    require(sha(PARENT/'consumer/Package.swift') == source['consumer_package_sha256'], 'Candidate consumer package changed')
    for producer in [*REFERENCES.values(), CANDIDATE]:
        require(sha(ROOT/producer['path']) == producer['sha256'], 'Frozen binary changed')
    guards.update(source_commit=checkpoint, candidate_build_identity_sha256=frozen['candidate_build_identity_sha256'], candidate_source_hashes=source['source_files'],
        candidate_patch_sha256=CANDIDATE['patch_sha256'], candidate_binary_sha256=CANDIDATE['sha256'],
        benchmark_reuse_sha256=sha(HERE/'benchmark-reuse.json'), benchmark_build_sha256=sha(HERE/'benchmark-build.json'), larger_guard_plan_sha256=sha(LARGER_PLAN_PATH))
    return guards


def make_plan(mode, reference):
    cases = [dict(id=f"{c['width']}x{c['height']}-p{c['bits']}-{c['pattern']}-c{c['components']}-n{c['near']}-i{c['interleave']}", **c) for c in LARGER_PLAN['cases']]
    entries = []
    for block in range(4):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2:
            indices.reverse()
        for position, index in enumerate(indices):
            order = ['reference', 'candidate'] if (block + index) % 2 == 0 else ['candidate', 'reference']
            entries.append(dict(block=block, position=position, case=cases[index], order=order))
    return dict(schema=1, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), cases=cases,
        larger_guard_plan_sha256=sha(LARGER_PLAN_PATH), blocks_per_case=4, warmups=5, observations_per_process=5,
        mode=mode, reference=reference, expected_processes=120, producers={'reference': REFERENCES[reference], 'candidate': CANDIDATE},
        operations=OPERATIONS, schedule=entries, confidence='Four paired blocks: descriptive spread and order groups only, no16-block confidence formula.',
        decision='No automatic acceptance, outcome-based repeat, dropping or threshold waiver; explicit review of every original-Consumer result.')


def percentile(sorted_values, q):
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)




def analyse(rows, plan):
    summary = []
    for case_index, case in enumerate(plan['cases']):
        selected = [r for r in rows if r['case_id'] == case['id']]
        require(len(selected) == 8, 'Incomplete case')
        result = dict(case=case, operations={})
        for op_index, operation in enumerate(OPERATIONS):
            pooled = {producer: [v for row in selected if row['producer'] == producer for v in row[operation + '_seconds']] for producer in PRODUCERS}
            medians = {producer: statistics.median(values) for producer, values in pooled.items()}
            pairs = []
            for block in range(4):
                pair = {r['producer']: r for r in selected if r['block'] == block}
                med = {producer: statistics.median(row[operation + '_seconds']) for producer, row in pair.items()}
                pairs.append(dict(block=block, order=pair['candidate']['order'], reference_median_seconds=med['reference'],
                    candidate_median_seconds=med['candidate'], ratio=med['candidate'] / med['reference'],
                    delta_seconds=med['candidate'] - med['reference']))
            ratios = [p['ratio'] for p in pairs]
            deltas = [p['delta_seconds'] for p in pairs]
            ordered = sorted(ratios)
            result['operations'][operation] = dict(pooled_median_seconds=medians,
                pooled_ratio=medians['candidate'] / medians['reference'], observations_per_producer=4 * plan['observations_per_process'],
                median_block_ratio=statistics.median(ratios), median_block_delta_seconds=statistics.median(deltas),
                ratio_range=[min(ratios), max(ratios)], ratio_iqr=[percentile(ordered, .25), percentile(ordered, .75)],
                ratio_sample_standard_deviation=statistics.stdev(ratios), blocks_above_1_05=sum(r > 1.05 for r in ratios),
                median_ratio_by_first_producer={producer: statistics.median(p['ratio'] for p in pairs if p['order'][0] == producer) for producer in PRODUCERS}, pairs=pairs)
        summary.append(result)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prepare', action='store_true')
    parser.add_argument('--output', type=pathlib.Path)
    parser.add_argument('--mode', choices=MODES)
    parser.add_argument('--reference', choices=REFERENCES)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    if args.prepare:
        path = HERE / 'larger-guard-schedule.json'
        require(not path.exists(), 'Frozen schedule already exists')
        write(path, make_plan('guard', 'pinned'))
        print(str(path.relative_to(HERE)) + ': ' + sha(path), flush=True)
        return
    require(args.mode is not None and args.reference is not None, '--mode and --reference required')
    global PRODUCERS
    PRODUCERS = {'reference': REFERENCES[args.reference], 'candidate': CANDIDATE}
    plan_path = HERE / 'larger-guard-schedule.json'
    plan = json.loads(plan_path.read_text())
    expected_plan = make_plan(args.mode, args.reference)
    require(plan['schedule'] == expected_plan['schedule'], 'Predeclared schedule changed')
    require(plan['producers'] == PRODUCERS, 'Predeclared producers changed')
    require((plan['warmups'], plan['observations_per_process']) == MODES[args.mode], 'Predeclared repetitions changed')
    if args.check_only:
        env = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools')
        proof = source_guards(env)
        print(json.dumps(dict(status='identity-only passed; no execution', plan_sha256=sha(plan_path), source_guards=proof), indent=2))
        return
    require(args.output is not None, '--output required')
    output = args.output.resolve()
    require(not output.exists(), 'Fresh output directory required')
    output.mkdir(parents=True)
    env = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools', SWIFTJLS_BENCHMARK_END_TO_END='1')
    for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE']:
        env.pop(key, None)
    rows = []
    current = None
    process = None
    try:
        start_guards = source_guards(env)
        start = conditions(env)
        write(output / 'environment.json', dict(plan=plan, schedule_sha256=sha(plan_path), runner_sha256=sha(pathlib.Path(__file__)), larger_guard_plan_sha256=sha(LARGER_PLAN_PATH),
            source_guards=start_guards, conditions=start, consumer_sha256=CONSUMER_SHA,
            swift=record(['swift', '--version'], env), performance_qualified=False, caller_context='original main-actor public-API Consumer'))
        admit_conditions(start)
        with (output / 'raw.jsonl').open('w') as raw, (output / 'conditions.jsonl').open('w') as log:
            last_snapshot = 0
            def snapshot():
                nonlocal last_snapshot
                value = conditions(env)
                value['completed_processes'] = len(rows)
                log.write(json.dumps(value) + '\n')
                log.flush()
                last_snapshot = time.monotonic()
                admit_conditions(value)
            snapshot()
            for entry in plan['schedule']:
                case = entry['case']
                for producer in entry['order']:
                    command = [str(ROOT / PRODUCERS[producer]['path']), str(case['width']), str(case['height']), str(case['bits']), case['pattern'], str(plan['warmups']), str(plan['observations_per_process']), producer, str(case['components']), str(case['near']), str(case['interleave'])]
                    current = dict(entry=entry, producer=producer, command=command)
                    if time.monotonic() - last_snapshot >= 10:
                        snapshot()
                    began = time.monotonic()
                    process = subprocess.Popen(command, env=env, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                    while True:
                        try:
                            stdout, stderr = process.communicate(timeout=1)
                            break
                        except subprocess.TimeoutExpired:
                            if time.monotonic() - last_snapshot >= 10:
                                snapshot()
                            require(time.monotonic() - began < 600, 'Consumer exceeded 600-second process limit')
                    current.update(exit_code=process.returncode, stdout=stdout, stderr=stderr)
                    require(process.returncode == 0, 'Consumer failed')
                    row = json.loads(stdout)
                    expected = {k: v for k, v in case.items() if k != 'id'}
                    expected.update(label=producer, warmups=plan['warmups'], iterations=plan['observations_per_process'], end_to_end=True, resource_profile='successor-workspace-1GiB-memory-2GiB-v1')
                    require(all(row.get(k) == v for k, v in expected.items()), 'Consumer profile mismatch')
                    for operation in OPERATIONS:
                        values = row.get(operation + '_seconds', [])
                        require(len(values) == plan['observations_per_process'] and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values), 'Invalid observations')
                    require(all(a >= b for a, b in zip(row['prepare_encode_seconds'], row['prepare_seconds'])), 'Combined timing shorter than preparation')
                    row.update(case_id=case['id'], producer=producer, block=entry['block'], position=entry['position'], order=entry['order'],
                        binary_sha256=PRODUCERS[producer]['sha256'], command=command, exit_code=process.returncode, stderr=stderr,
                        process_seconds=time.monotonic() - began, completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
                    rows.append(row)
                    raw.write(json.dumps(row) + '\n')
                    raw.flush()
                    process = None
                if entry['position'] == len(plan['cases']) - 1:
                    snapshot()
                    print(f"Round {entry['block'] + 1}/4 complete; {len(rows)}/120 processes retained", flush=True)
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        admit_conditions(end)
        require(len(rows) == 120, 'Incorrect process count')
        summary = analyse(rows, plan)
        write(output / 'summary.json', summary)
        write(output / 'complete.json', dict(completed=True, performance_qualified=False, processes=len(rows),
            source_guards=end_guards, end_conditions=end, schedule_sha256=sha(plan_path), runner_sha256=sha(pathlib.Path(__file__)), larger_guard_plan_sha256=sha(LARGER_PLAN_PATH)))
        for case in summary:
            print(json.dumps(dict(case=case['case']['id'], operations={op: {k: data[k] for k in ['pooled_ratio', 'median_block_ratio', 'ratio_range', 'median_ratio_by_first_producer', 'blocks_above_1_05']} for op, data in case['operations'].items()})), flush=True)
    except BaseException as error:
        if process is not None and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            stdout, stderr = process.communicate()
            current.update(stdout=stdout, stderr=stderr, exit_code=process.returncode)
        write(output / 'interrupted.json', dict(completed=False, error=repr(error), completed_processes=len(rows), current=current,
            utc=datetime.datetime.now(datetime.timezone.utc).isoformat(), conditions=conditions(env)))
        raise


if __name__ == '__main__':
    main()
