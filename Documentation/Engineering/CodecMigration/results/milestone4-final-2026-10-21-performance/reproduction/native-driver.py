#!/usr/bin/env python3
"""Execute the committed payload in the existing exact-26.0 VM; always stop it."""
import datetime, ipaddress, json, os, pathlib, shlex, shutil, subprocess
root=pathlib.Path(__file__).resolve().parents[2];out=pathlib.Path(__file__).resolve().parent
old=root/'work/m4-2026-10-14';env=os.environ.copy()
env['TART_HOME']=str(old/'vms');env['TART_NO_AUTO_PRUNE']='1'
tart=str(old/'tools/tart.app/Contents/MacOS/tart');records=[]
manifest=json.loads((out/'native-payload/manifest.json').read_text())
if (out/'native-results').exists():raise RuntimeError('Refusing to overwrite a native attempt')
results=out/'native-results';results.mkdir()
shutil.copy2(old/'vm-ssh.exp',out/'vm-ssh.exp')
def run(command,label,timeout=60):
    try:
        r=subprocess.run(command,capture_output=True,text=True,env=env,timeout=timeout)
    except subprocess.TimeoutExpired as error:
        records.append(dict(label=label,command=command,timeout_seconds=timeout))
        (out/'native-driver-commands.json').write_text(json.dumps(records,indent=2)+'\n')
        raise error
    records.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),label=label,command=command,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr))
    (out/'native-driver-commands.json').write_text(json.dumps(records,indent=2)+'\n')
    r.check_returncode();return r.stdout
run([tart,'list'],'existing VM inventory')
cmd=[tart,'run','m4-macos26','--no-graphics','--no-audio','--no-clipboard','--no-usb-accessories',
     '--dir=evidence:'+str(out/'native-payload')+':ro','--dir=results-2026-10-21-performance:'+str(results)]
with (out/'native-vm.log').open('w') as log:
    vm=subprocess.Popen(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
    (out/'native-vm-process.json').write_text(json.dumps(dict(command=cmd,pid=vm.pid,source_commit=manifest['source_commit']),indent=2)+'\n')
    try:
        ip=None
        for attempt in range(8):
            if vm.poll() is not None:raise RuntimeError('VM stopped before guest boot')
            try:
                ip=str(ipaddress.ip_address(run([tart,'ip','m4-macos26','--wait','30'],'resolve IP',timeout=40).strip()))
                break
            except subprocess.CalledProcessError:pass
        if ip is None:raise RuntimeError('VM address unavailable')
        command='python3 '+shlex.quote('/Volumes/My Shared Files/evidence/run-native.py')
        run(['expect',str(out/'vm-ssh.exp'),ip,str(out/'known_hosts'),command],'guest qualification',timeout=650)
        report=json.loads((results/'results.json').read_text())
        if report.get('source')!=manifest['source_commit'] or not report.get('success'):
            raise RuntimeError('Native report did not establish current-source success')
    finally:
        run([tart,'stop','m4-macos26'],'stop VM before benchmarks',timeout=50)
        vm.wait(timeout=30)
        run([tart,'list'],'post-run stopped VM inventory')
print('Native macOS 26.0 validation passed; VM stopped',flush=True)
