from pathlib import Path
import subprocess,os,json,hashlib,tarfile,io,time,statistics,math,concurrent.futures
root=Path.cwd();out=root/'work/recent-fixes-powered-2026-10-22';env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools',SWIFTJLS_BENCHMARK_END_TO_END='1')
for name in ['SWIFTJLS_BENCHMARK_EXPORT','SWIFTJLS_BENCHMARK_DECODE']:assert not env.get(name)
revisions={'baseline':'62309d3c59b04c5896d6ea076aae5ce06f5f33e3','candidate':'e66f7da0d663756bae2d1495454d59b028228f7f'}
cases=[[37,23,12,'noise',1,0,0],[37,23,16,'flat',1,0,0],[512,512,12,'noise',1,0,0],[512,512,16,'flat',1,0,0],[512,512,16,'noise',3,0,1],[512,512,12,'ramp',3,0,2]]
consumer=(root/'Scripts/Benchmark/Consumer.swift').read_bytes();(out/'Consumer.swift').write_bytes(consumer)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def capture(cmd):
 p=subprocess.run(cmd,capture_output=True,text=True,env=env);return dict(command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr)
manifest=dict(revisions=revisions,cases=cases,operations=['encode','decode','prepare','prepare_encode'],blocks=4,warmups=5,iterations=5,consumer_sha256=hashlib.sha256(consumer).hexdigest(),runner_sha256=sha(Path(__file__)),developer_dir=env['DEVELOPER_DIR'],builds={},source_files={},method='Common owning SwiftJLS API at both revisions; same consumer, release without sanitizers, per-process correctness before timing, four alternating paired blocks.20 observations per producer/case/operation. No population-confidence or fullM4 qualification claim.',environment={x:capture(cmd) for x,cmd in [('swift',['swift','--version']),('os',['sw_vers']),('hardware',['sysctl','hw.model','hw.ncpu','hw.memsize','machdep.cpu.brand_string'])]})
binaries={}
for label,revision in revisions.items():
 source=out/(label+'-source');source.mkdir(exist_ok=False)
 tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive',revision,'Package.swift','Sources']))).extractall(source)
 files=[source/'Package.swift',*sorted((source/'Sources').rglob('*.swift'))]
 for p in files:assert p.read_bytes()==subprocess.check_output(['git','show',revision+':'+str(p.relative_to(source))])
 manifest['source_files'][label]={str(p.relative_to(source)):sha(p) for p in files}
 package=out/(label+'-consumer');(package/'Sources/Benchmark').mkdir(parents=True)
 (package/'Sources/Benchmark/main.swift').write_bytes(consumer)
 (package/'Package.swift').write_text('// swift-tools-version: 6.2\nimport PackageDescription\nlet package=Package(name:"Benchmark",platforms:[.macOS(.v26)],dependencies:[.package(path:'+json.dumps(str(source))+')],targets:[.executableTarget(name:"Benchmark",dependencies:[.product(name:"SwiftJLS",package:'+json.dumps(source.name)+')])],swiftLanguageModes:[.v6])\n')
 binaries[label]=package/'.build/release/Benchmark'
 manifest['builds'][label]=dict(command=['swift','build','-c','release','--jobs','4','--package-path',str(package)])
def build(label):
 cmd=manifest['builds'][label]['command'];start=time.monotonic()
 with (out/(label+'-build.log')).open('w') as log:p=subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT,env=env)
 manifest['builds'][label].update(exit_code=p.returncode,seconds=time.monotonic()-start)
 assert p.returncode==0,label
 print(label+' build passed',flush=True)
with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:list(pool.map(build,revisions))
manifest['binaries']={label:dict(path=str(p),sha256=sha(p)) for label,p in binaries.items()}
schedule=[]
for case in cases:
 for block in range(4):
  for label in (['baseline','candidate'] if block%2==0 else ['candidate','baseline']):schedule.append(dict(case=case,block=block,label=label))
