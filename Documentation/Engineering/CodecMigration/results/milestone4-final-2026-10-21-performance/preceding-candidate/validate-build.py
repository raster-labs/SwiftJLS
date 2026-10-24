#!/usr/bin/env python3
"""Run authorised correctness checks/build only; never benchmark or promote."""
import datetime, hashlib, json, os, pathlib, subprocess, time, xml.etree.ElementTree as ET

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ENV = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools', ASAN_OPTIONS='detect_leaks=0')
source = json.loads((HERE / 'source-identity.json').read_text())
PLUGIN = ['-Xswiftc', '-load-plugin-library', '-Xswiftc',
    '/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib']

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def guard_sources():
    for path, expected in source['source_files'].items():
        assert sha(HERE / 'codec' / path) == expected, path
    assert sha(HERE / 'consumer/Sources/Benchmark/main.swift') == source['consumer_sha256']
    assert sha(HERE / 'consumer/Package.swift') == source['consumer_package_sha256']

def run(name, args):
    start = time.monotonic()
    with (HERE / (name + '.log')).open('x') as log:
        result = subprocess.run(args, cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT)
    record = dict(command=args, cwd=str(ROOT), exit_code=result.returncode,
        seconds=time.monotonic()-start, utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        developer_dir=ENV['DEVELOPER_DIR'], asan_options=ENV['ASAN_OPTIONS'])
    (HERE / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    print(json.dumps(record), flush=True)
    if result.returncode:
        raise SystemExit(result.returncode)
    return record

def tests(name, args, expected):
    path = HERE / (name + '.xml')
    record = run(name, args + ['--xunit-output', str(path)])
    tree = ET.parse(path)
    cases = tree.findall('.//testcase')
    assert len(cases) == expected, (name, len(cases), expected)
    assert not tree.findall('.//failure') and not tree.findall('.//error') and not tree.findall('.//skipped')
    record.update(test_count=len(cases), xml_sha256=sha(path))
    (HERE / (name + '.json')).write_text(json.dumps(record, indent=2) + '\n')
    return record

guard_sources()
codec = str(HERE / 'codec')
release = tests('focused-release', ['swift', 'test', '--build-system', 'swiftbuild', '-c', 'release', '--jobs', '4', '--package-path', codec,
    '--filter', 'GradientTableTests|DescriptorTests|ParserContainerTests'] + PLUGIN, 17)
asan = tests('gradient-asan', ['swift', 'test', '--build-system', 'swiftbuild', '--jobs', '4', '--package-path', codec,
    '--scratch-path', str(HERE / 'asan-build'), '--sanitize', 'address', '--filter', 'GradientTableTests'] + PLUGIN, 3)
build = run('benchmark-build', ['swift', 'build', '-c', 'release', '--jobs', '4', '--package-path', str(HERE / 'consumer')])
guard_sources()
binary = HERE / 'consumer/.build/release/Benchmark'
record = dict(source=source, release=release, asan=asan, command=build,
    binary=str(binary), binary_sha256=sha(binary), source_unchanged=True, consumer_unchanged=True,
    timings_run=False, promoted=False)
(HERE / 'build-identity.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k:v for k,v in record.items() if k not in ['source', 'release', 'asan', 'command']}, indent=2), flush=True)
