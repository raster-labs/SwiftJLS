#!/usr/bin/env python3
"""Build the isolated candidate and run focused release descriptor tests; no timing."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = HERE / 'source'
DEVELOPER_DIR = '/Library/Developer/CommandLineTools'
PIN = 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_hashes():
    paths = [SOURCE / 'Package.swift']
    for directory in ('Sources', 'Tests'):
        paths.extend(p for p in (SOURCE / directory).rglob('*') if p.is_file())
    return {str(p.relative_to(SOURCE)): sha(p) for p in sorted(paths)}


def main():
    assert not (HERE / 'build-results.json').exists()
    identity = json.loads((HERE / 'source-identity.json').read_text())
    assert subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=REPO, text=True).strip() == PIN
    assert not subprocess.check_output(['git', 'diff', 'HEAD', '--', 'Sources', 'Tests', 'Package.swift'], cwd=REPO, text=True)
    before = source_hashes()
    assert before == identity['candidate_files']
    benchmark = HERE / 'benchmark'
    assert sha(benchmark / 'Sources/Benchmark/main.swift') == identity['original_consumer_sha256']
    env = dict(os.environ, DEVELOPER_DIR=DEVELOPER_DIR)
    records = []
    commands = [
        ('benchmark-release', ['swift', 'build', '-c', 'release', '--jobs', '4', '--package-path', str(benchmark)]),
        ('descriptor-release', ['swift', 'test', '--package-path', str(SOURCE), '--build-system', 'swiftbuild',
            '-c', 'release', '--jobs', '4', '--scratch-path', str(HERE / 'test-build'), '--disable-xctest',
            '--filter', 'DescriptorTests', '--xunit-output', str(HERE / 'descriptor-release.xml'),
            '-Xswiftc', '-load-plugin-library', '-Xswiftc',
            '/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib'])]
    for name, args in commands:
        start = time.monotonic()
        with (HERE / (name + '.log')).open('x') as log:
            run = subprocess.run(args, cwd=REPO, env=env, stdout=log, stderr=subprocess.STDOUT)
        record = dict(label=name, command=args, developer_dir=DEVELOPER_DIR,
                      exit_code=run.returncode, seconds=time.monotonic() - start,
                      log_sha256=sha(HERE / (name + '.log')))
        xml = HERE / 'descriptor-release.xml'
        if name == 'descriptor-release' and xml.exists():
            cases = ET.parse(xml).findall('.//testcase')
            record.update(declarations=len(cases), failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),
                          skipped=sum(c.find('skipped') is not None for c in cases))
        records.append(record)
        (HERE / 'build-results.json').write_text(json.dumps(records, indent=2) + '\n')
        print(json.dumps(record), flush=True)
        assert run.returncode == 0 and source_hashes() == before
        if name == 'descriptor-release':
            assert record['declarations'] == identity['expected_descriptor_declarations'] and not record['failures'] and not record['skipped']
    binary = benchmark / '.build/release/Benchmark'
    proof = dict(base_revision=PIN, candidate_patch_sha256=sha(HERE / 'candidate.patch'),
        source_files=before, source_unchanged=True, binary=str(binary), binary_sha256=sha(binary),
        original_consumer_sha256=sha(benchmark / 'Sources/Benchmark/main.swift'),
        developer_dir=DEVELOPER_DIR,
        swift=subprocess.check_output(['swift', '--version'], cwd=REPO, env=env, text=True),
        sdk=subprocess.check_output(['xcrun', '--sdk', 'macosx', '--show-sdk-path'], cwd=REPO, env=env, text=True),
        benchmark_package_sha256=sha(benchmark / 'Package.swift'),
        commands=records, timing='not run', production_source_edits=False)
    (HERE / 'build-identity.json').write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps(dict(status='focused correctness and build passed; no timing', binary_sha256=proof['binary_sha256'])), flush=True)


if __name__ == '__main__':
    main()
