from pathlib import Path
import subprocess,json,time,os,statistics,hashlib
root=Path.cwd();out=root/'work/m4-packed-optimisation';out.mkdir(exist_ok=True)
binaries={'baseline':root/'work/m4-benchmark/baseline/.build/release/Benchmark','candidate':root/'work/m4-benchmark/successor/.build/release/Benchmark'}
cases=[(512,512,12,'flat',3,0,1),(512,512,16,'flat',3,0,1),(2048,2048,12,'flat',3,0,1),(2048,2048,16,'flat',3,0,1),(512,512,12,'noise',3,0,2),(512,512,16,'noise',3,0,2),(512,512,12,'ramp',3,0,0),(512,512,16,'ramp',3,0,0)]
def cmd(c):
 r=subprocess.run(c,text=True,capture_output=True);return dict(command=c,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
def conditions():return dict(power=cmd(['pmset','-g','batt']),thermal=cmd(['pmset','-g','therm']),load=cmd(['sysctl','-n','vm.loadavg']),vm=cmd(['vm_stat']))
meta=dict(baseline_commit='1b4964dc0205ac9a529e07df9742878f40853e29',candidate_source_sha256={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'Sources').rglob('*.swift'))},binaries={k:dict(path=str(v),sha256=hashlib.sha256(v.read_bytes()).hexdigest()) for k,v in binaries.items()},cases=cases,scope='Baseline SwiftJLS versus candidate SwiftJLS; both use the same benchmark consumer and explicit large-fixture limits. This is not a JLSwift predecessor comparison.',conditions_start=conditions())
(out/'environment.json').write_text(json.dumps(meta,indent=2)+'\n');records=[]
with (out/'raw.jsonl').open('x') as f:
 for w,h,b,p,c,n,i in cases:
  for block in range(4):
   for label in (['baseline','candidate'] if block%2==0 else ['candidate','baseline']):
    command=[str(binaries[label]),str(w),str(h),str(b),p,'5','5',label,str(c),str(n),str(i)]
    r=subprocess.run(command,text=True,capture_output=True,env=dict(os.environ,SWIFTJLS_BENCHMARK_END_TO_END='1'),timeout=600)
    if r.returncode:raise RuntimeError(r.stderr)
    row=json.loads(r.stdout);row.update(block=block,command=command);records.append(row);f.write(json.dumps(row)+'\n');f.flush()
  print(w,h,b,p,'completed',flush=True)
summary=[]
for w,h,b,p,c,n,i in cases:
 rows=[r for r in records if (r['width'],r['height'],r['bits'],r['pattern'],r['components'],r['near'],r['interleave'])==(w,h,b,p,c,n,i)]
 result=dict(width=w,height=h,bits=b,pattern=p,components=c,near=n,interleave=i,metrics={})
 for op in ['encode','decode','prepare_encode']:
  metrics={label:statistics.median(v for r in rows if r['label']==label for v in r[op+'_seconds']) for label in binaries}
  pairs=[]
  for block in range(4):
   pair={r['label']:r for r in rows if r['block']==block};pairs.append(statistics.median(pair['candidate'][op+'_seconds'])/statistics.median(pair['baseline'][op+'_seconds']))
  metrics.update(candidate_over_baseline=metrics['candidate']/metrics['baseline'],paired_ratios=pairs);result['metrics'][op]=metrics
 summary.append(result)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(out/'conditions-end.json').write_text(json.dumps(conditions(),indent=2)+'\n')
