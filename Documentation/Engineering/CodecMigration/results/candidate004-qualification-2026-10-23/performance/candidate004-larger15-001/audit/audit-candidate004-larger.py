from pathlib import Path
import collections,datetime,gzip,hashlib,json,math,statistics
R=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/campaigns_004/runs/larger15-001')
A=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023');sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest(); load=lambda n:json.loads((R/n).read_text());jl=lambda n:[json.loads(x) for x in (R/n).read_text().splitlines()]
c=load('complete.json');p=load('frozen_schedule.json');summary=load('summary.json');env=load('environment.json');rows=jl('raw.jsonl');events=jl('events.jsonl');conditions=jl('conditions.jsonl');errors=[];checks=0;start={f.name:sha(f) for f in R.iterdir() if f.is_file()}
def ck(x,msg):
 global checks
 checks+=1
 if not x: errors.append(msg)
def eq(a,b):return math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-20)
def med(x):return statistics.median(x)
def quantile(x,q):
 s=sorted(x);f=(len(s)-1)*q;i=int(f);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(f-i)
for name,key in [('frozen_schedule.json','schedule_sha256'),('frozen_runner.py','runner_sha256'),('frozen_larger_guard_plan.json','larger_guard_plan_sha256'),('raw.jsonl','raw_jsonl_sha256'),('events.jsonl','events_jsonl_sha256'),('conditions.jsonl','conditions_jsonl_sha256'),('summary.json','summary_json_sha256')]:ck(sha(R/name)==c[key],'hash '+name)
ad=json.loads((A/'031-candidate004-larger15/admission.json').read_text());end=json.loads((A/'031-candidate004-larger15/command-end.json').read_text());frozen=A/'031-candidate004-larger15'
for name,h in ad['pins'].items():ck(sha(frozen/Path(name).name)==h,'root freeze '+name)
ck(end['exit_code']==0 and end['pins_unchanged'],'root end pins');ck(sha(frozen/'preflight.json')==ad['preflight_sha'],'bound preflight')
ck(c['source_guards']==env['source_guards'],'before/after source guard');ck(sha(R/'frozen_shared_helper.py')==c['source_guards']['shared_helper_sha256']==ad['pins']['diag72_runner.py'],'shared helper freeze')
ck(c['completed'] is True and c['performance_qualified'] is False,'completion disposition')
prod=p['producers'];brp=Path(prod['candidate']['build_receipt_path']);br=json.loads(brp.read_text());ck(sha(brp)==prod['candidate']['build_receipt_sha256'],'build receipt')
ck(sha(Path(prod['candidate']['build_events_path']))==prod['candidate']['build_events_sha256'],'build events')
for arm,d in prod.items():ck(sha(Path(d['path']))==d['sha256']==c['source_guards']['binary_sha256'][arm],'binary '+arm)
for key in ['repo_snapshot_dir','arm_candidate_dir']:
 root=Path(br[key]);ck({str(f.relative_to(root)):sha(f) for f in (root/'Sources/SwiftJLS').rglob('*.swift')}==br['swiftjls_file_sha256']==c['source_guards']['all_swiftjls_source_hashes'],'full production set '+key)
root=Path(br['repo_snapshot_dir']);ck({str(f.relative_to(root)):sha(f) for f in (root/'Tests/SwiftJLSTests').rglob('*.swift')}==br['test_file_sha256'],'full test set')
ck(sha(Path(br['task_store_path']))==br['task_store_sha256']==c['source_guards']['task_store_sha256'],'task store')
expected=[(x,arm) for x in p['schedule'] for arm in x['order']];ck(len(rows)==len(events)==len(expected)==p['expected_processes']==120,'count');ck(len(p['cases'])==len(summary)==15,'cases');ck(p['blocks_per_case']==4 and p['warmups']==p['observations_per_process']==5,'samples')
data={};rmap={};last_end='';known=set();ops=['encode','decode','prepare','prepare_encode']
for i,(r,e,(ent,arm)) in enumerate(zip(rows,events,expected)):
 case=ent['case'];cid=case['id'];b=ent['block'];key=(cid,arm,b);ck(key not in known,'duplicate '+str(i));known.add(key);rmap[key]=r
 ck(e['entry']==ent and e['producer']==r['producer']==arm and r['case_id']==cid and r['block']==b and r['position']==ent['position'] and r['order']==ent['order'],'schedule '+str(i))
 cmd=[prod[arm]['path'],str(case['width']),str(case['height']),str(case['bits']),case['pattern'],'5','5',arm,str(case['components']),str(case['near']),str(case['interleave'])]
 ck(r['command']==e['command']==cmd and r['binary_sha256']==prod[arm]['sha256'],'command/pin '+str(i))
 raw=json.loads(e['stdout']);ck(all(r[k]==v for k,v in raw.items()),'stdout '+str(i));ck(all(r[k]==v for k,v in case.items() if k!='id'),'case '+str(i));ck(r['warmups']==r['iterations']==5 and r['end_to_end'] is True and r['label']==arm,'sample counts '+str(i));ck(e['exit_code']==r['exit_code']==0 and e['stderr']==r['stderr']=='','exit/fidelity '+str(i))
 ck(e['started_utc']>=last_end and e['completed_utc']>=e['started_utc'],'timestamp overlap '+str(i));last_end=e['completed_utc'];ck(all(e[k]==r[k] for k in ['started_utc','completed_utc','process_seconds']),'timestamps '+str(i))
 for op in ops:
  vals=r[op+'_seconds'];ck(len(vals)==5 and all(math.isfinite(v) and v>0 for v in vals),'observations '+str(i)+op);data[cid,arm,b,op]=vals
