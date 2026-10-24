#!/usr/bin/env python3
"""Source-only preparation: run only after parent authorizes a build window."""
import hashlib
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=REPO):
    run = subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                         env=dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools'))
    return dict(command=list(args), exit_code=run.returncode, stdout=run.stdout, stderr=run.stderr)


def source_state():
    state = {}
    for label, root in [('predecessor', REPO.parent / 'JLSwift'), ('successor', REPO)]:
        paths = sorted(p for p in (root / 'Sources').rglob('*') if p.is_file()) + [root / 'Package.swift']
        state[label] = dict(head=command(['git', 'rev-parse', 'HEAD'], root)['stdout'].strip(),
            diff=command(['git', 'diff', 'HEAD', '--', 'Sources', 'Package.swift'], root)['stdout'],
            files={str(p.relative_to(root)): sha(p) for p in paths})
    state['diagnostic'] = {str(p.relative_to(HERE)): sha(p) for p in
        [HERE / 'Package.swift', HERE / 'Sources/Benchmark/main.swift', HERE / 'original-Consumer.swift']}
    return state


def main():
    preparation = json.loads((HERE / 'preparation.json').read_text())
    before = source_state()
    assert before['predecessor']['head'] == preparation['predecessor_checkpoint']
    assert not before['predecessor']['diff']
    assert sha(REPO / 'Scripts/Benchmark/Consumer.swift') == preparation['source_consumer_sha256']
    args = ['swift', 'build', '-c', 'release', '--jobs', '4', '--package-path', str(HERE)]
    env = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools')
    with (HERE / 'build.log').open('x') as log:
        result = subprocess.run(args, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
    after = source_state()
    record = dict(command=args, developer_dir=env['DEVELOPER_DIR'], exit_code=result.returncode,
        source_before=before, source_after=after, source_unchanged=before == after,
        swift=command(['swift', '--version']), sdk=command(['xcrun', '--sdk', 'macosx', '--show-sdk-path']))
    if result.returncode == 0:
        binary = HERE / '.build/release/Benchmark'
        record.update(binary_sha256=sha(binary), linkage=command(['otool', '-L', str(binary)]))
    (HERE / 'build.json').write_text(json.dumps(record, indent=2) + '\n')
    assert result.returncode == 0 and before == after, 'Build failed or source changed during build'
    print(json.dumps(dict(exit_code=result.returncode, binary_sha256=record['binary_sha256'],
        source=before['successor']['head'], source_dirty=bool(before['successor']['diff'])), indent=2))


if __name__ == '__main__':
    main()
