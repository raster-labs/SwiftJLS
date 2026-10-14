import pathlib,subprocess,os,json,time,xml.etree.ElementTree as ET
r=pathlib.Path('work/m4-2026-10-14').resolve();root=r/'native-payload-value';out=r/'native-portable-controls';out.mkdir(exist_ok=True);records=[]
for name in ['debug','asan','tsan']:
 env=os.environ.copy();env['DYLD_FRAMEWORK_PATH']=str(root/'Frameworks');env['DYLD_LIBRARY_PATH']=str(root/'lib')
 if name!='debug':env['DYLD_INSERT_LIBRARIES']=str(root/'lib'/('libclang_rt.'+name+'_osx_dynamic.dylib'))
 xml=out/(name+'.xml');cmd=list(map(str,[root/'swiftpm-testing-helper','--test-bundle-path',root/'configurations'/name/'SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests','--testing-library','swift-testing','--xunit-output',xml]))
 p=subprocess.run(cmd,capture_output=True,text=True,env=env,timeout=180);(out/(name+'.stdout')).write_text(p.stdout);(out/(name+'.stderr')).write_text(p.stderr)
 record=dict(command=cmd,exit_code=p.returncode)
 if xml.exists():
  cases=ET.parse(xml).findall('.//testcase');record['tests']=dict(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
 records.append(record);(out/'results.json').write_text(json.dumps(records,indent=2)+'\n')
 if p.returncode or record.get('tests')!=dict(declarations=84,failures=0,skipped=0):raise RuntimeError(name+' portable control failed')
 print(name+' portable control passed',flush=True)
