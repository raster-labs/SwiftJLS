import subprocess,pathlib,json,time,sys
root=pathlib.Path.cwd();out=root/'work/m4-apple-final'; version=sys.argv[1]
runtimes=json.loads(subprocess.check_output(['xcrun','simctl','list','runtimes','--json']))['runtimes']
devices=json.loads(subprocess.check_output(['xcrun','simctl','list','devices','available','--json']))['devices']
results=[]
for prefix,sdk in [('iOS','iphonesimulator'),('tvOS','appletvsimulator'),('visionOS','xrsimulator'),('watchOS','watchsimulator')]:
 matches=[r for r in runtimes if r.get('version')==version and r.get('isAvailable') and r['name'].startswith(prefix)]
 if not matches:continue
 runtime=matches[0]
 candidates=[d for d in devices.get(runtime['identifier'],[]) if d.get('isAvailable')]
 if not candidates:continue
 selected=candidates[:1]
 if prefix=='iOS':
  selected=[next(d for d in candidates if d['name'].startswith('iPhone')),next(d for d in candidates if d['name'].startswith('iPad'))]
 for device in selected:
  label=prefix+'-'+version+'-'+device['name'].replace(' ','_').replace('/','_')
  entries=[]
  def run(args):
   cmd=['xcrun','simctl',*args];start=time.monotonic()
   r=subprocess.run(cmd,capture_output=True,text=True,timeout=180)
   entries.append(dict(command=cmd,exit_code=r.returncode,seconds=time.monotonic()-start,stdout=r.stdout,stderr=r.stderr))
   (out/(label+'.json')).write_text(json.dumps(dict(runtime=runtime,device=device,commands=entries),indent=2)+'\n')
   if r.returncode:raise RuntimeError(label+': '+r.stderr)
  was_booted=device['state']=='Booted'
  try:
   if not was_booted:run(['boot',device['udid']])
   run(['bootstatus',device['udid'],'-b'])
   run(['spawn',device['udid'],str(out/sdk/'AppleRuntimeConsumer'),str(root/'Tests/SwiftJLSTests/Fixtures')])
   print(label+' passed',flush=True)
  finally:
   if not was_booted:run(['shutdown',device['udid']])
