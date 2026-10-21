#!/usr/bin/env python3
"""One fixed128-round short confirmation; preserve pooled estimand and all24 metrics."""
import argparse
import importlib.util
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
PARENT = ROOT / 'work/m4-short-path-diagnostic'
BUILD_IDENTITY = json.loads((PARENT / 'build-identity.json').read_text())
CANDIDATE = {'path': str(pathlib.Path(BUILD_IDENTITY['binary']).relative_to(ROOT)),
    'sha256': BUILD_IDENTITY['binary_sha256'], 'base_revision': BUILD_IDENTITY['source']['base_source'],
    'patch_sha256': BUILD_IDENTITY['source']['patches']['combined.patch']}
MODES = {'short': (5, 5)}
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
    checker = PARENT / 'run-comparisons.py'
    require(sha(checker) == '62edb6a080e65e00f2ae1aa62002d2805ebf2b5a42a472c1c9fd7ec8bac178fe', 'Parent source checker changed')
    spec = importlib.util.spec_from_file_location('frozen_parent', checker)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    proof = module.source_guards(env)
    frozen = json.loads((HERE / 'plan.json').read_text())
    require(sha(HERE / 'run.py') == frozen['runner_sha256'], 'Frozen runner changed')
    require(sha(HERE / 'analyse.py') == frozen['analysis_sha256'], 'Frozen analysis changed')
    require(sha(HERE / 'schedules/short-pinned.json') == frozen['schedule_sha256'], 'Frozen schedule changed')
    require(sha(PARENT / 'build-identity.json') == frozen['candidate_build_identity_sha256'], 'Frozen build identity changed')
    proof.update(plan_sha256=sha(HERE/'plan.json'), analysis_sha256=frozen['analysis_sha256'])
    return proof


def make_plan(mode, reference):
    cases = [dict(id=f'p{bits}-{pattern}', width=37, height=23, bits=bits, pattern=pattern, components=1, near=0, interleave=0)
        for bits in [12, 16] for pattern in ['flat', 'ramp', 'noise']]
    entries = []
    for block in range(128):
        offset = block % len(cases)
        indices = list(range(offset, len(cases))) + list(range(offset))
        if block % 2:
            indices.reverse()
        for position, index in enumerate(indices):
            order = ['reference', 'candidate'] if block % 2 == 0 else ['candidate', 'reference']
            entries.append(dict(block=block, position=position, case=cases[index], order=order))
    return dict(schema=1, created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        cases=cases, blocks_per_case=128, warmups=MODES[mode][0], observations_per_process=MODES[mode][1], mode=mode, reference=reference,
        expected_processes=1536, producers={'reference': REFERENCES[reference], 'candidate': CANDIDATE}, operations=OPERATIONS, schedule=entries,
        confidence=dict(estimator='Original ratio of pooled medians, all640 observations per producer',
            resamples=50000, seed=20261021, family_size=24,
            familywise_quantiles=[.05/(2*24),1-.05/(2*24)], marginal_quantiles=[.025,.975],
            cluster='Whole paired round jointly across all6 cases,4 operations,2 producers and5 observations',
            strata='Even rounds reference first across every case; odd rounds candidate first across every case; sample64 complete rounds per stratum with replacement',
            limitations='Nominal percentile-bootstrap intervals assume exchangeable independent rounds within strata; one session may retain temporal correlation.'),
        decision='No automatic acceptance, reruns, drops, stopping based on outcomes, or threshold waiver. Preserve every completed/partial result and interruption reason. Report all24 pooled median ratios; upper familywise bound<=1.05 within measured gate, lower>1.05 confirmed regression, overlap unresolved. Retain marginal intervals, paired ratios, order and temporal spread.')



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
                    print(f"Round {entry['block'] + 1}/128 complete; {len(rows)}/1536 processes retained", flush=True)
            snapshot()
        end_guards = source_guards(env)
        end = conditions(env)
        require("Now drawing from 'AC Power'" in end['power']['output'], 'AC lost before completion')
        require(len(rows) == 1536, 'Incorrect process count')
        write(output / 'measurement-complete.json', dict(completed=True, processes=len(rows), source_guards=end_guards, end_conditions=end, plan_sha256=sha(HERE/'plan.json'), schedule_sha256=sha(plan_path), runner_sha256=sha(pathlib.Path(__file__))))
        analysis = subprocess.run([str(pathlib.Path('/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')), str(HERE/'analyse.py'), '--output', str(output)], cwd=ROOT, env=env, capture_output=True, text=True)
        write(output/'analysis-command.json', dict(exit_code=analysis.returncode, stdout=analysis.stdout, stderr=analysis.stderr))
        require(analysis.returncode == 0, 'Frozen analysis failed')
        summary = json.loads((output/'summary.json').read_text())
        write(output / 'complete.json', dict(completed=True, performance_qualified=False, processes=len(rows), plan_sha256=sha(HERE/'plan.json'), analysis_sha256=sha(HERE/'analyse.py'),
            source_guards=end_guards, end_conditions=end, schedule_sha256=sha(plan_path), runner_sha256=sha(pathlib.Path(__file__))))
        for case in summary:
            print(json.dumps(dict(case=case['case']['id'], operations={op: {k: data[k] for k in ['pooled_ratio', 'familywise_bonferroni_95', 'marginal_95', 'interpretation']} for op, data in case['operations'].items()})), flush=True)
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
