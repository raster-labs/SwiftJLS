import subprocess,pathlib,json,time,datetime,threading
root=pathlib.Path.cwd();out=root/'work/m4-powered-final-2026-10-13';out.mkdir();stop=threading.Event()
def command(args):
 r=subprocess.run(args,capture_output=True,text=True,timeout=15)
 return dict(command=args,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
def sample():
 return dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),power=command(['pmset','-g','batt']),thermal=command(['pmset','-g','therm']),load=command(['sysctl','-n','vm.loadavg']),vm=command(['vm_stat']),memory_pressure=command(['memory_pressure','-Q']),cpu=command(['top','-l','1','-n','0']))
def monitor():
 with (out/'conditions.jsonl').open('x') as f:
  while not stop.is_set():
   f.write(json.dumps(sample())+'\n');f.flush()
   if stop.wait(30):break
  f.write(json.dumps(sample())+'\n')
thread=threading.Thread(target=monitor);thread.start()
results=[]
try:
 for label in ['colour']:
  cmd=['python3','Scripts/Benchmark/compare.py','--predecessor','work/m4-benchmark/predecessor/.build/release/Benchmark','--successor','work/m4-benchmark/successor/.build/release/Benchmark','--output',str(out/label),'--end-to-end']
  if label=='colour':cmd+=['--colour','--cases','work/m4-final-colour-cases.json']
  start=time.monotonic()
  with (out/(label+'.log')).open('x') as f:r=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT)
  results.append(dict(label=label,command=cmd,exit_code=r.returncode,seconds=time.monotonic()-start))
  (out/'commands.json').write_text(json.dumps(results,indent=2)+'\n')
  if r.returncode:raise RuntimeError(label+' comparison failed')
  print(label+' comparison completed',flush=True)
finally:
 stop.set();thread.join()
