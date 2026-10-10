#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Interleave standalone release binaries; retain every timing and environment."""
import argparse, json, pathlib, platform, statistics, subprocess, time
p = argparse.ArgumentParser()
p.add_argument('--predecessor', type=pathlib.Path, required=True)
p.add_argument('--successor', type=pathlib.Path, required=True)
p.add_argument('--output', type=pathlib.Path, required=True)
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
binaries = dict(predecessor=str(a.predecessor.resolve()), successor=str(a.successor.resolve()))
def command(*args):
    r = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return dict(command=list(args), exit_code=r.returncode, output=r.stdout)
environment = dict(platform=platform.platform(), machine=platform.machine(),
    swift=command('swift', '--version'), hardware=command('sysctl', '-n', 'hw.model', 'hw.memsize', 'machdep.cpu.brand_string'),
    thermal_start=command('pmset', '-g', 'therm'), predecessor_sha='15aa75164145414f3d5ffb801401c52d40cc5bcc',
    successor_sha=command('git', 'rev-parse', 'HEAD'),
    methodology='Lossless scalar public API, owned decode, release without sanitizers. Four alternating process blocks, each with 5 warmups and 5 timed iterations. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.')
(a.output / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
records = []
raw = a.output / 'raw.jsonl'
with raw.open('w') as log:
    for width, height in [(37, 23), (512, 512), (2048, 2048), (4096, 3073)]:
        for bits in [12, 16]:
            for pattern in ['flat', 'ramp', 'noise']:
                for block in range(4):
                    order = ['predecessor', 'successor'] if block % 2 == 0 else ['successor', 'predecessor']
                    for label in order:
                        cmd = [binaries[label], str(width), str(height), str(bits), pattern, '5', '5', label]
                        start = time.monotonic()
                        result = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
                        if result.returncode:
                            (a.output / 'failure.json').write_text(json.dumps(dict(command=cmd, exit_code=result.returncode, stderr=result.stderr), indent=2))
                            raise RuntimeError(f'{label} failed for {width}x{height} p{bits} {pattern}')
                        record = json.loads(result.stdout)
                        record.update(block=block, process_seconds=time.monotonic() - start, command=cmd)
                        records.append(record)
                        log.write(json.dumps(record) + '\n'); log.flush()
                print(f'{width}x{height} p{bits} {pattern}: four paired blocks complete', flush=True)
summary = []
for width, height, bits, pattern in dict.fromkeys((r['width'], r['height'], r['bits'], r['pattern']) for r in records):
    case = dict(width=width, height=height, bits=bits, pattern=pattern)
    for label in binaries:
        runs = [r for r in records if all(r[k] == case[k] for k in ['width', 'height', 'bits', 'pattern']) and r['label'] == label]
        metrics = dict(encoded_bytes=runs[0]['encoded_bytes'], peak_process_rss_bytes=max(r['peak_process_rss_bytes'] for r in runs))
        for operation in ['encode', 'decode']:
            values = sorted(v for r in runs for v in r[operation + '_seconds'])
            metrics[operation] = dict(median_seconds=statistics.median(values), p95_seconds=values[int(0.95 * (len(values) - 1))],
                min_seconds=min(values), max_seconds=max(values), samples=len(values), megapixels_per_second=width * height / statistics.median(values) / 1e6)
        case[label] = metrics
    summary.append(case)
(a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(a.output / 'thermal-end.json').write_text(json.dumps(command('pmset', '-g', 'therm'), indent=2) + '\n')
