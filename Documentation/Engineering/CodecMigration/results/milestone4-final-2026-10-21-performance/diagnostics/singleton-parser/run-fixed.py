#!/usr/bin/env python3
"""Run the two predeclared comparisons once, in the agreed fixed order."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
readiness = json.loads((HERE / 'measurement-readiness.json').read_text())
assert hashlib.sha256((HERE / 'run-comparisons.py').read_bytes()).hexdigest() == readiness['runner_sha256']
assert not (HERE / 'timings').exists(), 'Fresh two-comparison run required'
records = []
for index, name in enumerate(readiness['comparison_order']):
    mode, reference = name.split('-')
    args = [sys.executable, str(HERE / 'run-comparisons.py'), '--mode', mode,
            '--reference', reference, '--output', str(HERE / 'timings' / name)]
    start = time.monotonic()
    with (HERE / (name + '.log')).open('x') as log:
        result = subprocess.run(args, cwd=HERE, stdout=log, stderr=subprocess.STDOUT)
    records.append(dict(comparison=name, command=args, exit_code=result.returncode,
                        seconds=time.monotonic() - start, log=name + '.log'))
    (HERE / 'comparison-commands.json').write_text(json.dumps(records, indent=2) + '\n')
    print(json.dumps(records[-1]), flush=True)
    assert result.returncode == 0, 'Comparison failed; partial evidence retained; no automatic retry'
print('Both fixed comparisons completed; no automatic acceptance', flush=True)
