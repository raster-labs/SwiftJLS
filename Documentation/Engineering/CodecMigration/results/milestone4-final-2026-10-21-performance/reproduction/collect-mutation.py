#!/usr/bin/env python3
"""Collect only the explicitly requested, source-pinned mutation experiment."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent / 'mutation'
GH = '/Users/pushparaj/.local/bin/gh'
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--run', required=True)
parser.add_argument('--revision', required=True)
args = parser.parse_args()
RUN = args.run
REVISION = args.revision


def command(*args):
    return subprocess.check_output([GH, *args], cwd=ROOT, text=True)


def require(value, message):
    if not value:
        raise ValueError(message)


run = json.loads(command('run', 'view', RUN, '--json',
    'databaseId,headSha,url,status,conclusion,createdAt,event,jobs'))
require(run['headSha'] == REVISION, 'Unexpected campaign source')
require(run['status'] == 'completed' and run['conclusion'] == 'success',
        'Campaign has not completed successfully')
require(len(run['jobs']) == 3 and all(j['conclusion'] == 'success' for j in run['jobs']),
        'Missing or failed entry-point job')
OUT.mkdir(exist_ok=True)
(OUT / 'run.json').write_text(json.dumps(run, indent=2) + '\n')
(OUT / 'run.log').write_text(command('run', 'view', RUN, '--log'))
entries = {}
for entry in ['owned', 'into', 'inspect']:
    target = OUT / entry
    if not target.exists():
        subprocess.run([GH, 'run', 'download', RUN, '--name', 'mutation-' + entry,
                        '--dir', str(target)], cwd=ROOT, check=True)
    report = json.loads((target / 'campaign-result.json').read_text())
    rows = [json.loads(line) for line in (target / 'campaign.jsonl').read_text().splitlines()]
    require(report['exit_code'] == 0 and report['failure'] is None, entry + ' failed')
    final = rows[-1]
    require(final['complete'] and final['seconds'] >= 3600, entry + ' duration incomplete')
    require(final['entry'] == entry and final['seedCount'] == 981, entry + ' profile mismatch')
    require(final['accepted'] + final['rejected'] == final['iterations'], entry + ' counts mismatch')
    require((target / 'campaign-stderr.log').stat().st_size == 0, entry + ' sanitizer stderr')
    entries[entry] = {'supervisor': report, 'final': final,
        'files': {p.name: {'sha256': hashlib.sha256(p.read_bytes()).hexdigest(),
                           'bytes': p.stat().st_size}
                  for p in sorted(target.iterdir()) if p.is_file()}}
source = {'revision': REVISION, 'run_head_sha': run['headSha'], 'run_id': int(RUN), 'run_url': run['url'],
          'artifact_hashes': {entry: record['files'] for entry, record in entries.items()},
          'entries': entries, 'status': 'passed',
          'scope': 'Three source-pinned release+ASan mutation experiments; general CI remains owner-reviewed.'}
(OUT / 'source.json').write_text(json.dumps(source, indent=2) + '\n')
print(json.dumps({entry: record['final'] for entry, record in entries.items()}, indent=2))
