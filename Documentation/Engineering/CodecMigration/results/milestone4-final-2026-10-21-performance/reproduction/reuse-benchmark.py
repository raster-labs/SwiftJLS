#!/usr/bin/env python3
"""Verify, record and reuse a frozen candidate; never build or relabel its origin."""
from __future__ import annotations

import argparse
import datetime
import importlib.util
import json
import os
from pathlib import Path
import subprocess

spec = importlib.util.spec_from_file_location('qualification_source', Path(__file__).with_name('qualification-source.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
FIXTURES = 'Tests/SwiftJLSTests/Fixtures'
CLT = '/Library/Developer/CommandLineTools'


def require(value, message):
    if not value:
        raise RuntimeError(message)


def read(path):
    return json.loads(path.read_text())


def git(*args):
    return subprocess.check_output(['git', *args], cwd=q.ROOT, text=True).strip()


def scoped_source(folder):
    paths = [folder / 'Package.swift', folder / 'VERSION']
    paths += [p for p in (folder / 'Sources').rglob('*') if p.is_file()]
    paths += [p for p in (folder / 'Tests').rglob('*.swift') if p.is_file()]
    require(all(not p.is_symlink() for p in paths), 'Symlink in source inventory')
    return {str(p.relative_to(folder)): q.sha(p) for p in sorted(paths)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-identity', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    identity_path = args.build_identity.resolve()
    identity_digest = q.sha(identity_path)
    folder = identity_path.parent
    record = read(identity_path)
    source = record['source']
    current = q.source()
    require(current['source_commit'] is not None, 'Promote and commit all source/tests/package before reuse')
    checkpoint = current['source_commit']
    require(not git('status', '--porcelain', '--untracked-files=all', '--', 'Sources', 'Tests', 'Package.swift', 'VERSION'),
            'Source/test/package/version working tree is dirty')
    require(record['source_unchanged'] is True and record['consumer_unchanged'] is True,
            'Successful unchanged candidate inputs are required')
    command = record['command']
    require(command['exit_code'] == 0 and command['developer_dir'] == source['developer_dir'] == CLT,
            'Successful explicit-CLT build record required')
    argv = command['command']
    require(argv[:2] == ['swift', 'build'] and '-c' in argv and argv[argv.index('-c') + 1] == 'release',
            'Candidate was not a recorded release build')
    require('--package-path' in argv, 'Missing recorded build package')
    built_package = Path(argv[argv.index('--package-path') + 1])
    if not built_package.is_absolute():
        built_package = Path(command['cwd']) / built_package
    require(built_package.resolve() == (folder / 'consumer').resolve(), 'Recorded build used a different package')
    actual = scoped_source(q.ROOT)
    require(actual == source['source_files'] == scoped_source(folder / 'codec'),
            'Final and candidate Sources/Swift Tests/Package/VERSION inventory or bytes differ')
    require(git('rev-parse', source['base_source']) == source['base_source'], 'Invalid original candidate base revision')
    fixtures_tree = git('rev-parse', checkpoint + ':' + FIXTURES)
    require(fixtures_tree == source['fixtures_tree'], 'Final fixture Git tree differs from candidate')
    require(git('rev-parse', source['base_source'] + ':' + FIXTURES) == fixtures_tree,
            'Candidate fixture provenance differs from its recorded base')
    patches = source['patches']
    require(isinstance(patches, dict) and 'combined.patch' in patches, 'Missing original patch provenance')
    for name, digest in patches.items():
        require(Path(name).name == name and q.sha(folder / name) == digest, 'Candidate patch changed: ' + name)
    consumer = folder / 'consumer/Sources/Benchmark/main.swift'
    package = folder / 'consumer/Package.swift'
    consumer_sha = q.sha(q.ROOT / 'Scripts/Benchmark/Consumer.swift')
    require(q.sha(consumer) == consumer_sha == source['consumer_sha256'], 'Candidate is not the unchanged original Consumer')
    require(q.sha(package) == source['consumer_package_sha256'], 'Candidate consumer package changed')
    binary = Path(record['binary']).resolve()
    require(binary.is_file() and binary.is_relative_to(folder / 'consumer/.build'), 'Unexpected frozen binary location')
    require(q.sha(binary) == record['binary_sha256'], 'Frozen candidate binary changed')
    env = os.environ.copy()
    env['DEVELOPER_DIR'] = CLT
    swift = subprocess.check_output(['swift', '--version'], env=env, text=True)
    require(swift == source['swift'], 'Current compiler differs from candidate compiler')
    q.unchanged(current)
    require(scoped_source(q.ROOT) == actual and q.sha(identity_path) == identity_digest and
            q.sha(binary) == record['binary_sha256'],
            'Source identity changed during reuse validation')
    output = dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  status='verified frozen candidate reuse; no build performed', rebuilt=False,
                  source_commit=checkpoint, source=current, source_files=actual,
                  fixtures_tree=fixtures_tree, version_sha256=actual['VERSION'],
                  build_identity_path=str(identity_path), build_identity_sha256=identity_digest,
                  original_build_record=record, original_base_source=source['base_source'],
                  original_patches=patches, original_build_command=command,
                  developer_dir=CLT, swift=swift, consumer_sha256=consumer_sha,
                  compiled_consumer_sha256=q.sha(consumer), consumer_package_sha256=q.sha(package),
                  binary=dict(path=str(binary), sha256=record['binary_sha256']),
                  verified=True)
    with args.output.open('x') as stream:
        json.dump(output, stream, indent=2)
        stream.write('\n')
    print(json.dumps({k: output[k] for k in ['status', 'rebuilt', 'source_commit', 'original_base_source', 'binary', 'verified']}, indent=2))


if __name__ == '__main__':
    main()
