import subprocess, json, time, pathlib, os, xml.etree.ElementTree as ET
environment=os.environ.copy(); environment["DEVELOPER_DIR"]="/Library/Developer/CommandLineTools"
out=pathlib.Path('work/m4-final-2026-10-14/tests'); out.mkdir(exist_ok=True)
results=[]
for name,extra in [('debug',[]),('release',['-c','release']),('asan',['--sanitize','address']),('tsan',['--sanitize','thread'])]:
    xml=out/(name+'.xml')
    cmd=['swift','test','--build-system','swiftbuild','--jobs','4','--scratch-path',str(pathlib.Path('work/m4-2026-10-14/run-tests-value')/name),'--disable-xctest','--xunit-output',str(xml),'-Xswiftc','-load-plugin-library','-Xswiftc','/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib']+extra
    start=time.monotonic()
    with (out/(name+'.log')).open('w') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=environment)
    record=dict(label=name,command=cmd,developer_dir=environment["DEVELOPER_DIR"],exit_code=result.returncode,seconds=time.monotonic()-start)
    if xml.exists():
        cases=ET.parse(xml).findall('.//testcase')
        record.update(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
    results.append(record)
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(record),flush=True)
