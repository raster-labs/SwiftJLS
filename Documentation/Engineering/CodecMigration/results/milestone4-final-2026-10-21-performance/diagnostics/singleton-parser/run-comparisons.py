#!/usr/bin/env python3
"""Two predeclared bounded combined-candidate comparisons; no automatic acceptance or outcome-based repeats."""
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

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'
BASELINE = '15aa75164145414f3d5ffb801401c52d40cc5bcc'
REFERENCES = {
    'pinned': {'path': 'work/m4-benchmark/predecessor/.build/release/Benchmark',
        'sha256': 'b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45', 'source': BASELINE},
}
BUILD_IDENTITY = json.loads((HERE / 'build-identity.json').read_text())
CANDIDATE = {'path': str(pathlib.Path(BUILD_IDENTITY['binary']).relative_to(ROOT)),
    'sha256': BUILD_IDENTITY['binary_sha256'], 'base_revision': BUILD_IDENTITY['source']['base_source'],
    'patch_sha256': BUILD_IDENTITY['source']['combined_patch_sha256']}
MODES = {'short': (5, 5), 'long': (20000, 1000)}
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
    return dict(command=command, exit_code=r.returncode, output=r.stdout + r.stderr)


def conditions(env):
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        power=record(['pmset', '-g', 'batt'], env), thermal=record(['pmset', '-g', 'therm'], env),
        load=record(['sysctl', '-n', 'vm.loadavg'], env))


def source_guards(env):
    identity = json.loads((HERE / 'build-identity.json').read_text())
    source = identity['source']
    require(source == json.loads((HERE / 'source-identity.json').read_text()), 'Candidate source/build records differ')
    require(identity['source_unchanged'] and identity['consumer_unchanged'], 'Candidate build identity incomplete')
    require(identity['command']['exit_code'] == 0, 'Candidate build failed')
    require(source['base_source'] == SOURCE, 'Candidate base changed')
    actual = {str(p.relative_to(HERE / 'codec')): sha(p) for directory in ('Sources', 'Tests')
        for p in (HERE / 'codec' / directory).rglob('*.swift')}
    actual.update({name: sha(HERE / 'codec' / name) for name in ('Package.swift', 'VERSION')})
    require(source['source_files'] == actual, 'Candidate sources changed')
    require(source['combined_patch_sha256'] == CANDIDATE['patch_sha256'] == sha(HERE / 'combined.patch'), 'Candidate patch changed')
    require(identity['binary_sha256'] == CANDIDATE['sha256'], 'Candidate binary provenance changed')
    require(source['consumer_sha256'] == CONSUMER_SHA, 'Candidate original consumer provenance changed')
    require(source['consumer_package_sha256'] == sha(HERE / 'consumer/Package.swift'), 'Candidate consumer package changed')
    require(source['developer_dir'] == '/Library/Developer/CommandLineTools', 'Candidate toolchain changed')
    guards = dict(successor_head=record(['git', 'rev-parse', 'HEAD'], env),
        successor_diff=record(['git', 'diff', '--exit-code', SOURCE, '--', 'Sources', 'Tests', 'Package.swift', 'Scripts/Benchmark'], env),
        predecessor_head=record(['git', 'rev-parse', 'HEAD'], env, ROOT.parent / 'JLSwift'),
        predecessor_diff=record(['git', 'diff', '--exit-code', BASELINE, '--', 'Sources', 'Package.swift'], env, ROOT.parent / 'JLSwift'))
    require(guards['successor_head']['output'].strip() == SOURCE, 'Exact successor HEAD required')
    require(guards['successor_diff']['exit_code'] == 0, 'Successor source differs from frozen source')
    require(guards['predecessor_head']['output'].strip() == BASELINE, 'Predecessor revision changed')
    require(guards['predecessor_diff']['exit_code'] == 0, 'Predecessor source changed')
    for path in ['Scripts/Benchmark/Consumer.swift', 'work/m4-benchmark/predecessor/Sources/Benchmark/main.swift',
                 'work/m4-benchmark/successor/Sources/Benchmark/main.swift',
                 'work/m4-singleton-parser-diagnostic/consumer/Sources/Benchmark/main.swift']:
        require(sha(ROOT / path) == CONSUMER_SHA, 'Common consumer changed: ' + path)
    for producer in [*REFERENCES.values(), CANDIDATE]:
        require(sha(ROOT / producer['path']) == producer['sha256'], 'Frozen binary changed: ' + producer['path'])
    guards.update(candidate_build_identity_sha256=sha(HERE / 'build-identity.json'), candidate_source_hashes=source['source_files'],
        candidate_patch_sha256=CANDIDATE['patch_sha256'], candidate_binary_sha256=CANDIDATE['sha256'])
    return guards


