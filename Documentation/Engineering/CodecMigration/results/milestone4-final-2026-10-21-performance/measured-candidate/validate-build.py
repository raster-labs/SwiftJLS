#!/usr/bin/env python3
"""Run authorised correctness checks/build only; never benchmark or promote."""
import datetime, hashlib, json, os, pathlib, shutil, subprocess, tarfile, time, xml.etree.ElementTree as ET

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

# Materialise all remaining source inputs from the byte-verified parent, then
# extract the unchanged fixture tree directly from its recorded Git revision.
parent = ROOT / 'work/m4-short-path-diagnostic'
for name, expected in source['source_files'].items():
    target = HERE / 'codec' / name
    if not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(parent / 'codec' / name, target)
    assert sha(target) == expected, name
consumer = HERE / 'consumer'
(consumer / 'Sources/Benchmark').mkdir(parents=True, exist_ok=False)
shutil.copyfile(parent / 'consumer/Sources/Benchmark/main.swift', consumer / 'Sources/Benchmark/main.swift')
shutil.copyfile(parent / 'consumer/Package.swift', consumer / 'Package.swift')
fixtures = 'Tests/SwiftJLSTests/Fixtures'
assert not (HERE / 'codec' / fixtures).exists()
assert subprocess.check_output(['git', 'rev-parse', source['base_source'] + ':' + fixtures], cwd=ROOT, text=True).strip() == source['fixtures_tree']
process = subprocess.Popen(['git', 'archive', source['base_source'], fixtures], cwd=ROOT, stdout=subprocess.PIPE)
with tarfile.open(fileobj=process.stdout, mode='r|') as archive:
    for member in archive:
        path = pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isfile() or member.isdir()
        archive.extract(member, HERE / 'codec')
assert process.wait() == 0
(HERE / 'fixture-materialisation.json').write_text(json.dumps(dict(base_source=source['base_source'], fixtures_tree=source['fixtures_tree'], method='Exact git archive; no fixture edits'), indent=2) + '\n')
guard_sources()
codec = str(HERE / 'codec')
release = tests('focused-release', ['swift', 'test', '--build-system', 'swiftbuild', '-c', 'release', '--jobs', '4', '--package-path', codec,
    '--filter', 'OwnedAdmissionTests|DestinationLifecycleTests|cancellationInProviderFinalisationPreventsPublication|MappingMetadataTests'] + PLUGIN, 15)
asan = tests('focused-asan', ['swift', 'test', '--build-system', 'swiftbuild', '--jobs', '4', '--package-path', codec,
    '--scratch-path', str(HERE / 'asan-build'), '--sanitize', 'address', '--filter', 'OwnedAdmissionTests|DestinationLifecycleTests|cancellationInProviderFinalisationPreventsPublication|MappingMetadataTests'] + PLUGIN, 15)
build = run('benchmark-build', ['swift', 'build', '-c', 'release', '--jobs', '4', '--package-path', str(HERE / 'consumer')])
guard_sources()
binary = HERE / 'consumer/.build/release/Benchmark'
binary_hash = sha(binary)
preflight = HERE / 'preflight-correctness-only'
preflight.mkdir()
env = dict(ENV, SWIFTJLS_BENCHMARK_END_TO_END='1')
for key in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE']:
    env.pop(key, None)
records = []
for bits in [12, 16]:
    for pattern in ['flat', 'ramp', 'noise']:
        case = f'37x23-{pattern}-p{bits}'
        args = [str(binary), '37', '23', str(bits), pattern, '0', '1', 'correctness-only-' + case]
        result = subprocess.run(args, cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
        item = dict(case=case, command=args, exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr,
            purpose='Correctness only; original Consumer checks every decoded sample. No qualified timings.')
        (preflight / (case + '.json')).write_text(json.dumps(item, indent=2) + '\n')
        assert result.returncode == 0, item
        row = json.loads(result.stdout)
        assert row['warmups'] == 0 and row['iterations'] == 1 and row['bits'] == bits
        records.append(dict(case=case, exit_code=0, full_sample_verification='passed', encoded_bytes=row['encoded_bytes']))
guard_sources()
assert sha(binary) == binary_hash
summary = dict(purpose='Correctness only; no qualified timing', cases=records, all_six_passed=True)
(preflight / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
record = dict(source=source, release=release, asan=asan, command=build, preflight=summary,
    binary=str(binary), binary_sha256=sha(binary), source_unchanged=True, consumer_unchanged=True,
    timings_run=False, promoted=False)
(HERE / 'build-identity.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps({k:v for k,v in record.items() if k not in ['source', 'release', 'asan', 'command']}, indent=2), flush=True)