manifest['schedule']=schedule;(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
conditions=[]
def condition(phase):
 r=dict(phase=phase,utc=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),power=capture(['pmset','-g','batt']),thermal=capture(['pmset','-g','therm']),load=capture(['sysctl','-n','vm.loadavg']))
 conditions.append(r);(out/'conditions.json').write_text(json.dumps(conditions,indent=2)+'\n')
 assert r['power']['exit_code']==0 and "Now drawing from 'AC Power'" in r['power']['stdout'],'AC power required'
 assert r['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in r['thermal']['stdout'] and 'No performance warning level has been recorded' in r['thermal']['stdout'],'Thermal/performance warning'
 return r
condition('before timing');(out/'background-before.json').write_text(json.dumps(capture(['ps','-axo','pid,pcpu,comm','-r']),indent=2)+'\n')
records=[]
with (out/'raw.jsonl').open('w') as log:
 for ordinal,item in enumerate(schedule):
  case=item['case'];w,h,b,pattern,c,n,i=case;label=item['label'];condition('before process '+str(ordinal))
  cmd=[str(binaries[label]),str(w),str(h),str(b),pattern,'5','5',label,str(c),str(n),str(i)];start=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
  if p.returncode:
   (out/'failure.json').write_text(json.dumps(dict(command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2));raise RuntimeError('Consumer failed')
  r=json.loads(p.stdout)
  expected=dict(label=label,width=w,height=h,bits=b,pattern=pattern,components=c,near=n,interleave=i,warmups=5,iterations=5,end_to_end=True,resource_profile='successor-workspace-1GiB-memory-2GiB-v1')
  assert all(r[k]==v for k,v in expected.items())
  for operation in manifest['operations']:
   values=r[operation+'_seconds'];assert len(values)==5 and all(type(v) in [int,float] and math.isfinite(v) and v>0 for v in values)
  assert all(a<=b for a,b in zip(r['prepare_seconds'],r['prepare_encode_seconds']))
  r.update(command=cmd,block=item['block'],ordinal=ordinal,process_seconds=time.monotonic()-start,stderr=p.stderr,exit_code=p.returncode)
  records.append(r);log.write(json.dumps(r)+'\n');log.flush();condition('after process '+str(ordinal))
  if (ordinal+1)%8==0:print('Completed',case,flush=True)
condition('after timing');(out/'background-after.json').write_text(json.dumps(capture(['ps','-axo','pid,pcpu,comm','-r']),indent=2)+'\n')
assert manifest['runner_sha256']==sha(Path(__file__))
for label,p in binaries.items():
 assert sha(p)==manifest['binaries'][label]['sha256']
 for path,h in manifest['source_files'][label].items():assert sha(out/(label+'-source')/path)==h
summary=[];keys=['width','height','bits','pattern','components','near','interleave']
for case in cases:
 row=dict(case=case,metrics={})
 selected={label:[r for r in records if r['label']==label and [r[k] for k in keys]==case] for label in revisions}
 for metric in manifest['operations']:
  measures={}
  for label,runs in selected.items():
   values=sorted(v for r in runs for v in r[metric+'_seconds']);assert len(values)==20
   measures[label]=dict(median=statistics.median(values),p95=values[18],minimum=values[0],maximum=values[-1],samples=20)
  measures['ratio']=measures['candidate']['median']/measures['baseline']['median']
  measures['paired_block_ratios']=[statistics.median(next(r for r in selected['candidate'] if r['block']==i)[metric+'_seconds'])/statistics.median(next(r for r in selected['baseline'] if r['block']==i)[metric+'_seconds']) for i in range(4)]
  measures['above_5_percent']=measures['ratio']>1.05;row['metrics'][metric]=measures
 row['encoded_bytes']={label:sorted(set(r['encoded_bytes'] for r in runs)) for label,runs in selected.items()};assert row['encoded_bytes']['baseline']==row['encoded_bytes']['candidate']
 row['rss']={label:max(r['peak_process_rss_bytes'] for r in runs) for label,runs in selected.items()};row['rss_ratio']=row['rss']['candidate']/row['rss']['baseline'];summary.append(row)
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(dict(complete=True,processes=len(records),conditions=len(conditions),flagged=[dict(case=r['case'],metric=k,ratio=v['ratio']) for r in summary for k,v in r['metrics'].items() if v['above_5_percent']]),indent=2),flush=True)
