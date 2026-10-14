from pathlib import Path
import shutil, subprocess, json, hashlib
out=Path('work/m4-2026-10-14/native-payload-value'); out.mkdir(exist_ok=True)
(out/'repo').mkdir(exist_ok=True)
archive=subprocess.Popen(['git','archive','HEAD'],stdout=subprocess.PIPE)
subprocess.run(['tar','-x','-C',str(out/'repo')],stdin=archive.stdout,check=True); archive.stdout.close(); assert archive.wait()==0
products=Path('work/m4-2026-10-14/run-tests-value/release/out/Products/Release')
shutil.copytree(products/'SwiftJLSTests.xctest',out/'SwiftJLSTests.xctest',dirs_exist_ok=True)
shutil.copytree(products/'SwiftJLS_SwiftJLSTests.bundle',out/'SwiftJLS_SwiftJLSTests.bundle',dirs_exist_ok=True)
shutil.copy2(products/'swiftjls-cli',out/'swiftjls-cli')
shutil.copy2('/Library/Developer/CommandLineTools/usr/libexec/swift/pm/swiftpm-testing-helper',out/'swiftpm-testing-helper')
(out/'Frameworks').mkdir(exist_ok=True);(out/'lib').mkdir(exist_ok=True)
for name in ['Testing','_Testing_Foundation']:
 shutil.copytree(Path('/Library/Developer/CommandLineTools/Library/Developer/Frameworks')/(name+'.framework'),out/'Frameworks'/(name+'.framework'),dirs_exist_ok=True,symlinks=True)
shutil.copy2('/Library/Developer/CommandLineTools/Library/Developer/usr/lib/lib_TestingInterop.dylib',out/'lib/lib_TestingInterop.dylib')
for name in ['AppleRuntimeConsumer','ResourceStress']:
 shutil.copy2(Path('Examples')/name/'.build/release'/name,out/name)
manifest=dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),sources_tree=subprocess.check_output(['git','rev-parse','HEAD:Sources'],text=True).strip(),files={str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in out.rglob('*') if p.is_file() and not p.is_symlink()})
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