def make_plan(mode, reference):
    cases = [dict(id=f'p{bits}-{pattern}', width=37, height=23, bits=bits, pattern=pattern, components=1, near=0, interleave=0)
        for bits in [12, 16] for pattern in ['flat', 'ramp', 'noise']]
    entries = []
    for block in range(16):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2:
            indices.reverse()
        for position, index in enumerate(indices):
            order = ['reference', 'candidate'] if (block + index) % 2 == 0 else ['candidate', 'reference']
            entries.append(dict(block=block, position=position, case=cases[index], order=order))
    return dict(schema=1, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        cases=cases, blocks_per_case=16, warmups=MODES[mode][0], observations_per_process=MODES[mode][1], mode=mode, reference=reference,
        expected_processes=192, producers={'reference': REFERENCES[reference], 'candidate': CANDIDATE}, operations=OPERATIONS, schedule=entries,
        confidence=dict(unit='paired process block; never individual timed iterations',
            bootstrap='Percentile 95% interval of the median of 16 paired ratios/deltas; 20,000 resamples; fixed seed 20261021 plus case index*10 plus operation index.',
            exact='Conservative distribution-free nominal 95% median interval: ordered observations 4 and 13 (one-based), coverage 1 - 2*sum(C(16,j),j=0...3)/2^16 = 0.978729248046875 under independent continuous observations; ties conservative.',
            limitations='Blocks use separate processes but share one host/session and may retain temporal correlation. Intervals assume independent/exchangeable blocks, are marginal rather than simultaneous across 24 metrics, and do not establish causation or acceptance. Bootstrap intervals may underrepresent unobserved tails with only 16 blocks.'),
        decision='No automatic acceptance, reruns, drops, stopping based on outcomes, or threshold waiver. Preserve every completed/partial result and interruption reason. Report pooled medians, paired block medians, order groups, spread, counts above 1.05, all ratios/deltas, and both intervals.')


