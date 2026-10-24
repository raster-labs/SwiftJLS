import subprocess,json,time,pathlib,os,hashlib,xml.etree.ElementTree as ET
root=pathlib.Path.cwd();out=root/'work/recent-fixes-final-2026-10-22';env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools'); records=[]
def run(label,cmd,environment=env):
 start=time.monotonic()
 with (out/(label+'.log')).open('w') as log:r=subprocess.run(list(map(str,cmd)),stdout=log,stderr=subprocess.STDOUT,env=environment)
 row=dict(label=label,command=list(map(str,cmd)),exit_code=r.returncode,seconds=time.monotonic()-start,developer_dir=environment.get('DEVELOPER_DIR'))
 records.append(row);(out/'commands.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(row),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
 return row
plugin='/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib'
for label,flags in [('debug',[]),('release',['-c','release']),('asan',['--sanitize','address']),('tsan',['--sanitize','thread'])]:
 xml=out/(label+'.xml');row=run(label,['swift','test','--build-system','swiftbuild','--jobs','4','--scratch-path',out/label,'--disable-xctest','--xunit-output',xml,'-Xswiftc','-load-plugin-library','-Xswiftc',plugin,*flags]);cases=ET.parse(xml).findall('.//testcase');row.update(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases));(out/'commands.json').write_text(json.dumps(records,indent=2)+'\n');print('COUNT',label,row['declarations'],row['failures'],row['skipped'],flush=True)
cli=out/'release/release/swiftjls-cli'
if not cli.exists():cli=next((out/'release').rglob('Products/Release/swiftjls-cli'))
run('cli-payload',['python3','Scripts/test-payload-cli.py','--binary',cli,'--output',out/'cli-payload.json'])
run('cli-process',['python3','Scripts/test-cli.py','--binary',cli,'--output',out/'cli-process'])
run('consumer-build',['swift','build','-c','release','--jobs','4','--package-path','Examples/IndependentConsumer','--scratch-path',out/'consumer-build'])
run('consumer',[out/'consumer-build/release/Consumer'])
print('HOST_COMPLETE',flush=True)
