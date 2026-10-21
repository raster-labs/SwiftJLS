#!/usr/bin/env python3
"""Run only after the main campaign and the separately authorised build finish.

Compare the original predecessor, matched preserved synchronous/async core
boundaries, and unchanged successor. Four ordered blocks, 20000 warmups and 1000
observations per producer for each scalar 37x23 flat 12/16-bit case. This is a
separate diagnostic, never a replacement baseline or automatic waiver.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PRODUCERS = ('original', 'sync_core', 'async_core', 'successor')
OPERATIONS = ('encode', 'decode', 'prepare', 'prepare_encode')
ORDERS = [('original', 'sync_core', 'async_core', 'successor'),
          ('successor', 'async_core', 'sync_core', 'original'),
          ('sync_core', 'original', 'successor', 'async_core'),
          ('async_core', 'successor', 'original', 'sync_core')]


def command(args):
    run = subprocess.run(args, capture_output=True, text=True, timeout=20)
    return dict(command=list(args), exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr)


def conditions(label):
    return dict(label=label, utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        power=command(['pmset', '-g', 'batt']), thermal=command(['pmset', '-g', 'therm']),
        load=command(['sysctl', '-n', 'vm.loadavg']))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=HERE / 'results')
    args = parser.parse_args()
    build = json.loads((HERE / 'build.json').read_text())
    assert build['exit_code'] == 0
    preparation = json.loads((HERE / 'preparation.json').read_text())
    for path, digest in preparation['files'].items():
        assert sha(HERE / path) == digest, f'Diagnostic source changed: {path}'
    assert sha(REPO / 'Scripts/Benchmark/Consumer.swift') == preparation['files']['original-Consumer.swift']
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == preparation['source_checkpoint']
    assert not subprocess.check_output(['git', 'diff', '--name-only', '--', 'Sources'], cwd=REPO, text=True).strip()
    assert subprocess.check_output(['git', '-C', str(REPO.parent / 'JLSwift'), 'rev-parse', 'HEAD'], text=True).strip() == preparation['predecessor_checkpoint']
    binaries = dict(original=REPO / 'work/m4-benchmark/predecessor/.build/release/Benchmark',
        sync_core=HERE / 'wrapped/.build/release/SyncBenchmark',
        async_core=HERE / 'wrapped/.build/release/Benchmark',
        successor=REPO / 'work/m4-benchmark/successor/.build/release/Benchmark')
    hashes = {label: sha(path) for label, path in binaries.items()}
    assert hashes['async_core'] == build['binary_sha256']
    assert hashes['sync_core'] == build['sync_binary_sha256']
    final = json.loads((REPO / 'work/m4-final-2026-10-14/powered/scalar/environment.json').read_text())
    assert hashes['original'] == final['binary_sha256']['predecessor']
    assert hashes['successor'] == final['binary_sha256']['successor']
    assert final['successor_sha']['output'].strip() == preparation['source_checkpoint']
    assert not any(os.environ.get(key) for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE'])
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, SWIFTJLS_BENCHMARK_END_TO_END='1')
    metadata = dict(source_checkpoint=preparation['source_checkpoint'], predecessor_checkpoint=preparation['predecessor_checkpoint'],
        binary_sha256=hashes, runner_sha256=sha(Path(__file__)), preparation=preparation,
        caller_context='Unchanged top-level main-actor caller; existing asynchronous wrappers use the generic executor.',
        methodology='Four process blocks using recorded orders, 20000 warmups and 1000 timed observations each. Scalar37x23 flat12/16. Initial sample checks outside timing; source preparation and preparation-plus-encode retain original boundaries.',
        orders=ORDERS, acceptance='No decision or waiver. Async versus matched sync adapter measures the added async boundary beyond an ordinary module call; a thread hop per call is not established.')
    (output / 'environment.json').write_text(json.dumps(metadata, indent=2) + '\n')
    records = []
    with (output / 'raw.jsonl').open('x') as raw, (output / 'conditions.jsonl').open('x') as state:
        for bits in (12, 16):
            # Exact predecessor byte equality is established outside retained
            # timed observations; all four normal consumers verify samples.
            exports = {}
            for label in PRODUCERS:
                export = output / f'preflight-p{bits}-{label}.jls'
                args = [str(binaries[label]), '37', '23', str(bits), 'flat', '0', '1', label]
                check = subprocess.run(args, cwd=REPO, env=dict(env, SWIFTJLS_BENCHMARK_EXPORT=str(export)),
                    capture_output=True, text=True, timeout=600)
                (output / f'preflight-p{bits}-{label}.json').write_text(json.dumps(dict(command=args,
                    exit_code=check.returncode, stdout=check.stdout, stderr=check.stderr), indent=2) + '\n')
                assert check.returncode == 0, f'Preflight failed: p{bits}/{label}'
                exports[label] = export.read_bytes()
            assert exports['original'] == exports['sync_core'] == exports['async_core'], 'Wrapper changed predecessor encoded bytes'
            for block, order in enumerate(ORDERS):
                for label in order:
                    snapshot = conditions(f'p{bits}/block{block}/{label}/before')
                    state.write(json.dumps(snapshot) + '\n'); state.flush()
                    args = [str(binaries[label]), '37', '23', str(bits), 'flat', '20000', '1000', label]
                    start = time.monotonic()
                    run = subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True, timeout=600)
                    assert run.returncode == 0, f'Consumer failed: {label}: {run.stderr}'
                    row = json.loads(run.stdout)
                    expected = dict(label=label, width=37, height=23, bits=bits, pattern='flat',
                        components=1, near=0, interleave=0, warmups=20000, iterations=1000, end_to_end=True,
                        resource_profile='successor-workspace-1GiB-memory-2GiB-v1')
                    assert all(row.get(key) == value for key, value in expected.items()), 'Wrong consumer profile'
                    for operation in OPERATIONS:
                        values = row[operation + '_seconds']
                        assert len(values) == 1000 and all(math.isfinite(value) and value > 0 for value in values)
                    row.update(block=block, command=args, process_seconds=time.monotonic() - start)
                    records.append(row); raw.write(json.dumps(row) + '\n'); raw.flush()
                    state.write(json.dumps(conditions(f'p{bits}/block{block}/{label}/after')) + '\n'); state.flush()
    summary = []
    for bits in (12, 16):
        item = dict(width=37, height=23, bits=bits, pattern='flat', operations={})
        for operation in OPERATIONS:
            medians = {label: statistics.median(value for row in records if row['bits'] == bits and row['label'] == label
                for value in row[operation + '_seconds']) for label in PRODUCERS}
            comparisons = {}
            for numerator, denominator in [('async_core', 'sync_core'), ('sync_core', 'original'), ('async_core', 'original'), ('successor', 'original'), ('successor', 'async_core')]:
                ratios = []
                deltas = []
                for block in range(4):
                    group = {row['label']: statistics.median(row[operation + '_seconds'])
                        for row in records if row['bits'] == bits and row['block'] == block}
                    ratios.append(group[numerator] / group[denominator])
                    deltas.append((group[numerator] - group[denominator]) * 1e6)
                comparisons[numerator + '_over_' + denominator] = dict(pooled_ratio=medians[numerator] / medians[denominator],
                    pooled_delta_us=(medians[numerator] - medians[denominator]) * 1e6,
                    paired_block_ratios=ratios, paired_block_delta_us=deltas)
            item['operations'][operation] = dict(median_us={label: value * 1e6 for label, value in medians.items()}, comparisons=comparisons)
        summary.append(item)
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2))


if __name__ == '__main__':
    main()
