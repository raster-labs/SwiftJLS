#!/usr/bin/env python3
"""Frozen-binary process controls; never infer regression acceptance."""
import argparse
import datetime
import hashlib
import json
import math
import os
import pathlib
import signal
import statistics
import subprocess
import time

ROOT = pathlib.Path(__file__).resolve().parents[4]
PRODUCERS = {
    'canonical': {'path': 'work/m4-benchmark/successor/.build/release/Benchmark',
        'sha256': '08cbea5d7629e04794923f67c7564a19384d9cdc8a83a0daabde02b622901261',
        'source': 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'},
    'isolated': {'path': 'work/m4-sample-native-diagnostic/consumer/.build/release/Benchmark',
        'sha256': '23176acf5d878ac62ffea2f846d003df210ca8fed8192485d259e922ab211d79',
        'source': 'c330b731e250d6b4c054c1c6a91fa9894e32a8c3 plus patch 0dd56230051726c9fd7d6bdf9d9e7023cc3a429ff7f19c4231c166365942d74e; production source bytes identical to bee49a2'},
    'pinned': {'path': 'work/m4-benchmark/predecessor/.build/release/Benchmark',
        'sha256': 'b117c48d9ca62e49ae0c618f6acb25d413165f0cfc2670599774f673b4164f45',
        'source': '15aa75164145414f3d5ffb801401c52d40cc5bcc'},
}
CONTROLS = {'binary': ('canonical', 'isolated'),
    'canonical-self': ('canonical', 'canonical'), 'pinned-self': ('pinned', 'pinned')}
OPERATIONS = ['encode', 'decode', 'prepare', 'prepare_encode']
CONSUMER_SHA = '27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def record(command, env):
    r = subprocess.run(command, capture_output=True, text=True, env=env)
    return dict(command=command, exit_code=r.returncode, output=r.stdout + r.stderr)


def conditions(env):
    return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        power=record(['pmset', '-g', 'batt'], env),
        thermal=record(['pmset', '-g', 'therm'], env),
        load=record(['sysctl', '-n', 'vm.loadavg'], env))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=pathlib.Path, required=True)
    parser.add_argument('--controls', choices=list(CONTROLS), nargs='+', default=list(CONTROLS))
    args = parser.parse_args()
    require(len(set(args.controls)) == len(args.controls), 'Duplicate control')
    output = args.output.resolve()
    require(not output.exists(), 'Choose a fresh output path; evidence must not be overwritten')
    output.mkdir(parents=True)
    env = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools',
        SWIFTJLS_BENCHMARK_END_TO_END='1')
    for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE']:
        env.pop(key, None)
    require(sha(ROOT / 'Scripts/Benchmark/Consumer.swift') == CONSUMER_SHA, 'Common consumer changed')
    for producer in PRODUCERS.values():
        require(sha(ROOT / producer['path']) == producer['sha256'], 'Frozen binary changed: ' + producer['path'])
    start = conditions(env)
    environment = dict(producers=PRODUCERS, controls={k: CONTROLS[k] for k in args.controls},
        consumer_sha256=CONSUMER_SHA, runner_sha256=sha(pathlib.Path(__file__)),
        power_and_conditions_start=start, swift=record(['swift', '--version'], env),
        host_repository_head=record(['git', 'rev-parse', 'HEAD'], env),
        methodology='Original common public-API consumer, unchanged binaries, 37x23 scalar flat at 12/16 bits. Four alternating process blocks, 20,000 warmups and 1,000 measured iterations per process. Canonical generation excluded; preparation and preparation+encode retained. Right/left ratios label producer identities explicitly. Self-comparisons are separate processes of the exact same binary. These controls test reproducibility and binary-linked differences; they do not waive any measured regression.',
        performance_qualified=False)
    (output / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    require("Now drawing from 'AC Power'" in start['power']['output'], 'AC power required')
    all_results = []
    for control in args.controls:
        producers = dict(zip(['left', 'right'], CONTROLS[control]))
        folder = output / control
        folder.mkdir()
        rows = []
        with (folder / 'raw.jsonl').open('w') as raw, (folder / 'conditions.jsonl').open('w') as log:
            last_snapshot = 0

            def snapshot():
                nonlocal last_snapshot
                value = conditions(env)
                log.write(json.dumps(value) + '\n')
                log.flush()
                last_snapshot = time.monotonic()
                require("Now drawing from 'AC Power'" in value['power']['output'], 'AC lost; partial evidence retained')

            snapshot()
            for bits in [12, 16]:
                for block in range(4):
                    order = ['left', 'right'] if block % 2 == 0 else ['right', 'left']
                    for slot in order:
                        producer = producers[slot]
                        label = producer + '_' + slot
                        command = [str(ROOT / PRODUCERS[producer]['path']), '37', '23', str(bits), 'flat', '20000', '1000', label]
                        began = time.monotonic()
                        process = subprocess.Popen(command, env=env, cwd=ROOT, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
                        try:
                            while True:
                                try:
                                    stdout, stderr = process.communicate(timeout=1)
                                    break
                                except subprocess.TimeoutExpired:
                                    if time.monotonic() - last_snapshot >= 10:
                                        snapshot()
                                    require(time.monotonic() - began < 600, 'Consumer timed out')
                        except BaseException:
                            try:
                                os.killpg(process.pid, signal.SIGTERM)
                            except ProcessLookupError:
                                pass
                            stdout, stderr = process.communicate()
                            (folder / 'interrupted.json').write_text(json.dumps(dict(command=command, stdout=stdout, stderr=stderr), indent=2) + '\n')
                            raise
                        if process.returncode:
                            (folder / 'failure.json').write_text(json.dumps(dict(command=command,
                                exit_code=process.returncode, stdout=stdout, stderr=stderr), indent=2) + '\n')
                            raise RuntimeError('Consumer failed; failure.json retained')
                        row = json.loads(stdout)
                        expected = dict(label=label, width=37, height=23, bits=bits, pattern='flat',
                            components=1, near=0, interleave=0, warmups=20000, iterations=1000,
                            end_to_end=True, resource_profile='successor-workspace-1GiB-memory-2GiB-v1')
                        require(all(row.get(k) == v for k, v in expected.items()), 'Consumer profile differs')
                        for operation in OPERATIONS:
                            values = row.get(operation + '_seconds', [])
                            require(len(values) == 1000 and all(type(v) in (int, float) and math.isfinite(v) and v > 0 for v in values), 'Invalid observations')
                        row.update(control=control, slot=slot, producer=producer,
                            binary_sha256=PRODUCERS[producer]['sha256'], block=block,
                            command=command, exit_code=process.returncode, stderr=stderr,
                            process_seconds=time.monotonic() - began)
                        rows.append(row)
                        raw.write(json.dumps(row) + '\n')
                        raw.flush()
                        if time.monotonic() - last_snapshot >= 10:
                            snapshot()
                print(f'{control}: p{bits} four paired blocks complete', flush=True)
            snapshot()
        results = []
        for bits in [12, 16]:
            sample = [r for r in rows if r['bits'] == bits]
            case = dict(bits=bits, width=37, height=23, pattern='flat', producers=producers, operations={})
            for operation in OPERATIONS:
                values = {slot: [v for r in sample if r['slot'] == slot for v in r[operation + '_seconds']] for slot in producers}
                medians = {slot: statistics.median(v) for slot, v in values.items()}
                pairs = []
                for block in range(4):
                    pair = {r['slot']: r for r in sample if r['block'] == block}
                    pairs.append(statistics.median(pair['right'][operation + '_seconds']) / statistics.median(pair['left'][operation + '_seconds']))
                case['operations'][operation] = dict(median_seconds=medians,
                    right_over_left=medians['right'] / medians['left'], paired_right_over_left=pairs,
                    sample_count={k: len(v) for k, v in values.items()},
                    minimum_seconds={k: min(v) for k, v in values.items()}, maximum_seconds={k: max(v) for k, v in values.items()})
            results.append(case)
        (folder / 'summary.json').write_text(json.dumps(results, indent=2) + '\n')
        all_results.append(dict(control=control, cases=results))
        print(json.dumps(dict(control=control, results=results)), flush=True)
    for producer in PRODUCERS.values():
        require(sha(ROOT / producer['path']) == producer['sha256'], 'Frozen binary changed during collection')
    end_conditions = conditions(env)
    require("Now drawing from 'AC Power'" in end_conditions['power']['output'], 'AC lost before completion')
    (output / 'complete.json').write_text(json.dumps(dict(completed=True, performance_qualified=False,
        controls=all_results, end_conditions=end_conditions), indent=2) + '\n')


if __name__ == '__main__':
    main()
