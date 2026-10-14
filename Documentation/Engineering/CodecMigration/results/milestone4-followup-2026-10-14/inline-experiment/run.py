import subprocess,json,pathlib,statistics
root=pathlib.Path.cwd(); out=root/'work/m4-2026-10-14/inline-experiment/results.jsonl'
bins={'current':root/'work/m4-benchmark/successor/.build/release/Benchmark','inline':root/'work/m4-2026-10-14/inline-experiment/benchmark/.build/release/Benchmark'}
cases=[[2048,2048,16,'ramp',1,0,0],[2048,2048,12,'ramp',1,0,0],[2048,2048,16,'flat',3,0,1],[512,512,16,'ramp',3,0,1],[512,512,16,'noise',3,0,2]]
with out.open('w') as f:
 for c in cases:
  for block in range(4):
   for label in (list(bins) if block%2==0 else list(bins)[::-1]):
    cmd=[str(bins[label]),*map(str,c[:4]),'2','3',label,*map(str,c[4:])]
    r=subprocess.run(cmd,capture_output=True,text=True,check=True,timeout=300)
    record=json.loads(r.stdout);f.write(json.dumps(dict(case=c,label=label,block=block,record=record))+'\n');f.flush()
  print(str(c)+' done',flush=True)