def percentile(sorted_values, q):
    position = (len(sorted_values) - 1) * q
    low = int(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (position - low)


def intervals(values, seed):
    require(len(values) == 16, 'Expected 16 paired process blocks')
    rng = random.Random(seed)
    bootstrap = sorted(statistics.median(rng.choices(values, k=16)) for _ in range(20000))
    ordered = sorted(values)
    return dict(percentile_bootstrap_95=[percentile(bootstrap, .025), percentile(bootstrap, .975)],
        exact_conservative_nominal_95=[ordered[3], ordered[12]], exact_coverage=0.978729248046875)


def analyse(rows, plan):
    summary = []
    for case_index, case in enumerate(plan['cases']):
        selected = [r for r in rows if r['case_id'] == case['id']]
        require(len(selected) == 32, 'Incomplete case')
        result = dict(case=case, operations={})
        for op_index, operation in enumerate(OPERATIONS):
            pooled = {producer: [v for row in selected if row['producer'] == producer for v in row[operation + '_seconds']] for producer in PRODUCERS}
            medians = {producer: statistics.median(values) for producer, values in pooled.items()}
            pairs = []
            for block in range(16):
                pair = {r['producer']: r for r in selected if r['block'] == block}
                med = {producer: statistics.median(row[operation + '_seconds']) for producer, row in pair.items()}
                pairs.append(dict(block=block, order=pair['candidate']['order'], reference_median_seconds=med['reference'],
                    candidate_median_seconds=med['candidate'], ratio=med['candidate'] / med['reference'],
                    delta_seconds=med['candidate'] - med['reference']))
            ratios = [p['ratio'] for p in pairs]
            deltas = [p['delta_seconds'] for p in pairs]
            ordered = sorted(ratios)
            result['operations'][operation] = dict(pooled_median_seconds=medians,
                pooled_ratio=medians['candidate'] / medians['reference'], observations_per_producer=16 * plan['observations_per_process'],
                median_block_ratio=statistics.median(ratios), median_block_delta_seconds=statistics.median(deltas),
                ratio_range=[min(ratios), max(ratios)], ratio_iqr=[percentile(ordered, .25), percentile(ordered, .75)],
                ratio_sample_standard_deviation=statistics.stdev(ratios), blocks_above_1_05=sum(r > 1.05 for r in ratios),
                ratio_intervals=intervals(ratios, 20261021 + case_index * 10 + op_index),
                delta_intervals_seconds=intervals(deltas, 20261021 + case_index * 10 + op_index),
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
        (HERE / 'schedules').mkdir(exist_ok=False)
        for mode in MODES:
            for reference in ('pinned',):
                path = HERE / 'schedules' / f'{mode}-{reference}.json'
                write(path, make_plan(mode, reference))
                print(str(path.relative_to(HERE)) + ': ' + sha(path), flush=True)
        return
    require(args.mode is not None and args.reference is not None, '--mode and --reference required')
    global PRODUCERS
    PRODUCERS = {'reference': REFERENCES[args.reference], 'candidate': CANDIDATE}
    plan_path = HERE / 'schedules' / f'{args.mode}-{args.reference}.json'
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
        write(output / 'environment.json', dict(plan=plan, schedule_sha256=sha(plan_path), runner_sha256=sha(pathlib.Path(__file__)),
            source_guards=start_guards, conditions=start, consumer_sha256=CONSUMER_SHA,
            swift=record(['swift', '--version'], env), performance_qualified=False, caller_context='original main-actor public-API Consumer'))
        require("Now drawing from 'AC Power'" in start['power']['output'], 'AC power required')
        with (output / 'raw.jsonl').open('w') as raw, (output / 'conditions.jsonl').open('w') as log:
            last_snapshot = 0
            def snapshot():
                nonlocal last_snapshot
                value = conditions(env)
                value['completed_processes'] = len(rows)
                log.write(json.dumps(value) + '\n')
                log.flush()
                last_snapshot = time.monotonic()
                require("Now drawing from 'AC Power'" in value['power']['output'], 'AC power lost; partial evidence retained')
            snapshot()
            for entry in plan['schedule']:
                case = entry['case']
                for producer in entry['order']:
                    command = [str(ROOT / PRODUCERS[producer]['path']), '37', '23', str(case['bits']), case['pattern'], str(plan['warmups']), str(plan['observations_per_process']), producer]
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
                if entry['position'] == 5:
                    snapshot()
                    print(f"Round {entry['block'] + 1}/16 complete; {len(rows)}/192 processes retained", flush=True)
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        require("Now drawing from 'AC Power'" in end['power']['output'], 'AC lost before completion')
        require(len(rows) == 192, 'Incorrect process count')
        summary = analyse(rows, plan)
        write(output / 'summary.json', summary)
        write(output / 'complete.json', dict(completed=True, performance_qualified=False, processes=len(rows),
            source_guards=end_guards, end_conditions=end, schedule_sha256=sha(plan_path), runner_sha256=sha(pathlib.Path(__file__))))
        for case in summary:
            print(json.dumps(dict(case=case['case']['id'], operations={op: {k: data[k] for k in ['pooled_ratio', 'median_block_ratio', 'ratio_intervals', 'blocks_above_1_05']} for op, data in case['operations'].items()})), flush=True)
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
