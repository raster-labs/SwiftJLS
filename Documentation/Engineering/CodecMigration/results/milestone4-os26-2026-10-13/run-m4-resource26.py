import subprocess,pathlib,json,time
root=pathlib.Path.cwd();out=root/'work/m4-resource26';out.mkdir(exist_ok=True)
commands=[]
def run(cmd,label):
 start=time.monotonic();r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
 entry=dict(label=label,command=cmd,exit_code=r.returncode,seconds=time.monotonic()-start,stdout=r.stdout,stderr=r.stderr)
 commands.append(entry);(out/'commands.json').write_text(json.dumps(commands,indent=2)+'\n')
 if r.returncode:raise RuntimeError(label+': '+r.stderr)
 return r.stdout
runtimes=json.loads(subprocess.check_output(['xcrun','simctl','list','runtimes','--json']))['runtimes']
devices=json.loads(subprocess.check_output(['xcrun','simctl','list','devices','available','--json']))['devices']
for platform,sdk,target in [('iOS','iphonesimulator','ios'),('tvOS','appletvsimulator','tvos'),('visionOS','xrsimulator','xros')]:
 lib=root/'work/m4-apple'/sdk;binary=out/('ResourceStress-'+sdk)
 sdkpath=subprocess.check_output(['xcrun','--sdk',sdk,'--show-sdk-path'],text=True).strip()
 run(['xcrun','swiftc','-O','-swift-version','6','-strict-concurrency=complete','-target',f'arm64-apple-{target}26.0-simulator','-sdk',sdkpath,'-I',str(lib),'-L',str(lib),'-lSwiftJLS','-Xlinker','-rpath','-Xlinker',str(lib),str(root/'Examples/ResourceStress/Sources/ResourceStress/main.swift'),'-o',str(binary)],platform+' compile')
 run(['codesign','--force','--sign','-',str(binary)],platform+' sign')
 runtime=next(r for r in runtimes if r['version']=='26.0' and r['name'].startswith(platform) and r['isAvailable'])
 candidates=devices[runtime['identifier']]
 selected=candidates[:1] if platform!='iOS' else [next(d for d in candidates if d['name'].startswith(k)) for k in ['iPhone','iPad']]
 for device in selected:
  udid=device['udid'];label=runtime['name']+' '+device['name'];started=device['state']!='Booted'
  try:
   if started:run(['xcrun','simctl','boot',udid],label+' boot')
   run(['xcrun','simctl','bootstatus',udid,'-b'],label+' bootstatus')
   result=json.loads(run(['xcrun','simctl','spawn',udid,str(binary)],label+' resource workload'))
   assert len(result)==4 and sum(r['frames'] for r in result)==32
   assert all(r['ownedPixelAllocations']==r['frames'] and r['suppliedPixelAllocations']==0 and r['reportedCopyBytes']==0 for r in result)
   print(label+' resource workload passed',flush=True)
  finally:
   if started:run(['xcrun','simctl','shutdown',udid],label+' shutdown')
