#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Interleave standalone release binaries; retain every timing and environment."""
import argparse, hashlib, json, math, os, pathlib, platform, statistics, subprocess, time
p = argparse.ArgumentParser()
p.add_argument('--predecessor', type=pathlib.Path, required=True)
p.add_argument('--successor', type=pathlib.Path, required=True)
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('--colour', action='store_true', help='RGB NEAR 0/3, all three interleaves')
p.add_argument('--smoke', action='store_true', help='Correctness/harness check at 37x23 only; not performance qualification')
p.add_argument('--end-to-end', action='store_true', help='Also time preparation and preparation plus encode from identical canonical samples')
p.add_argument('--cases', type=pathlib.Path, help='JSON array selecting cases from the standard grid: [width,height,bits,pattern,components,near,interleave]')
a = p.parse_args()
profiles = [(3, near, mode) for near in [0, 3] for mode in [0, 1, 2]] if a.colour else [(1, 0, 0)]
sizes = [(37,23)] if a.smoke else [(37,23),(512,512),(2048,2048),(4096,3073)]
cases = [(w,h,bits,pattern,c,n,i) for w,h in sizes
         for bits in [12,16] for pattern in ['flat','ramp','noise'] for c,n,i in profiles]
selection_bytes = None
if a.cases:
    try:
        selection_bytes = a.cases.read_bytes()
        selected = json.loads(selection_bytes)
        if not isinstance(selected, list) or not selected:
            raise ValueError('selection must be a nonempty array')
        for case in selected:
            if not isinstance(case, list) or len(case) != 7 or any(
                    type(value) is not (str if index == 3 else int) for index, value in enumerate(case)):
                raise ValueError('invalid case fields')
            if tuple(case) not in cases:
                raise ValueError('case is outside the selected standard grid')
        selected = [tuple(case) for case in selected]
        if len(set(selected)) != len(selected):
            raise ValueError('duplicate case')
        cases = [case for case in cases if case in selected]
    except (OSError, ValueError, TypeError) as error:
        p.error(f'Invalid --cases: {error}')
