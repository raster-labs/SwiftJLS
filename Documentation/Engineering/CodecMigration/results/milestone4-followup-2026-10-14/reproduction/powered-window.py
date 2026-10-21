import os,signal,subprocess,time,pathlib,json,datetime
out=pathlib.Path('work/m4-2026-10-14'); events=[]
def record(action):
 events.append(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),action=action))
 (out/'benchmark-window.json').write_text(json.dumps(events,indent=2)+'\n')
pid=2763
command=subprocess.check_output(['ps','-p',str(pid),'-o','command='],text=True)
assert 'tart clone ghcr.io/cirruslabs/macos-tahoe-base@' in command
assert 'AC Power' in subprocess.check_output(['pmset','-g','batt'],text=True)
os.kill(pid,signal.SIGSTOP); record('Paused this task VM download before the controlled benchmark window')
try:
 time.sleep(45)
 with (out/'benchmark-start-processes.txt').open('w') as f: subprocess.run(['ps','-axo','pid,%cpu,comm'],stdout=f,check=True)
 record('Started powered scalar and representative RGB runs after settling')
 subprocess.run(['python3',str(out/'run-powered.py')],check=True)
 record('Powered runs completed')
finally:
 os.kill(pid,signal.SIGCONT);record('Resumed this task VM download')
