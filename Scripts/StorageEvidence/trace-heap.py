#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Retain ordinary-build allocation stacks for the real cross-codec routes.

This collects evidence, not a zero-copy verdict: stack classification and copy
byte accounting are separate from process-wide allocation totals.
"""
import argparse
import hashlib
import json
import pathlib
import subprocess

parser = argparse.ArgumentParser()
parser.add_argument('--binary', type=pathlib.Path, required=True)
parser.add_argument('--output', type=pathlib.Path, required=True)
parser.add_argument('--scope', default='Whole-process real cross-codec consumer including setup and runtime allocations; not a zero-copy verdict.')
parser.add_argument('arguments', nargs=argparse.REMAINDER)
args = parser.parse_args()
output = args.output.resolve()
output.mkdir(parents=True, exist_ok=True)
binary = args.binary.resolve()
commands = []

def run(command, name):
    result = subprocess.run(command, capture_output=True, timeout=180)
    (output / (name + '.stdout')).write_bytes(result.stdout)
    (output / (name + '.stderr')).write_bytes(result.stderr)
    commands.append(dict(command=command, exit_code=result.returncode))
    (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
    result.check_returncode()
    return result.stdout

version = run(['heaptrack', '--version'], 'version').decode().strip()
run(['heaptrack', '-o', str(output / 'allocations'), str(binary), *(args.arguments[1:] if args.arguments[:1] == ['--'] else args.arguments)], 'consumer')
profiles = list(output.glob('allocations*.gz')) + list(output.glob('allocations*.zst'))
if len(profiles) != 1:
    raise RuntimeError('Expected exactly one allocator profile: ' + str(profiles))
profile = profiles[0]
report = run(['heaptrack_print', '-f', str(profile), '-n', '1000', '-s', '1000',
              '-H', str(output / 'sizes.tsv'), '-F', str(output / 'allocation-stacks.txt')], 'analysis')
demangled = subprocess.run(['swift', 'demangle'], input=report, capture_output=True, check=True)
(output / 'analysis-demangled.txt').write_bytes(demangled.stdout)
# A broken injection must not pass merely because the consumer exited normally.
if b'calls to allocation functions' not in report or not (output / 'sizes.tsv').stat().st_size:
    raise RuntimeError('Allocation data missing')
summary = dict(tool=version, binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
               profile=profile.name, profile_sha256=hashlib.sha256(profile.read_bytes()).hexdigest(),
               build='Swift release with debug symbols, no sanitizers',
               scope=args.scope,
               commands=commands)
(output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary, indent=2))
