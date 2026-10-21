import os,signal,subprocess,time,pathlib,json,datetime
out=pathlib.Path('work/m4-2026-10-14'); events=[]
def record(action):
 events.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),action=action))
 (out/'benchmark-window-value.json').write_text(json.dumps(events,indent=2)+'\n')
# Qualification must finish before timing; do not overlap our local builds.
while True:
 path=out/'value-qualification-commands.json'
 if path.exists():
  records=json.loads(path.read_text())
  if any(r['exit_code'] for r in records): raise RuntimeError('Qualification command failed')
  if len(records)==8: break
 time.sleep(5)
pid=11540
command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
assert 'tart clone ghcr.io/cirruslabs/macos-tahoe-base@' in command
assert 'AC Power' in subprocess.check_output(['pmset','-g','batt'],text=True)
os.kill(pid,signal.SIGSTOP); record('Paused this task VM download before the controlled benchmark window')
try:
 time.sleep(45)
 with (out/'benchmark-start-processes-value.txt').open('w') as f: subprocess.run(['ps','-axo','pid,%cpu,comm'],stdout=f,check=True)
 record('Started powered scalar and representative RGB runs after settling')
 subprocess.run(['python3',str(out/'run-powered-value.py')],check=True)
 record('Powered runs completed')
finally:
 os.kill(pid,signal.SIGCONT);record('Resumed this task VM download')
