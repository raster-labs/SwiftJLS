import json, os, pathlib, subprocess, time, xml.etree.ElementTree as ET
base=pathlib.Path(__file__).resolve().parent
repo=base.parents[1]
env=os.environ.copy();env['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
records=[]
commands=[('focused-release-tests',['swift','test','--package-path',str(base/'codec'),'--build-system','swiftbuild','--jobs','4','--scratch-path',str(base/'test-build'),'--disable-xctest','--xunit-output',str(base/'focused-release.xml'),'-Xswiftc','-load-plugin-library','-Xswiftc','/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib','-c','release','--filter','SampleNativeDecodeTests|ComponentCodecTests']),('consumer-release-build',['swift','build','-c','release','--package-path',str(base/'consumer'),'--jobs','4'])]
for label,command in commands:
 started=time.monotonic()
 with (base/(label+'.log')).open('w') as log:r=subprocess.run(command,env=env,cwd=repo,stdout=log,stderr=subprocess.STDOUT)
 row=dict(label=label,command=command,developer_dir=env['DEVELOPER_DIR'],exit_code=r.returncode,seconds=time.monotonic()-started)
 if label=='focused-release-tests' and (base/'focused-release.xml').is_file():
  cases=ET.parse(base/'focused-release.xml').findall('.//testcase');row.update(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
 records.append(row);(base/'build-results.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(row),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
