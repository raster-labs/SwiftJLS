#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Interleave standalone release binaries; retain every timing and environment."""
import argparse, hashlib, json, pathlib, platform, statistics, subprocess, time
p = argparse.ArgumentParser()
p.add_argument('--predecessor', type=pathlib.Path, required=True)
p.add_argument('--successor', type=pathlib.Path, required=True)
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('--colour', action='store_true', help='RGB NEAR 0/3, all three interleaves')
p.add_argument('--smoke', action='store_true', help='Correctness/harness check at 37x23 only; not performance qualification')
a = p.parse_args()
a.output.mkdir(parents=True, exist_ok=True)
binaries = dict(predecessor=str(a.predecessor.resolve()), successor=str(a.successor.resolve()))
def command(*args):
    r = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    return dict(command=list(args), exit_code=r.returncode, output=r.stdout)
environment = dict(platform=platform.platform(), machine=platform.machine(), smoke_only=a.smoke,
    consumer_sha256=hashlib.sha256(pathlib.Path(__file__).with_name('Consumer.swift').read_bytes()).hexdigest(),
    runner_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
    binary_sha256={label: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() for label,path in binaries.items()},
    power_start=command('pmset', '-g', 'batt'), load_start=command('sysctl', '-n', 'vm.loadavg'),
    swift=command('swift', '--version'), hardware=command('sysctl', '-n', 'hw.model', 'hw.memsize', 'machdep.cpu.brand_string'),
    thermal_start=command('pmset', '-g', 'therm'), predecessor_sha='15aa75164145414f3d5ffb801401c52d40cc5bcc',
    successor_sha=command('git', 'rev-parse', 'HEAD'),
    methodology=('RGB NEAR 0/3, all three interleaves, public API. ' if a.colour else 'Lossless scalar public API. ') + 'Owned decode, release without sanitizers. Four alternating process blocks, each with 5 warmups and 5 timed iterations. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.')
(a.output / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
records = []
raw = a.output / 'raw.jsonl'
with raw.open('w') as log:
    profiles = [(3, near, mode) for near in [0, 3] for mode in [0, 1, 2]] if a.colour else [(1, 0, 0)]
    sizes = [(37,23)] if a.smoke else [(37,23),(512,512),(2048,2048),(4096,3073)]
    cases = [(w,h,bits,pattern,c,n,i) for w,h in sizes
             for bits in [12,16] for pattern in ['flat','ramp','noise'] for c,n,i in profiles]
    for width, height, bits, pattern, components, near, interleave in cases:
        for block in range(4):
            order = ['predecessor', 'successor'] if block % 2 == 0 else ['successor', 'predecessor']
            for label in order:
                cmd = [binaries[label], str(width), str(height), str(bits), pattern, '5', '5', label]
                if a.colour: cmd += [str(components), str(near), str(interleave)]
                start = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=600)
                if result.returncode:
                    (a.output / 'failure.json').write_text(json.dumps(dict(command=cmd, exit_code=result.returncode, stderr=result.stderr), indent=2))
                    raise RuntimeError(f'{label} failed for {width}x{height} p{bits} {pattern}')
                record = json.loads(result.stdout)
                record.update(components=components, near=near, interleave=interleave, block=block, process_seconds=time.monotonic() - start, command=cmd)
                records.append(record)
                log.write(json.dumps(record) + '\n'); log.flush()
        print(f'{width}x{height} p{bits} {pattern} c{components} n{near} i{interleave}: four paired blocks complete', flush=True)
summary = []
keys = ['width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave']
for values in dict.fromkeys(tuple(r[k] for k in keys) for r in records):
    case = dict(zip(keys, values))
    width, height = case['width'], case['height']
    for label in binaries:
        runs = [r for r in records if all(r[k] == case[k] for k in keys) and r['label'] == label]
        metrics = dict(encoded_bytes=runs[0]['encoded_bytes'], peak_process_rss_bytes=max(r['peak_process_rss_bytes'] for r in runs))
        for operation in ['encode', 'decode']:
            values = sorted(v for r in runs for v in r[operation + '_seconds'])
            metrics[operation] = dict(median_seconds=statistics.median(values), p95_seconds=values[int(0.95 * (len(values) - 1))],
                min_seconds=min(values), max_seconds=max(values), samples=len(values), megapixels_per_second=width * height / statistics.median(values) / 1e6)
        case[label] = metrics
    summary.append(case)
(a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(a.output / 'thermal-end.json').write_text(json.dumps(command('pmset', '-g', 'therm'), indent=2) + '\n')

(a.output / 'power-end.json').write_text(json.dumps(command('pmset', '-g', 'batt'), indent=2) + '\n')
(a.output / 'load-end.json').write_text(json.dumps(command('sysctl', '-n', 'vm.loadavg'), indent=2) + '\n')
