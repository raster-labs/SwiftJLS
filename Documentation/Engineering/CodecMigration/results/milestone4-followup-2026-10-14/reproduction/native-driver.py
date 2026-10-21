import pathlib,subprocess,os,time,json,ipaddress,shlex,datetime
root=pathlib.Path.cwd();out=root/'work/m4-2026-10-14';env=os.environ.copy();env['TART_HOME']=str(out/'vms');env['TART_NO_AUTO_PRUNE']='1'
tart=str(out/'tools/tart.app/Contents/MacOS/tart');records=[]
def record(label,command,r):
 records.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),label=label,command=command,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr));(out/'native-driver-commands.json').write_text(json.dumps(records,indent=2)+'\n')
def run(command,label,timeout=60):
 r=subprocess.run(command,capture_output=True,text=True,env=env,timeout=timeout);record(label,command,r);r.check_returncode();return r.stdout
while True:
 r=subprocess.run([tart,'list','--source','local','--quiet'],capture_output=True,text=True,env=env,timeout=15)
 if r.returncode:record('list failure',r.args,r);r.check_returncode()
 if 'm4-macos26' in r.stdout.splitlines():break
 ps=subprocess.run(['ps','-p','11540','-o','command='],capture_output=True,text=True)
 if 'tart clone ghcr.io/cirruslabs/macos-tahoe-base@' not in ps.stdout:raise RuntimeError('Download ended without local VM; inspect download log')
 time.sleep(30)
print('VM download ready',flush=True)
run([tart,'set','m4-macos26','--cpu','4','--memory','8192'],'configure')
results=out/'native-results';results.mkdir(exist_ok=True)
with (out/'native-vm.log').open('w') as log:
 cmd=[tart,'run','m4-macos26','--no-graphics','--no-audio','--no-clipboard','--no-usb-accessories','--dir=evidence:'+str(out/'native-payload-value')+':ro','--dir=results:'+str(results)]
 vm=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
 (out/'native-vm-process.json').write_text(json.dumps(dict(command=cmd,pid=vm.pid),indent=2)+'\n')
 ip=None
 for attempt in range(8):
  if vm.poll() is not None:raise RuntimeError('VM stopped before boot')
  r=subprocess.run([tart,'ip','m4-macos26','--wait','30'],capture_output=True,text=True,env=env,timeout=40);record('resolve IP',r.args,r)
  if r.returncode==0:
   ip=str(ipaddress.ip_address(r.stdout.strip()));break
 if ip is None:raise RuntimeError('VM address unavailable')
 command='python3 '+shlex.quote('/Volumes/My Shared Files/evidence/run-native.py')
 run(['expect',str(out/'vm-ssh.exp'),ip,str(out/'vm-known-hosts'),command],'guest qualification',timeout=650)
 report=json.loads((results/'results.json').read_text())
 if not report.get('success'):raise RuntimeError('Guest report did not establish success')
 run([tart,'stop','m4-macos26'],'stop completed VM',timeout=50)
 vm.wait(timeout=30)
print('Native macOS 26.0 qualification completed',flush=True)
