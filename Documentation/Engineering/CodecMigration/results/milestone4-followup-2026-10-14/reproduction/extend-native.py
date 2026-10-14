from pathlib import Path
import shutil,json,hashlib
r=Path('work/m4-2026-10-14');out=r/'native-payload-value'
for name in ['debug','asan','tsan']:
 source=r/'run-tests-value'/name/'out/Products/Debug/SwiftJLSTests.xctest'
 shutil.copytree(source,out/'configurations'/name/'SwiftJLSTests.xctest',dirs_exist_ok=True)
for name in ['asan','tsan']:
 shutil.copy2(Path('/Library/Developer/CommandLineTools/usr/lib/clang/21/lib/darwin')/('libclang_rt.'+name+'_osx_dynamic.dylib'),out/'lib')
p=out/'run-native.py';s=p.read_text();at=s.index("run([root/'AppleRuntimeConsumer'")
extra="""report['extra_tests']={}
for name in ['debug','asan','tsan']:
 extra_env=env.copy()
 if name!='debug':extra_env['DYLD_INSERT_LIBRARIES']=str(root/'lib'/('libclang_rt.'+name+'_osx_dynamic.dylib'))
 xml=out/('unit-'+name+'.xml')
 run([root/'swiftpm-testing-helper','--test-bundle-path',root/'configurations'/name/'SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests','--testing-library','swift-testing','--xunit-output',xml],'unit-'+name,extra_env)
 if xml.exists():
  cases=ET.parse(xml).findall('.//testcase');report['extra_tests'][name]=dict(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
"""
s=s[:at]+extra+s[at:]
s=s.replace("report.get('tests')==dict(declarations=84,failures=0,skipped=0)","report.get('tests')==dict(declarations=84,failures=0,skipped=0) and report['extra_tests']=={name:dict(declarations=84,failures=0,skipped=0) for name in ['debug','asan','tsan']}")
p.write_text(s)
m=out/'manifest.json';d=json.loads(m.read_text());d['files']={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and not p.is_symlink() and p!=m};m.write_text(json.dumps(d,indent=2)+'\n')
