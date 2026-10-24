#!/usr/bin/env python3
"""Run only the workspace archive adapter and retain every attempt; no publication."""
import datetime
import importlib.util
import json
from pathlib import Path
import traceback

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / 'diagnostics/archive-validation'
OUT.mkdir(parents=True, exist_ok=True)
index = 1
while (OUT / f'workspace-preflight-attempt-{index}.json').exists():
    index += 1
result_path = OUT / f'workspace-preflight-attempt-{index}.json'
log_path = OUT / f'workspace-preflight-attempt-{index}.log'
plan = json.loads((HERE / 'archive-plan.json').read_text())
selected = {}
record = dict(started_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    source_commit=plan['source_commit'], validator='archive-evidence.py:validate_workspace',
    scope='Focused final workspace archive-admission check only; no publication, bootstrap, measurements, or acceptance')

def add(path, relative=None):
    path = Path(path).resolve()
    key = relative if relative is not None else str(path.relative_to(HERE))
    value = dict(source=str(path.relative_to(ROOT)), bytes=path.stat().st_size)
    if key in selected and selected[key] != value:
        raise ValueError('Conflicting selected archive name: ' + key)
    selected[key] = value

try:
    spec = importlib.util.spec_from_file_location('archive_evidence', HERE / 'archive-evidence.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    record['adapter_sha256'] = module.sha(HERE / 'archive-evidence.py')
    summary = module.validate_workspace(plan['source_commit'], add)
    record.update(passed=True, profile_count=summary['profile_count'],
                  binary_sha256=summary['binary_sha256'], classifier_sha256=summary['classifier_sha256'])
    log = 'Focused validate_workspace completed successfully. No archive was published.\n'
except Exception as error:
    record.update(passed=False, error=repr(error))
    log = traceback.format_exc()
finally:
    record.update(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  selected_file_count=len(selected), selected_files=selected)
    with result_path.open('x') as stream:
        json.dump(record, stream, indent=2); stream.write('\n')
    with log_path.open('x') as stream:
        stream.write(log)
print(json.dumps({key: record.get(key) for key in ['passed', 'source_commit', 'profile_count', 'selected_file_count', 'error']}))
print(str(result_path.relative_to(ROOT)))
raise SystemExit(0 if record['passed'] else 1)
