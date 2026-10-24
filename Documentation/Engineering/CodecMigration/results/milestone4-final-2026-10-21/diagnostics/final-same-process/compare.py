#!/usr/bin/env python3
"""Optional diagnostic. Do not build or time until parent authorizes it.

Both codecs coexist in one process with original public async wrappers. Alternate
producer order every observation, reversing initial order over four processes.
Raw timings remain authoritative. Results never replace the full campaign.
"""
import argparse
import json
import math
import os
from pathlib import Path
import subprocess
import time
from build import HERE, REPO, command, sha, validate_build_identity
from analyze import CASES, OPERATIONS, PRODUCERS, analyze

def conditions(label):
    return dict(label=label, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        power=command(['pmset', '-g', 'batt']), thermal=command(['pmset', '-g', 'therm']),
        load=command(['sysctl', '-n', 'vm.loadavg']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'results')
    parser.add_argument('--check-only', action='store_true', help='Verify identity only; do not launch a benchmark or create results')
    args = parser.parse_args()
    build = json.loads((HERE / 'build.json').read_text())
    identity = validate_build_identity(build)
    binary = HERE / '.build/release/Benchmark'
    if args.check_only:
        print(json.dumps(dict(status='identity verified; no build or timing executed',
            source=identity['source'], binary_sha256=identity['binary_sha256']), indent=2))
        return
    assert not any(os.environ.get(key) for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE'])
    output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, SWIFTJLS_BENCHMARK_END_TO_END='1')
    metadata = dict(binary_sha256=sha(binary), source=build['source_after'], identity=identity,
        runner_sha256=sha(Path(__file__)), caller_context='Original top-level caller and nonisolated async wrappers, no extra public adapter frame.',
        methodology='Four processes per case; predecessor/successor first alternates by block and every observation. 20000 warmups and 1000 retained observations per producer per block. Original construction, verification and timing boundaries.',
        limitation='Both library objects and both producer images coexist; binary layout, allocator/cache interaction and execution context differ from the main separate-process campaign. Combined RSS is not producer workspace. No automatic waiver.')
    (output / 'environment.json').write_text(json.dumps(metadata, indent=2) + '\n')
    records = []
    (output / 'commands').mkdir()
    with (output / 'raw.jsonl').open('x') as raw, (output / 'conditions.jsonl').open('x') as state:
        for bits, pattern in CASES:
            for block in range(4):
                first = PRODUCERS[block % 2]
                snapshot = conditions(f'p{bits}-{pattern}/block{block}/before')
                state.write(json.dumps(snapshot) + '\n'); state.flush()
                assert 'AC Power' in snapshot['power']['stdout'], 'Controlled timing requires AC power'
                run_args = [str(binary), '37', '23', str(bits), pattern, '20000', '1000', f'p{bits}-{pattern}-block{block}']
                start = time.monotonic()
                run = subprocess.run(run_args, cwd=REPO, env=dict(env, SWIFTJLS_SAME_PROCESS_FIRST=first),
                    capture_output=True, text=True, timeout=600)
                captured = dict(command=run_args, exit_code=run.returncode, stdout=run.stdout,
                    stderr=run.stderr, seconds=time.monotonic() - start)
                (output / 'commands' / f'p{bits}-{pattern}-block{block}.json').write_text(json.dumps(captured, indent=2) + '\n')
                assert run.returncode == 0, run.stderr
                row = json.loads(run.stdout)
                expected = dict(width=37, height=23, bits=bits, pattern=pattern, warmups=20000,
                    iterations=1000, end_to_end=True, components=1, near=0, interleave=0,
                    first_producer=first, resource_profile='successor-workspace-1GiB-memory-2GiB-v1')
                assert all(row.get(key) == value for key, value in expected.items())
                for producer in PRODUCERS:
                    for operation in OPERATIONS:
                        values = row[producer][operation + '_seconds']
                        assert len(values) == 1000 and all(math.isfinite(v) and v > 0 for v in values)
                row.update(block=block, command=run_args, process_seconds=time.monotonic() - start)
                records.append(row); raw.write(json.dumps(row) + '\n'); raw.flush()
                after = conditions(f'p{bits}-{pattern}/block{block}/after')
                state.write(json.dumps(after) + '\n'); state.flush()
                assert 'AC Power' in after['power']['stdout'], 'Power changed during timing'

    summary = analyze(records)
    final_identity = validate_build_identity(build)
    assert final_identity == identity, 'Source identity changed during timing'
    (output / 'post-run-identity.json').write_text(json.dumps(final_identity, indent=2) + '\n')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
