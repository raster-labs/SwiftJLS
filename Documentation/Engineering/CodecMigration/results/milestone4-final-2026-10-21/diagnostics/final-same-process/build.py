#!/usr/bin/env python3
"""Fresh diagnostic build. Run only after the coordinator grants a build window."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
DEVELOPER_DIR = '/Library/Developer/CommandLineTools'
PINS = {'predecessor': '15aa75164145414f3d5ffb801401c52d40cc5bcc',
        'successor': 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'}
CONSUMER_SHA = '27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'
CONTROL_FILES = ('Package.swift', 'Sources/Benchmark/main.swift', 'original-Consumer.swift',
                 'build.py', 'compare.py', 'analyze.py', 'preflight.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=REPO):
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
        env=dict(os.environ, DEVELOPER_DIR=DEVELOPER_DIR))
    return dict(command=list(args), exit_code=result.returncode,
                stdout=result.stdout, stderr=result.stderr)


def git(args, root):
    result = command(['git', *args], root)
    assert result['exit_code'] == 0, result
    return result['stdout']


def source_state():
    state = {}
    for producer, root in [('predecessor', REPO.parent / 'JLSwift'), ('successor', REPO)]:
        head = git(['rev-parse', 'HEAD'], root).strip()
        assert head == PINS[producer], f'{producer}: exact source HEAD required'
        diff = git(['diff', 'HEAD', '--', 'Sources', 'Package.swift'], root)
        assert not diff, f'{producer}: source/package working changes'
        paths = sorted(p for p in (root / 'Sources').rglob('*') if p.is_file()) + [root / 'Package.swift']
        files = {str(p.relative_to(root)): sha(p) for p in paths}
        committed = set(git(['ls-tree', '-r', '--name-only', head, '--', 'Sources', 'Package.swift'], root).splitlines())
        assert set(files) == committed, f'{producer}: untracked, missing or extra source files'
        state[producer] = dict(head=head, diff=diff, files=files)
    state['diagnostic'] = {name: sha(HERE / name) for name in CONTROL_FILES}
    assert sha(REPO / 'Scripts/Benchmark/Consumer.swift') == CONSUMER_SHA
    assert state['diagnostic']['original-Consumer.swift'] == CONSUMER_SHA
    return state


def validate_build_identity(build):
    assert build['exit_code'] == 0 and build['source_unchanged']
    assert build['source_before'] == build['source_after']
    current = source_state()
    assert current == build['source_after'], 'Exact source or diagnostic files changed since build'
    binary = HERE / '.build/release/Benchmark'
    assert sha(binary) == build['binary_sha256'], 'Diagnostic binary changed'
    return dict(source=current, binary_sha256=build['binary_sha256'],
                exact_source_heads=True, clean_source_and_package=True,
                original_consumer_sha256=CONSUMER_SHA)


def main():
    assert not any((HERE / name).exists() for name in ('build.json', 'build.log', '.build')), 'Fresh build required'
    preparation = json.loads((HERE / 'preparation.json').read_text())
    before = source_state()
    assert before == preparation['prepared_source'], 'Source changed after preparation'
    args = ['swift', 'build', '-c', 'release', '--jobs', '4', '--package-path', str(HERE)]
    start = time.monotonic()
    with (HERE / 'build.log').open('x') as log:
        result = subprocess.run(args, cwd=REPO,
            env=dict(os.environ, DEVELOPER_DIR=DEVELOPER_DIR), stdout=log, stderr=subprocess.STDOUT)
    after = source_state()
    record = dict(command=args, developer_dir=DEVELOPER_DIR, exit_code=result.returncode,
        seconds=time.monotonic() - start, source_before=before, source_after=after,
        source_unchanged=before == after, build_log_sha256=sha(HERE / 'build.log'),
        swift=command(['swift', '--version']), sdk=command(['xcrun', '--sdk', 'macosx', '--show-sdk-path']))
    if result.returncode == 0:
        binary = HERE / '.build/release/Benchmark'
        record.update(binary=str(binary), binary_sha256=sha(binary), linkage=command(['otool', '-L', str(binary)]))
    (HERE / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    assert result.returncode == 0 and before == after, 'Build failed or source changed'
    print(json.dumps(dict(source=PINS['successor'], binary_sha256=record['binary_sha256'], exit_code=0), indent=2))


if __name__ == '__main__':
    main()
