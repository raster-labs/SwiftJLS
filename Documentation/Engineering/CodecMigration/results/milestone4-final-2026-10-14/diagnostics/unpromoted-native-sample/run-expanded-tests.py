import json,os,pathlib,subprocess,time,xml.etree.ElementTree as ET
base=pathlib.Path(__file__).resolve().parent;repo=base.parents[1]
env=os.environ.copy();env['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
results=[]
for label,build,extra in [('all-release','test-build',['-c','release']),('focused-asan','asan-build',['--sanitize','address','--filter','SampleNativeDecodeTests|ComponentCodecTests'])]:
 xml=base/(label+'.xml')
 command=['swift','test','--package-path',str(base/'codec'),'--build-system','swiftbuild','--jobs','4','--scratch-path',str(base/build),'--disable-xctest','--xunit-output',str(xml),'-Xswiftc','-load-plugin-library','-Xswiftc','/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib']+extra
 start=time.monotonic()
 with (base/(label+'.log')).open('w') as log:r=subprocess.run(command,env=env,cwd=repo,stdout=log,stderr=subprocess.STDOUT)
 row=dict(label=label,command=command,developer_dir=env['DEVELOPER_DIR'],exit_code=r.returncode,seconds=time.monotonic()-start)
 if xml.is_file():
  cases=ET.parse(xml).findall('.//testcase');row.update(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
 results.append(row);(base/'expanded-test-results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(row),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
