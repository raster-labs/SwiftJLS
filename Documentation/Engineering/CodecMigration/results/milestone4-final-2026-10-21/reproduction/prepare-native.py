#!/usr/bin/env python3
"""Package validated host binaries only after their exact source is committed."""
import importlib.util, json, os, shutil, subprocess, xml.etree.ElementTree as ET
from pathlib import Path
spec=importlib.util.spec_from_file_location('qualification_source',Path(__file__).with_name('qualification-source.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q);os.chdir(q.ROOT)
identity=q.source()
if identity['source_commit'] is None:raise RuntimeError('Commit source/tests/package before native packaging')
tested=json.loads((q.OUT/'tests/source.json').read_text())
if tested['files'] != identity['files']:raise RuntimeError('Committed source differs from tested source')
results=json.loads((q.OUT/'tests/results.json').read_text())
if {x['label'] for x in results} != {'debug','release','asan','tsan'} or len(results)!=4:
    raise RuntimeError('Four host configurations required')
if any(x['exit_code'] or x.get('failures') or x.get('skipped') or not x.get('declarations') for x in results):
    raise RuntimeError('All host configurations must pass completely')
counts={}
for result in results:
    cases=ET.parse(q.OUT/'tests'/(result['label']+'.xml')).findall('.//testcase')
    if len(cases)!=result['declarations'] or any(c.find('failure') is not None or c.find('error') is not None or c.find('skipped') is not None for c in cases):
        raise RuntimeError('Host result/XML mismatch')
    counts[result['label']]=len(cases)
if len(set(counts.values()))!=1:raise RuntimeError('Inconsistent host counts')
expected=counts['release']
builds=json.loads((q.OUT/'consumer-builds.json').read_text())
if builds['source']['files']!=identity['files']:raise RuntimeError('Consumers built against different source')
commands=json.loads((q.OUT/'value-qualification-commands.json').read_text())
required={'native-AppleRuntimeConsumer-value','native-ResourceStress-value','host-AppleRuntimeConsumer-value','host-ResourceStress-value','cli-payload-value','cli-process-value'}
if not required.issubset({x['label'] for x in commands if x['exit_code']==0}):
    raise RuntimeError('Missing successful consumer/CLI qualification')
out=q.OUT/'native-payload';out.mkdir(exist_ok=False);(out/'repo').mkdir()
archive=subprocess.Popen(['git','archive',identity['source_commit']],stdout=subprocess.PIPE)
try:
    subprocess.run(['tar','-x','-C',str(out/'repo')],stdin=archive.stdout,check=True)
finally:
    archive.stdout.close()
if archive.wait()!=0:raise RuntimeError('git archive failed')
products=q.OUT/'test-build/release/out/Products/Release'
for bundle in ['SwiftJLSTests.xctest','SwiftJLS_SwiftJLSTests.bundle']:
    shutil.copytree(products/bundle,out/bundle)
shutil.copy2(products/'swiftjls-cli',out/'swiftjls-cli')
clt=Path('/Library/Developer/CommandLineTools')
shutil.copy2(clt/'usr/libexec/swift/pm/swiftpm-testing-helper',out/'swiftpm-testing-helper')
(out/'Frameworks').mkdir();(out/'lib').mkdir()
for name in ['Testing','_Testing_Foundation']:
    shutil.copytree(clt/'Library/Developer/Frameworks'/(name+'.framework'),out/'Frameworks'/(name+'.framework'),symlinks=True)
shutil.copy2(clt/'Library/Developer/usr/lib/lib_TestingInterop.dylib',out/'lib/lib_TestingInterop.dylib')
for name in ['AppleRuntimeConsumer','ResourceStress']:
    record=builds['binaries'][name];binary=Path(record['path'])
    if q.sha(binary)!=record['sha256']:raise RuntimeError(name+' binary changed after qualification')
    shutil.copy2(binary,out/name)
for name in ['debug','asan','tsan']:
    products=q.OUT/'test-build'/name/'out/Products/Debug'
    for bundle in ['SwiftJLSTests.xctest','SwiftJLS_SwiftJLSTests.bundle']:
        shutil.copytree(products/bundle,out/'configurations'/name/bundle)
env=os.environ.copy();env['DEVELOPER_DIR']=str(clt)
clang=Path(subprocess.check_output(['xcrun','clang','--print-resource-dir'],env=env,text=True).strip())
for name in ['asan','tsan']:
    library='libclang_rt.'+name+'_osx_dynamic.dylib'
    shutil.copy2(clang/'lib/darwin'/library,out/'lib'/library)
shutil.copy2(q.OUT/'run-native-template.py',out/'run-native.py')
q.unchanged(identity)
manifest=dict(source_commit=identity['source_commit'],
    sources_tree=subprocess.check_output(['git','rev-parse',identity['source_commit']+':Sources'],text=True).strip(),
    tests_tree=subprocess.check_output(['git','rev-parse',identity['source_commit']+':Tests'],text=True).strip(),
    expected_test_declarations=expected,host_test_counts=counts,
    files={str(p.relative_to(out)):q.sha(p) for p in out.rglob('*') if p.is_file() and not p.is_symlink() and p!=out/'manifest.json'})
q.write(out/'manifest.json',manifest)
print(json.dumps(dict(source_commit=identity['source_commit'],expected_test_declarations=expected,payload=str(out)),indent=2))
