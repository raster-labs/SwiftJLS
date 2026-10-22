from pathlib import Path
import subprocess,os,json,hashlib,time,statistics,math
root=Path.cwd();parent=root/'work/recent-fixes-powered-2026-10-22';out=parent/'repeat';out.mkdir(exist_ok=False)
base=json.loads((parent/'manifest.json').read_text());env=dict(os.environ,DEVELOPER_DIR=base['developer_dir'],SWIFTJLS_BENCHMARK_END_TO_END='1')
binaries={k:Path(v['path']) for k,v in base['binaries'].items()}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def capture(cmd):
 r=subprocess.run(cmd,capture_output=True,text=True,env=env);return dict(command=cmd,exit_code=r.returncode,stdout=r.stdout,stderr=r.stderr)
schedule=[]
for block in range(16):
 for label in (['baseline','candidate'] if block%2==0 else ['candidate','baseline']):schedule.append(dict(experiment='direct',block=block,label=label,binary=label))
 if block%2==0:
  index=block//2
  for label in (['baseline','candidate'] if index%2==0 else ['candidate','baseline']):schedule.append(dict(experiment='same-candidate-control',block=index,label=label,binary='candidate'))
manifest=dict(case=[512,512,12,'noise',1,0,0],schedule=schedule,binaries=base['binaries'],initial_manifest_sha256=sha(parent/'manifest.json'),runner_sha256=sha(Path(__file__)),direct_pairs=16,control_pairs=8,warmups=5,iterations=5,reason='One initial preparation median and whole-process RSS flag; fixed16 direct pairs and8 same-candidate controls, interleaved before any repeat data. All4 operation metrics and RSS retained; this does not replace original data.')
(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');records=[];conditions=[]
def condition(phase):
 r=dict(phase=phase,power=capture(['pmset','-g','batt']),thermal=capture(['pmset','-g','therm']),load=capture(['sysctl','-n','vm.loadavg']));conditions.append(r);(out/'conditions.json').write_text(json.dumps(conditions,indent=2)+'\n')
 assert "Now drawing from 'AC Power'" in r['power']['stdout'] and r['power']['exit_code']==0
 assert r['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in r['thermal']['stdout'] and 'No performance warning level has been recorded' in r['thermal']['stdout']
for label,p in binaries.items():assert sha(p)==base['binaries'][label]['sha256']
with (out/'raw.jsonl').open('w') as log:
 for index,entry in enumerate(schedule):
  condition('before '+str(index));cmd=[str(binaries[entry['binary']]),'512','512','12','noise','5','5',entry['label'],'1','0','0'];start=time.monotonic();p=subprocess.run(cmd,capture_output=True,text=True,timeout=600,env=env)
  if p.returncode:
   (out/'failure.json').write_text(json.dumps(dict(command=cmd,exit_code=p.returncode,stdout=p.stdout,stderr=p.stderr),indent=2));raise RuntimeError('Consumer failed')
  r=json.loads(p.stdout)
  assert [r[k] for k in ['width','height','bits','pattern','components','near','interleave']]==manifest['case'] and r['label']==entry['label'] and r['warmups']==5 and r['iterations']==5 and r['end_to_end']==True and r['resource_profile']=='successor-workspace-1GiB-memory-2GiB-v1'
  for op in base['operations']:assert len(r[op+'_seconds'])==5 and all(math.isfinite(v) and v>0 for v in r[op+'_seconds'])
  assert all(a<=b for a,b in zip(r['prepare_seconds'],r['prepare_encode_seconds']))
  r.update(entry,command=cmd,ordinal=index,exit_code=p.returncode,stderr=p.stderr,process_seconds=time.monotonic()-start);records.append(r);log.write(json.dumps(r)+'\n');log.flush();condition('after '+str(index))
  if (index+1)%12==0:print('repeat processes',index+1,flush=True)
for label,p in binaries.items():assert sha(p)==base['binaries'][label]['sha256']
summary={}
for experiment in ['direct','same-candidate-control']:
 selected={label:[r for r in records if r['experiment']==experiment and r['label']==label] for label in ['baseline','candidate']};metrics={}
 for op in base['operations']:
  medians={label:statistics.median(v for r in rows for v in r[op+'_seconds']) for label,rows in selected.items()};pairs=[statistics.median(next(r for r in selected['candidate'] if r['block']==i)[op+'_seconds'])/statistics.median(next(r for r in selected['baseline'] if r['block']==i)[op+'_seconds']) for i in range(len(selected['baseline']))]
  metrics[op]=dict(medians=medians,ratio=medians['candidate']/medians['baseline'],paired_ratios=pairs,minimum_pair=min(pairs),maximum_pair=max(pairs),pairs_above_threshold=sum(v>1.05 for v in pairs))
 rss={label:[r['peak_process_rss_bytes'] for r in rows] for label,rows in selected.items()}
 assert set(r['encoded_bytes'] for rows in selected.values() for r in rows)=={410542}
 summary[experiment]=dict(metrics=metrics,rss=rss,maximum_rss_ratio=max(rss['candidate'])/max(rss['baseline']),median_rss_ratio=statistics.median(rss['candidate'])/statistics.median(rss['baseline']))
(out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:dict(ratios={op:r['ratio'] for op,r in v['metrics'].items()},maximum_rss_ratio=v['maximum_rss_ratio'],median_rss_ratio=v['median_rss_ratio']) for k,v in summary.items()},indent=2),flush=True)
