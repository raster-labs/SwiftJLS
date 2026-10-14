#!/usr/bin/env python3
import pathlib,subprocess,json,os,time,hashlib,xml.etree.ElementTree as ET
root=pathlib.Path(__file__).resolve().parent
out=pathlib.Path('/Volumes/My Shared Files/results');out.mkdir(exist_ok=True)
report=dict(source=json.loads((root/'manifest.json').read_text())['source_commit'],commands=[],scope='Swift 6.4 host-built arm64 binaries, executed in hardware-virtualised native arm64 macOS 26.0; no Intel emulation or physical-device claim.')
def run(command,label,env=None):
 start=time.monotonic();r=subprocess.run(list(map(str,command)),capture_output=True,text=True,env=env,timeout=300)
 (out/(label+'.stdout')).write_text(r.stdout);(out/(label+'.stderr')).write_text(r.stderr)
 item=dict(label=label,command=list(map(str,command)),exit_code=r.returncode,seconds=time.monotonic()-start)
 report['commands'].append(item);(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 return r
version=run(['sw_vers'],'os');arch=run(['uname','-m'],'architecture')
report['os']=version.stdout;report['architecture']=arch.stdout.strip()
report['exact_26_0_native_arm64']=any(line.strip()=='ProductVersion:\t26.0' for line in version.stdout.splitlines()) and arch.stdout.strip()=='arm64'
# Explicit parsing also supports sw_vers padding changes.
report['exact_26_0_native_arm64']=next((x.split(':',1)[1].strip() for x in version.stdout.splitlines() if x.startswith('ProductVersion:')),None)=='26.0' and arch.stdout.strip()=='arm64'
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
if not report['exact_26_0_native_arm64']:raise RuntimeError('Exact native arm64 macOS 26.0 not established')
run(['sysctl','hw.model','hw.memsize','hw.ncpu'],'hardware')
env=os.environ.copy();env['DYLD_FRAMEWORK_PATH']=str(root/'Frameworks');env['DYLD_LIBRARY_PATH']=str(root/'lib')
test=run([root/'swiftpm-testing-helper','--test-bundle-path',root/'SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests','--testing-library','swift-testing','--xunit-output',out/'unit.xml'],'unit',env)
if (out/'unit.xml').exists():
 cases=ET.parse(out/'unit.xml').findall('.//testcase');report['tests']=dict(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
report['extra_tests']={}
for name in ['debug','asan','tsan']:
 extra_env=env.copy()
 if name!='debug':extra_env['DYLD_INSERT_LIBRARIES']=str(root/'lib'/('libclang_rt.'+name+'_osx_dynamic.dylib'))
 xml=out/('unit-'+name+'.xml')
 run([root/'swiftpm-testing-helper','--test-bundle-path',root/'configurations'/name/'SwiftJLSTests.xctest/Contents/MacOS/SwiftJLSTests','--testing-library','swift-testing','--xunit-output',xml],'unit-'+name,extra_env)
 if xml.exists():
  cases=ET.parse(xml).findall('.//testcase');report['extra_tests'][name]=dict(declarations=len(cases),failures=sum(c.find('failure') is not None or c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
run([root/'AppleRuntimeConsumer',root/'repo/Tests/SwiftJLSTests/Fixtures'],'consumer')
run([root/'ResourceStress'],'resources')
run(['python3',root/'repo/Scripts/test-payload-cli.py','--binary',root/'swiftjls-cli','--output',out/'cli-payload.json'],'cli-payload')
run(['python3',root/'repo/Scripts/test-cli.py','--binary',root/'swiftjls-cli','--output',out/'cli-process'],'cli-process')
report['success']=all(c['exit_code']==0 for c in report['commands']) and report.get('tests')==dict(declarations=108,failures=0,skipped=0) and report['extra_tests']=={name:dict(declarations=108,failures=0,skipped=0) for name in ['debug','asan','tsan']}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if not report['success']:raise RuntimeError('Native runtime qualification failed; inspect retained outputs')