for i,q in enumerate([env['conditions']]+conditions+[c['end_conditions']]):
 ck(q['power']['exit_code']==0 and "Now drawing from 'AC Power'" in q['power']['output'],'AC '+str(i));ck(q['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in q['thermal']['output'] and 'No performance warning level has been recorded' in q['thermal']['output'],'thermal '+str(i));ck(q['interfering_workload_matches']==[],'named interference '+str(i));ck(q['simulator_inventory']['process_count']==0,'simulator '+str(i))
ck(conditions[0]['completed_processes']==0 and conditions[-1]['completed_processes']==120 and all(a['completed_processes']<=b['completed_processes'] for a,b in zip(conditions,conditions[1:])),'condition coverage')
archive=Path('/Users/pushparaj/projects/SwiftJLS/Documentation/Engineering/CodecMigration/results/factory-qualification-2026-10-22/performance/larger15-guard-002/summary.json');archive=archive if archive.exists() else archive.with_suffix('.json.gz');old=json.loads(gzip.decompress(archive.read_bytes()) if archive.suffix=='.gz' else archive.read_bytes());old={x['case']['id']:x for x in old};metrics={};sizes=[];pair_above=[];order_above=[];rss=[]
for case in summary:
 cid=case['case']['id'];ref=[rmap[cid,'reference',b] for b in range(4)];cand=[rmap[cid,'candidate',b] for b in range(4)]
 ck(collections.Counter(tuple(x['order']) for x in cand)==collections.Counter({('reference','candidate'):2,('candidate','reference'):2}) and all(cand[b]['order']!=cand[b-1]['order'] for b in range(1,4)),'balanced alternating pair order '+cid)
 observed={arm:{rmap[cid,arm,b]['encoded_bytes'] for b in range(4)} for arm in prod};ck(all(len(x)==1 for x in observed.values()),'deterministic size '+cid);sz=case['encoded_bytes'];sv={a:next(iter(v)) for a,v in observed.items()};ck(all(sz[a]==v for a,v in sv.items()),'size data '+cid);ck(sz['delta_bytes']==sv['candidate']-sv['reference'] and eq(sz['ratio'],sv['candidate']/sv['reference']),'size summary '+cid);ck(all(sv[a]==old[cid]['encoded_bytes'][a] for a in prod) and sz['matches_archived_sizes'] and not sz['unexpected_from_archived_sizes_flag'],'archived size '+cid)
 special=cid=='4096x3073-p12-flat-c3-n0-i2';ck(sz['explained_spiff_header_difference']==special and (not special or (sv=={'reference':2115,'candidate':2159} and sz['explained_proof']['spiff_app8_bytes']==44 and sz['explained_proof']['entropy_bytes']==2078)),'specific SPIFF proof '+cid)
 ck(sz['retained_for_review']==(sz['delta_bytes']!=0 and not special),'size retained '+cid);sizes.append({'case':cid,**sz})
 rssobs={a:[rmap[cid,a,b]['peak_process_rss_bytes'] for b in range(4)] for a in prod};rssmed={a:med(v) for a,v in rssobs.items()};mr=case['peak_process_rss_bytes'];ck(mr['observations']==rssobs and mr['median']==rssmed and eq(mr['ratio'],rssmed['candidate']/rssmed['reference']),'RSS '+cid);rss.append({'case':cid,'ratio':mr['ratio']})
 for op,m in case['operations'].items():
  pooled={a:med(v for b in range(4) for v in data[cid,a,b,op]) for a in prod};ck(all(eq(m['pooled_median_seconds'][a],v) for a,v in pooled.items()),'pooled medians '+cid+op);ratio=pooled['candidate']/pooled['reference'];ck(eq(m['pooled_ratio'],ratio),'ratio '+cid+op);pairs=[med(data[cid,'candidate',b,op])/med(data[cid,'reference',b,op]) for b in range(4)];deltas=[med(data[cid,'candidate',b,op])-med(data[cid,'reference',b,op]) for b in range(4)]
  ck(m['observations_per_producer']==20 and eq(m['median_block_ratio'],med(pairs)) and eq(m['median_block_delta_seconds'],med(deltas)),'paired summary '+cid+op)
  ck(all(eq(x,y) for x,y in zip(m['ratio_range'],[min(pairs),max(pairs)])) and all(eq(x,y) for x,y in zip(m['ratio_iqr'],[quantile(pairs,.25),quantile(pairs,.75)])) and eq(m['ratio_sample_standard_deviation'],statistics.stdev(pairs)) and m['blocks_above_1_05']==sum(v>1.05 for v in pairs),'spread '+cid+op)
  ck(len(m['pairs'])==4,'pair count '+cid+op)
  for b,x in enumerate(m['pairs']):ck(x['block']==b and x['order']==cand[b]['order'] and eq(x['ratio'],pairs[b]) and eq(x['delta_seconds'],deltas[b]) and eq(x['reference_median_seconds'],med(data[cid,'reference',b,op])) and eq(x['candidate_median_seconds'],med(data[cid,'candidate',b,op])),'pair '+cid+op+str(b))
  for a in prod:
   v=med(pairs[b] for b in range(4) if cand[b]['order'][0]==a);ck(eq(m['median_ratio_by_first_producer'][a],v),'order summary '+cid+op+a)
   if v>1.05:order_above.append({'case':cid,'operation':op,'first':a,'ratio':v})
  if max(pairs)>1.05:pair_above.append({'case':cid,'operation':op,'pairs_above_1_05':sum(v>1.05 for v in pairs),'max_ratio':max(pairs)})
  metrics[cid+'|'+op]=ratio
ck(all(sha(R/n)==h for n,h in start.items()),'campaign stable during audit')
processes={}
for q in conditions:
 for x in q['processes_above_10_percent']:
  key=str(x['pid'])+'|'+x['exe_name'];d=processes.setdefault(key,{'count':0,'max_ps_cpu':0,'first_utc':q['utc'],'last_utc':q['utc']});d['count']+=1;d['max_ps_cpu']=max(d['max_ps_cpu'],x['cpu']);d['last_utc']=q['utc']
result={'errors':errors,'checks':checks,'processes':len(rows),'conditions':len(conditions),'metrics_recomputed':len(metrics),'pair_records_recomputed':len(metrics)*4,'pooled_points_over_1_05':{k:v for k,v in metrics.items() if v>1.05},'max_pooled_point':max(metrics.items(),key=lambda x:x[1]),'pooled_metrics':metrics,'points_with_any_pair_above_1_05':pair_above,'order_groups_above_1_05':order_above,'encoded_sizes':sizes,'encoded_delta_counts':dict(collections.Counter('equal' if x['delta_bytes']==0 else ('smaller' if x['delta_bytes']<0 else 'larger') for x in sizes)),'rss_ratios':rss,'cpu_ps_sum_range':[min(q['summed_cpu_percent'] for q in conditions),max(q['summed_cpu_percent'] for q in conditions)],'background_above10':processes,'measurement_span_seconds':(datetime.datetime.fromisoformat(events[-1]['completed_utc'])-datetime.datetime.fromisoformat(events[0]['started_utc'])).total_seconds(),'source_guards':c['source_guards'],'campaign_hashes':start,'archived_sizes_summary_sha256':sha(archive),'claim':'Completed representative descriptive guard only; no family confidence claim and no closure of three unresolved short endpoints; shared host retained.'}
(A/'candidate004-larger-independent-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:result[k] for k in ['errors','checks','processes','conditions','metrics_recomputed','pair_records_recomputed','pooled_points_over_1_05','max_pooled_point','points_with_any_pair_above_1_05','order_groups_above_1_05','encoded_delta_counts','cpu_ps_sum_range','measurement_span_seconds']},indent=2))
