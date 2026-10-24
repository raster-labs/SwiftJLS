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
import statistics
import subprocess
import time
from build import HERE, REPO, command, sha, source_state

OPERATIONS = ('encode', 'decode', 'prepare', 'prepare_encode')
PRODUCERS = ('predecessor', 'successor')
DOCUMENTATION_HEAD = 'a0aa84dcb306c1d6a00d6a962e6d0f0c1e94f656'


def validate_build_identity(build):
    """Admit the recorded documentation HEAD only through exact source proof."""
    assert build['exit_code'] == 0 and build['source_unchanged']
    assert build['source_before'] == build['source_after']
    built = build['source_after']
    current = source_state()
    proof = {}
    for producer, root in [('predecessor', REPO.parent / 'JLSwift'), ('successor', REPO)]:
        old, now = built[producer], current[producer]
        assert not old['diff'] and not now['diff'], f'{producer}: source/package working diff is not clean'
        assert old['files'] == now['files'], f'{producer}: exact source/package files differ from build'
        allowed_heads = {old['head']} if producer == 'predecessor' else {old['head'], DOCUMENTATION_HEAD}
        assert now['head'] in allowed_heads, f'{producer}: unapproved current HEAD'
        committed = command(['git', 'diff', '--name-only', old['head'], now['head'], '--', 'Sources', 'Package.swift'], root)
        assert committed['exit_code'] == 0 and not committed['stdout'].strip(), f'{producer}: committed source/package changed'
        ancestor = command(['git', 'merge-base', '--is-ancestor', old['head'], now['head']], root)
        assert ancestor['exit_code'] == 0, f'{producer}: current HEAD is not the built revision or its descendant'
        proof[producer] = dict(build_sha=old['head'], current_head=now['head'],
            exact_source_and_package_hashes_match=True, clean_working_source_and_package_diff=True,
            committed_source_and_package_diff=committed, build_is_ancestor_of_current_head=True,
            file_count=len(now['files']))
    assert current['diagnostic'] == built['diagnostic'], 'Compiled diagnostic source/package changed'
    assert sha(REPO / 'Scripts/Benchmark/Consumer.swift') == built['diagnostic']['original-Consumer.swift'], 'Original consumer changed'
    binary = HERE / '.build/release/Benchmark'
    assert sha(binary) == build['binary_sha256'], 'Diagnostic binary changed'
    return dict(build_source=built, current_source=current, proof=proof,
        binary_sha256=build['binary_sha256'], compiled_diagnostic_hashes_match=True,
        original_consumer_hash_matches=True)


def conditions(label):
    return dict(label=label, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        power=command(['pmset', '-g', 'batt']), thermal=command(['pmset', '-g', 'therm']),
        load=command(['sysctl', '-n', 'vm.loadavg']))


def distribution(values):
    ordered = sorted(v * 1e6 for v in values)
    def percentile(p):
        return ordered[max(0, math.ceil(p * len(ordered)) - 1)]
    return dict(count=len(ordered), median_us=statistics.median(ordered),
        p05_us=percentile(.05), p25_us=percentile(.25), p75_us=percentile(.75),
        p95_us=percentile(.95), minimum_us=ordered[0], maximum_us=ordered[-1])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'results-2026-10-21')
    parser.add_argument('--check-only', action='store_true', help='Verify identity only; do not launch a benchmark or create results')
    args = parser.parse_args()
    build = json.loads((HERE / 'build.json').read_text())
    identity = validate_build_identity(build)
    binary = HERE / '.build/release/Benchmark'
    if args.check_only:
        print(json.dumps(dict(status='identity verified; no build or timing executed',
            proof=identity['proof'], binary_sha256=identity['binary_sha256']), indent=2))
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
    with (output / 'raw.jsonl').open('x') as raw, (output / 'conditions.jsonl').open('x') as state:
        for bits in (12, 16):
            for block in range(4):
                first = PRODUCERS[block % 2]
                snapshot = conditions(f'p{bits}/block{block}/before')
                state.write(json.dumps(snapshot) + '\n'); state.flush()
                assert 'AC Power' in snapshot['power']['stdout'], 'Controlled timing requires AC power'
                run_args = [str(binary), '37', '23', str(bits), 'flat', '20000', '1000', f'p{bits}-block{block}']
                start = time.monotonic()
                run = subprocess.run(run_args, cwd=REPO, env=dict(env, SWIFTJLS_SAME_PROCESS_FIRST=first),
                    capture_output=True, text=True, timeout=600)
                assert run.returncode == 0, run.stderr
                row = json.loads(run.stdout)
                expected = dict(width=37, height=23, bits=bits, pattern='flat', warmups=20000,
                    iterations=1000, end_to_end=True, components=1, near=0, interleave=0,
                    first_producer=first, resource_profile='successor-workspace-1GiB-memory-2GiB-v1')
                assert all(row.get(key) == value for key, value in expected.items())
                for producer in PRODUCERS:
                    for operation in OPERATIONS:
                        values = row[producer][operation + '_seconds']
                        assert len(values) == 1000 and all(math.isfinite(v) and v > 0 for v in values)
                row.update(block=block, command=run_args, process_seconds=time.monotonic() - start)
                records.append(row); raw.write(json.dumps(row) + '\n'); raw.flush()
                state.write(json.dumps(conditions(f'p{bits}/block{block}/after')) + '\n'); state.flush()
    summary = []
    for bits in (12, 16):
        item = dict(bits=bits, width=37, height=23, pattern='flat', operations={})
        rows = [row for row in records if row['bits'] == bits]
        for operation in OPERATIONS:
            key = operation + '_seconds'
            pooled = {producer: [v for row in rows for v in row[producer][key]] for producer in PRODUCERS}
            block_medians = {producer: [statistics.median(row[producer][key]) for row in rows] for producer in PRODUCERS}
            pred, succ = (statistics.median(pooled[producer]) for producer in PRODUCERS)
            by_order = {}
            for first in PRODUCERS:
                samples = {producer: [] for producer in PRODUCERS}
                for row in rows:
                    for i in range(1000):
                        actual_first = row['first_producer'] if i % 2 == 0 else PRODUCERS[1 - PRODUCERS.index(row['first_producer'])]
                        if actual_first == first:
                            for producer in PRODUCERS:
                                samples[producer].append(row[producer][key][i])
                by_order[first + '_first'] = {producer: distribution(samples[producer]) for producer in PRODUCERS}
            item['operations'][operation] = dict(
                distributions={producer: distribution(pooled[producer]) for producer in PRODUCERS},
                pooled_ratio=succ / pred, pooled_delta_us=(succ - pred) * 1e6,
                paired_block_ratios=[s / p for p, s in zip(block_medians['predecessor'], block_medians['successor'])],
                paired_block_delta_us=[(s - p) * 1e6 for p, s in zip(block_medians['predecessor'], block_medians['successor'])],
                block_median_us={producer: [v * 1e6 for v in block_medians[producer]] for producer in PRODUCERS},
                paired_observation_delta_us_distribution=distribution([s - p for p, s in zip(pooled['predecessor'], pooled['successor'])]),
                by_observation_order=by_order)
        summary.append(item)
    final_identity = validate_build_identity(build)
    assert final_identity == identity, 'Source identity changed during timing'
    (output / 'post-run-identity.json').write_text(json.dumps(final_identity, indent=2) + '\n')
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
