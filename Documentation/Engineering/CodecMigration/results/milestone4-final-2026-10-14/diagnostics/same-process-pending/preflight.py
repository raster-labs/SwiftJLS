#!/usr/bin/env python3
"""Correctness-only fixture checks: zero warmups, one observation, no timing qualification."""
import json
import os
from pathlib import Path
import subprocess
from build import HERE, REPO, sha, source_state
from compare import conditions

build = json.loads((HERE / 'build.json').read_text())
assert build['exit_code'] == 0 and build['source_unchanged']
assert source_state() == build['source_after']
binary = HERE / '.build/release/Benchmark'
assert sha(binary) == build['binary_sha256']
output = HERE / 'preflight-correctness-only'
output.mkdir(exist_ok=False)
records = []
for bits, first in [(12, 'predecessor'), (16, 'successor')]:
    args = [str(binary), '37', '23', str(bits), 'flat', '0', '1', f'correctness-only-p{bits}']
    before = conditions(f'p{bits}/before')
    env = dict(os.environ, SWIFTJLS_BENCHMARK_END_TO_END='1', SWIFTJLS_SAME_PROCESS_FIRST=first)
    for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE']:
        env.pop(key, None)
    run = subprocess.run(args, cwd=REPO, env=env, capture_output=True, text=True, timeout=60)
    record = dict(bits=bits, purpose='Untimed correctness preflight only; emitted single-observation durations are not performance evidence.',
        command=args, before=before, after=conditions(f'p{bits}/after'),
        exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr)
    (output / f'p{bits}.json').write_text(json.dumps(record, indent=2) + '\n')
    assert run.returncode == 0, run.stderr
    row = json.loads(run.stdout)
    assert row['warmups'] == 0 and row['iterations'] == 1 and row['bits'] == bits
    records.append(dict(bits=bits, exit_code=run.returncode, own_and_cross_decode_sample_verification='passed',
        predecessor_encoded_bytes=row['predecessor']['encoded_bytes'], successor_encoded_bytes=row['successor']['encoded_bytes']))
summary = dict(purpose='Correctness only, not performance qualification', source=build['source_after']['successor']['head'],
    binary_sha256=build['binary_sha256'], records=records)
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
