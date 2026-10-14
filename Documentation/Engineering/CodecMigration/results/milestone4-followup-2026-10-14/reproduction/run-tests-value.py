import subprocess, json, time, pathlib, xml.etree.ElementTree as ET
out=pathlib.Path('work/m4-2026-10-14/run-tests-value'); out.mkdir(exist_ok=True)
results=[]
for name,extra in [('debug',[]),('release',['-c','release']),('asan',['--sanitize','address']),('tsan',['--sanitize','thread'])]:
    xml=out/(name+'.xml')
    cmd=['swift','test','--build-system','swiftbuild','--jobs','4','--scratch-path',str(out/name),'--disable-xctest','--xunit-output',str(xml),'-Xswiftc','-load-plugin-library','-Xswiftc','/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib']+extra
    start=time.monotonic()
    with (out/(name+'.log')).open('w') as log:
        result=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT)
    record=dict(label=name,command=cmd,exit_code=result.returncode,seconds=time.monotonic()-start)
    if xml.exists():
        cases=ET.parse(xml).findall('.//testcase')
        record.update(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
    results.append(record)
    (out/'results.json').write_text(json.dumps(results,indent=2)+'\n')
    print(json.dumps(record),flush=True)
