#!/usr/bin/env python3
"""Reuse the accepted candidate005 host bundles; package them for exact26.0 execution."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

spec = importlib.util.spec_from_file_location('qualification_source', Path(__file__).with_name('qualification-source.py'))
q = importlib.util.module_from_spec(spec)
spec.loader.exec_module(q)
identity = q.source()
expected = q.PINS['expected_declarations']
suites = q.PINS['expected_suite_declarations']
classnames = q.PINS['expected_xunit_classnames']
host_path = Path(q.PINS['host_receipt'])
if q.sha(host_path) != q.PINS['host_receipt_sha256']:
    raise RuntimeError('Accepted host receipt changed.')
host = json.loads(host_path.read_text())
if (host['swiftjls_file_sha256'] | host['test_file_sha256']) != q.PINS['production'] | q.PINS['tests']:
    raise RuntimeError('Accepted host tests do not bind candidate005.')
if host.get('candidate') != 'candidate_005' or host['declaration_counts_from_source'] != dict(suite_declarations=suites, test_declarations=expected):
    raise RuntimeError('Host source/declaration receipt mismatch.')
if {r['label'] for r in host['validation']} != {'debug', 'release', 'asan', 'tsan'} or len(host['validation']) != 4:
    raise RuntimeError('Four distinct host configurations required.')
builds = json.loads((q.OUT / 'consumer-builds.json').read_text())
if builds['source'] != identity:
    raise RuntimeError('Native consumer source mismatch.')

out = q.OUT / 'native-payload'
out.mkdir(exist_ok=False)
repo_dst = out / 'repo'
repo_dst.mkdir()
for rel, expected_sha in identity['files'].items():
    src = q.ROOT / rel
    dst = repo_dst / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    if q.sha(dst) != expected_sha:
        raise RuntimeError(f'Native source copy mismatch: {rel}')
for required in ['ManPages/swiftjls-cli.1', 'Scripts/install-cli.sh']:
    if required not in identity['files'] or not (repo_dst / required).is_file():
        raise RuntimeError('Native CLI qualification payload missing: ' + required)

bundle_shas = {}
host_bundle_binding = {}
for row in host['validation']:
    label = row['label']
    if row['exit_code'] or row['tests'] != expected or row['failures'] or row['errors'] or row['skipped']:
        raise RuntimeError(f'Host {label} not fully passing.')
    xml = host_path.parent / (label + '.xml')
    if q.sha(xml) != row['xml_sha256']:
        raise RuntimeError(f'Host XML changed: {label}')
    cases = list(ET.parse(xml).getroot().iter('testcase'))
    if len(cases) != expected or any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases):
        raise RuntimeError(f'Host XML count/failure mismatch: {label}')
    command = row['command']
    products = Path(command[command.index('--scratch-path') + 1]) / 'out/Products' / ('Release' if label == 'release' else 'Debug')
    destination = out if label == 'release' else out / 'configurations' / label
    destination.mkdir(parents=True, exist_ok=True)
    for name in ['SwiftJLSTests.xctest', 'SwiftJLS_SwiftJLSTests.bundle']:
        shutil.copytree(products / name, destination / name, symlinks=True)
    executable_rel = 'SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests'
    original_sha = q.sha(products / executable_rel)
    if q.sha(destination / executable_rel) != original_sha:
        raise RuntimeError(f'Test executable copy mismatch: {label}')
    bundle_shas[label] = original_sha
    host_bundle_binding[label] = dict(host_command=command, host_xml_sha256=q.sha(xml),
        original_executable=str(products / executable_rel), original_mtime_ns=(products / executable_rel).stat().st_mtime_ns,
        executable_sha256=original_sha, testcases=expected, xunit_classnames=len({c.attrib.get('classname') for c in cases}))
    if label == 'release':
        shutil.copy2(products / 'swiftjls-cli', out / 'swiftjls-cli')
if len(set(bundle_shas.values())) != 4:
    raise RuntimeError('Four distinct bundle executable identities required.')
cli_receipt = Path(q.PINS['host_cli_process_receipt'])
if q.sha(cli_receipt) != q.PINS['host_cli_process_receipt_sha256']:
    raise RuntimeError('Accepted host CLI receipt changed.')
cli = json.loads(cli_receipt.read_text())
if cli['status'] != 'passed' or cli['checks'] != 103 or cli['binary_sha256'] != q.sha(out / 'swiftjls-cli'):
    raise RuntimeError('Native CLI binary differs from accepted host CLI.')

clt = Path('/Library/Developer/CommandLineTools')
shutil.copy2(clt / 'usr/libexec/swift/pm/swiftpm-testing-helper', out / 'swiftpm-testing-helper')
(out / 'Frameworks').mkdir()
(out / 'lib').mkdir()
for name in ['Testing', '_Testing_Foundation']:
    shutil.copytree(clt / 'Library/Developer/Frameworks' / (name + '.framework'), out / 'Frameworks' / (name + '.framework'), symlinks=True)
shutil.copy2(clt / 'Library/Developer/usr/lib/lib_TestingInterop.dylib', out / 'lib/lib_TestingInterop.dylib')
env = dict(os.environ, DEVELOPER_DIR=str(clt))
clang = Path(subprocess.check_output(['/usr/bin/xcrun', 'clang', '--print-resource-dir'], env=env, text=True).strip())
for name in ['asan', 'tsan']:
    library = f'libclang_rt.{name}_osx_dynamic.dylib'
    shutil.copy2(clang / 'lib/darwin' / library, out / 'lib' / library)
consumers = {}
for name in ['AppleRuntimeConsumer', 'ResourceStress']:
    record = builds['binaries'][name]
    if q.sha(record['path']) != record['sha256']:
        raise RuntimeError('Native consumer changed after validation.')
    shutil.copy2(record['path'], out / name)
    consumers[name] = record['sha256']
shutil.copy2(q.OUT / 'run-native-template.py', out / 'run-native.py')
q.unchanged(identity)
manifest = dict(source_id='candidate_005', base_head=identity['base_head'], source_commit=None,
    sources_patch_sha256=identity['sources_patch_sha256'], source_manifest_sha256=identity['source_manifest_sha256'],
    source_receipt_sha256=identity['source_receipt_sha256'], expected_test_declarations=expected,
    expected_named_suite_declarations=suites, expected_xunit_classnames=classnames,
    host_test_counts={mode: expected for mode in bundle_shas}, host_bundle_binding=host_bundle_binding,
    host_receipt_sha256=q.PINS['host_receipt_sha256'], bundle_executable_sha256=bundle_shas,
    cli_binary_sha256=q.sha(out / 'swiftjls-cli'), consumer_binary_sha256=consumers,
    files={str(p.relative_to(out)): q.sha(p) for p in sorted(out.rglob('*')) if p.is_file() and not p.is_symlink()})
q.write(out / 'manifest.json', manifest)
print(json.dumps({k: manifest[k] for k in ['source_id', 'source_manifest_sha256', 'expected_test_declarations', 'bundle_executable_sha256']}, indent=2), flush=True)
