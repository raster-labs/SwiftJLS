import pathlib,subprocess,json,os,datetime
root=pathlib.Path.cwd();w=root/'work/m4-2026-10-14';env=os.environ.copy();env['TART_HOME']=str(w/'vms');env['TART_NO_AUTO_PRUNE']='1';records=[]
def run(label,command,timeout):
 r=subprocess.run(command,capture_output=True,text=True,env=env,timeout=timeout)
 records.append(dict(label=label,command=command,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr,utc=datetime.datetime.now(datetime.timezone.utc).isoformat()));(w/'native-resume-commands.json').write_text(json.dumps(records,indent=2)+'\n');r.check_returncode();return r.stdout
run('verify guest version',['expect',str(w/'vm-ssh.exp'),'192.168.64.2',str(w/'vm-known-hosts'),'sw_vers'],30)
run('guest qualification',['expect',str(w/'vm-ssh.exp'),'192.168.64.2',str(w/'vm-known-hosts'),"python3 '/Volumes/My Shared Files/evidence/run-native.py'"],650)
x=json.loads((w/'native-results/results.json').read_text())
if not x.get('success'):raise RuntimeError('Guest qualification did not pass')
run('stop completed VM',[str(w/'tools/tart.app/Contents/MacOS/tart'),'stop','m4-macos26'],50)
print('Native macOS 26.0 qualification completed',flush=True)
