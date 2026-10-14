#!/usr/bin/env python3
"""Build only when the parent signals that the full campaign has finished."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
environment = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools')
command = ['swift', 'build', '-c', 'release', '--jobs', '4', '--package-path', str(HERE / 'wrapped')]
with (HERE / 'build.log').open('x') as log:
    result = subprocess.run(command, cwd=REPO, env=environment, stdout=log, stderr=subprocess.STDOUT)
record = dict(command=command, developer_dir=environment['DEVELOPER_DIR'], exit_code=result.returncode,
    scope='Separate diagnostic build; no production or benchmark sources changed')
if result.returncode == 0:
    binary = HERE / 'wrapped/.build/release/Benchmark'
    record['binary_sha256'] = hashlib.sha256(binary.read_bytes()).hexdigest()
    record['sync_binary_sha256'] = hashlib.sha256((HERE / 'wrapped/.build/release/SyncBenchmark').read_bytes()).hexdigest()
    for label, cmd in [('swift', ['swift', '--version']), ('sdk', ['xcrun', '--sdk', 'macosx', '--show-sdk-path']),
                       ('linkage', ['otool', '-L', str(binary)])]:
        run = subprocess.run(cmd, cwd=REPO, env=environment, capture_output=True, text=True)
        record[label] = dict(command=cmd, exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr)
(HERE / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
if result.returncode:
    raise SystemExit(result.returncode)
print(json.dumps(record, indent=2))
