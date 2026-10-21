#!/usr/bin/env python3
import importlib.util, json, os, subprocess, time, xml.etree.ElementTree as ET
from pathlib import Path
spec=importlib.util.spec_from_file_location('qualification_source',Path(__file__).with_name('qualification-source.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
os.chdir(q.ROOT)
environment=os.environ.copy();environment['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
out=q.OUT/'tests';out.mkdir(exist_ok=False)
identity=q.source();q.write(out/'source.json',identity)
q.write(out/'toolchain.json',dict(developer_dir=environment['DEVELOPER_DIR'],
    swift=subprocess.check_output(['swift','--version'],env=environment,text=True),
    os=subprocess.check_output(['sw_vers'],text=True)))
results=[]
for name,extra in [('debug',[]),('release',['-c','release']),('asan',['--sanitize','address']),('tsan',['--sanitize','thread'])]:
    xml=out/(name+'.xml')
    cmd=['swift','test','--build-system','swiftbuild','--jobs','4','--scratch-path',str(q.OUT/'test-build'/name),'--disable-xctest','--xunit-output',str(xml),'-Xswiftc','-load-plugin-library','-Xswiftc','/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib']+extra
    start=time.monotonic()
    with (out/(name+'.log')).open('w') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=environment)
    record=dict(label=name,command=cmd,developer_dir=environment['DEVELOPER_DIR'],exit_code=result.returncode,seconds=time.monotonic()-start)
    if xml.exists():
        cases=ET.parse(xml).findall('.//testcase')
        record.update(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
    results.append(record);q.write(out/'results.json',results);print(json.dumps(record),flush=True)
    q.unchanged(identity)
    if result.returncode or not record.get('declarations') or record.get('failures') or record.get('skipped'):
        raise RuntimeError(name+' did not pass fully; outputs retained')
if len({x['declarations'] for x in results}) != 1:
    raise RuntimeError('Different declaration counts between configurations')
print('All four host configurations passed '+str(results[0]['declarations'])+' declarations',flush=True)
