#!/usr/bin/env python3
"""Fresh SDK/simulator and native consumer builds; reuse accepted host tests/CLI."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time

spec = importlib.util.spec_from_file_location('qualification_source', Path(__file__).with_name('qualification-source.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
identity = q.source()
if (q.OUT / 'platform-commands.json').exists():
    raise RuntimeError('Refusing to overwrite an Apple qualification attempt.')
q.write(q.OUT / 'qualification-source.json', identity)
records = []


def run(command, label, env):
    entry = dict(label=label, command=list(map(str, command)), cwd=str(q.ROOT), started_epoch=time.time())
    records.append(entry)
    q.write(q.OUT / 'platform-commands.json', records)
    with (q.OUT / (label + '.log')).open('w') as log:
        result = subprocess.run(entry['command'], cwd=q.ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    entry.update(exit_code=result.returncode, completed_epoch=time.time(), log_sha256=q.sha(q.OUT / (label + '.log')))
    q.write(q.OUT / 'platform-commands.json', records)
    q.unchanged(identity)
    if result.returncode:
        raise RuntimeError(f'{label} failed; retain this attempt and inspect its log.')
    print(label + ' passed', flush=True)


env = dict(os.environ, DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
env.pop('SDKROOT', None)
for name in ['apple-build-value', 'apple-runtime-value', 'apple-resource-value']:
    run([sys.executable, q.OUT / (name + '.py')], name, env)

env['DEVELOPER_DIR'] = '/Library/Developer/CommandLineTools'
binaries = {}
for name in ['AppleRuntimeConsumer', 'ResourceStress']:
    command = ['/usr/bin/xcrun', 'swift', 'build', '--build-system', 'swiftbuild', '-c', 'release',
               '--jobs', '4', '--package-path', q.ROOT / 'Examples' / name,
               '--scratch-path', q.OUT / 'native-consumer-build' / name]
    run(command, 'native-' + name + '-build', env)
    directory = Path(subprocess.check_output(list(map(str, command + ['--show-bin-path'])), env=env, text=True).strip())
    binary = directory / name
    binaries[name] = dict(path=str(binary), sha256=q.sha(binary), bytes=binary.stat().st_size)
    args = [binary, q.ROOT / 'Tests/SwiftJLSTests/Fixtures'] if name == 'AppleRuntimeConsumer' else [binary]
    run(args, 'host-' + name, env)

rows = json.loads((q.OUT / 'host-ResourceStress.log').read_text())
assert len(rows) == 4 and sum(x['frames'] for x in rows) == 32
assert all(x['ownedPixelAllocations'] == x['frames'] and x['suppliedPixelAllocations'] == 0 and x['reportedCopyBytes'] == 0 for x in rows)
assert 'Combined legacy mapping/HP runtime passed.' in (q.OUT / 'host-AppleRuntimeConsumer.log').read_text()
q.write(q.OUT / 'consumer-builds.json', dict(source=identity, binaries=binaries,
        host_tests_reused=q.PINS['host_receipt'], host_cli_receipts_reused=q.PINS['host_cli_receipts']))
q.unchanged(identity)
print('Apple SDK/simulator/resource and fresh native consumer preparation complete.', flush=True)
