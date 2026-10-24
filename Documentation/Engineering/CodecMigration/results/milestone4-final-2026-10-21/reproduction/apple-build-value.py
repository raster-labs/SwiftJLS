import pathlib, subprocess, json, time
root=pathlib.Path.cwd(); out=root/'work/m4-final-2026-10-21/apple-value'; out.mkdir(exist_ok=True)
sources=[str(p) for p in sorted((root/'Sources/SwiftJLS').rglob('*.swift'))]
results=[]
def run(cmd, log):
 start=time.monotonic()
 with log.open('w') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
 results.append(dict(command=cmd,exit_code=r.returncode,seconds=time.monotonic()-start,log=str(log.relative_to(root))))
 (out/'build-results.json').write_text(json.dumps(results,indent=2)+'\n')
 if r.returncode: raise RuntimeError(str(log))
for sdk,triple in [('iphonesimulator','arm64-apple-ios26.0-simulator'),('appletvsimulator','arm64-apple-tvos26.0-simulator'),('xrsimulator','arm64-apple-xros26.0-simulator'),('watchsimulator','arm64-apple-watchos26.0-simulator')]:
 target=out/sdk; target.mkdir(exist_ok=True)
 sdkpath=subprocess.check_output(['xcrun','--sdk',sdk,'--show-sdk-path'],text=True).strip()
 common=['xcrun','swiftc','-O','-swift-version','6','-strict-concurrency=complete','-target',triple,'-sdk',sdkpath]
 run(common+['-parse-as-library','-emit-library','-emit-module','-module-name','SwiftJLS',*sources,'-emit-module-path',str(target/'SwiftJLS.swiftmodule'),'-Xlinker','-install_name','-Xlinker','@rpath/libSwiftJLS.dylib','-o',str(target/'libSwiftJLS.dylib')],target/'library.log')
 run(['codesign','--force','--sign','-',str(target/'libSwiftJLS.dylib')],target/'sign-library.log')
 run(common+['-I',str(target),'-L',str(target),'-lSwiftJLS','-Xlinker','-rpath','-Xlinker',str(target),str(root/'Examples/AppleRuntimeConsumer/Sources/AppleRuntimeConsumer/main.swift'),'-o',str(target/'AppleRuntimeConsumer')],target/'consumer.log')
 run(['codesign','--force','--sign','-',str(target/'AppleRuntimeConsumer')],target/'sign-consumer.log')
 print(sdk+' build passed',flush=True)
sdkpath=subprocess.check_output(['xcrun','--sdk','watchos','--show-sdk-path'],text=True).strip()
run(['xcrun','swiftc','-O','-swift-version','6','-strict-concurrency=complete','-parse-as-library','-emit-module','-module-name','SwiftJLS','-target','arm64_32-apple-watchos26.0','-sdk',sdkpath,*sources,'-emit-module-path',str(out/'SwiftJLS-watch32.swiftmodule')],out/'watch32.log')
print('Watch arm64_32 module build passed',flush=True)