if any(os.environ.get(key) for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE']):
    p.error('Unset benchmark export/decode variables before collecting timings')
if a.output.exists() and any(a.output.iterdir()):
    p.error('Use a new or empty output directory; previous evidence must not be overwritten')
a.output.mkdir(parents=True, exist_ok=True)
binaries = dict(predecessor=str(a.predecessor.resolve()), successor=str(a.successor.resolve()))
consumer_env = dict(os.environ, SWIFTJLS_BENCHMARK_END_TO_END='1' if a.end_to_end else '0')
def command(*args):
    try:
        r = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except FileNotFoundError:
        return dict(command=list(args), exit_code=None, unavailable=True, output='Command unavailable on this host')
    return dict(command=list(args), exit_code=r.returncode, output=r.stdout)
environment = dict(caller_context='main-actor caller', platform=platform.platform(), machine=platform.machine(), smoke_only=a.smoke,
    selected_cases=cases, case_selection_sha256=hashlib.sha256(selection_bytes).hexdigest() if selection_bytes is not None else None,
    end_to_end=a.end_to_end, performance_qualified=False,
    consumer_sha256=hashlib.sha256(pathlib.Path('Scripts/Benchmark/Consumer.swift').read_bytes()).hexdigest(),
    runner_sha256=hashlib.sha256(pathlib.Path(__file__).read_bytes()).hexdigest(),
    binary_sha256={label: hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest() for label,path in binaries.items()},
    power_start=command('pmset', '-g', 'batt'), load_start=command('sysctl', '-n', 'vm.loadavg'),
    swift=command('swift', '--version'), hardware=command('sysctl', '-n', 'hw.model', 'hw.memsize', 'machdep.cpu.brand_string'),
    thermal_start=command('pmset', '-g', 'therm'), predecessor_sha='15aa75164145414f3d5ffb801401c52d40cc5bcc',
    successor_sha=command('git', 'rev-parse', 'HEAD'),
    methodology=('RGB public API; selected_cases records the executed subset of the NEAR 0/3, three-interleave grid. ' if a.colour else 'Lossless scalar public API. ') + 'Owned decode, release without sanitizers. Four alternating process blocks, each with 1000 warmups and 1000 timed iterations; small-image steady-state repeat. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.',
    preparation_boundary=('Canonical UInt16 fixture generation excluded; public input allocation, layout conversion, descriptor construction and input validation included. Preparation-plus-encode is measured together, not a sum of medians. Destruction of the prepared input is outside timing. Canonical and reusable inputs remain in whole-process RSS.' if a.end_to_end else 'Source preparation excluded from encode timing.'))
(a.output / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
records = []
raw = a.output / 'raw.jsonl'
with raw.open('w') as log:
    for width, height, bits, pattern, components, near, interleave in cases:
        for block in range(4):
            order = ['predecessor', 'successor'] if block % 2 == 0 else ['successor', 'predecessor']
            for label in order:
                cmd = [binaries[label], str(width), str(height), str(bits), pattern, '1000', '1000', label]
                if a.colour: cmd += [str(components), str(near), str(interleave)]
                start = time.monotonic()
                result = subprocess.run(cmd, text=True, capture_output=True, timeout=600, env=consumer_env)
                if result.returncode:
                    (a.output / 'failure.json').write_text(json.dumps(dict(command=cmd, exit_code=result.returncode, stderr=result.stderr), indent=2))
                    raise RuntimeError(f'{label} failed for {width}x{height} p{bits} {pattern}')
                record = json.loads(result.stdout)
                expected = dict(label=label, width=width, height=height, bits=bits,
                    resource_profile='successor-workspace-1GiB-memory-2GiB-v1',
                    pattern=pattern, components=components, near=near, interleave=interleave,
                    warmups=1000, iterations=1000)
                if any(record.get(key) != value for key, value in expected.items()):
                    raise RuntimeError('Consumer profile mismatch')
                operations = ['encode', 'decode'] + (['prepare', 'prepare_encode'] if a.end_to_end else [])
                if record.get('end_to_end') != a.end_to_end:
                    raise RuntimeError('Consumer timing mode mismatch; rebuild both binaries from Consumer.swift')
                for operation in operations:
                    values = record.get(operation + '_seconds', [])
                    if len(values) != 1000 or any(not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values):
                        raise RuntimeError(f'Missing/invalid {operation} observations from {label}')
                if a.end_to_end and any(total < preparation for total, preparation in
                        zip(record['prepare_encode_seconds'], record['prepare_seconds'])):
                    raise RuntimeError('Preparation-plus-encode cannot be shorter than preparation')
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
        for operation in ['encode', 'decode'] + (['prepare', 'prepare_encode'] if a.end_to_end else []):
            values = sorted(v for r in runs for v in r[operation + '_seconds'])
            metrics[operation] = dict(median_seconds=statistics.median(values), p95_seconds=values[int(0.95 * (len(values) - 1))],
                min_seconds=min(values), max_seconds=max(values), samples=len(values), megapixels_per_second=width * height / statistics.median(values) / 1e6)
        case[label] = metrics
    case['successor_over_predecessor'] = {
        operation: case['successor'][operation]['median_seconds'] / case['predecessor'][operation]['median_seconds']
        for operation in ['encode', 'decode'] + (['prepare', 'prepare_encode'] if a.end_to_end else [])}
    case['performance_qualified'] = False
    summary.append(case)
(a.output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
(a.output / 'thermal-end.json').write_text(json.dumps(command('pmset', '-g', 'therm'), indent=2) + '\n')

(a.output / 'power-end.json').write_text(json.dumps(command('pmset', '-g', 'batt'), indent=2) + '\n')
(a.output / 'load-end.json').write_text(json.dumps(command('sysctl', '-n', 'vm.loadavg'), indent=2) + '\n')
