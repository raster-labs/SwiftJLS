#!/usr/bin/env python3
"""Execute both predeclared short self-controls once; no outcome-based repeats."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
readiness = json.loads((HERE / 'readiness.json').read_text())
assert hashlib.sha256((HERE / 'run.py').read_bytes()).hexdigest() == readiness['runner_sha256']
assert not (HERE / 'results').exists()
records = []
for control in readiness['control_order']:
    args = [sys.executable, str(HERE / 'run.py'), '--control', control,
            '--output', str(HERE / 'results' / control)]
    start = time.monotonic()
    with (HERE / (control + '.log')).open('x') as log:
        result = subprocess.run(args, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
    records.append(dict(control=control, command=args, exit_code=result.returncode,
                        seconds=time.monotonic() - start, log=control + '.log'))
    (HERE / 'commands.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(records[-1]), flush=True)
    assert result.returncode == 0, 'Control failed; preserve partial evidence, no automatic retry'
print('Both short self-controls completed; no automatic acceptance', flush=True)
