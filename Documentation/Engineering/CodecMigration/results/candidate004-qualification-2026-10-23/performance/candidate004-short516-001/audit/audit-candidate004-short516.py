from pathlib import Path
import collections,datetime,gzip,hashlib,json,math,statistics
R=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/campaigns_004/runs/short516-001')
O=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda f:json.loads((R/f).read_text())
lines=lambda f:[json.loads(l) for l in (R/f).read_text().splitlines()]
c=load('complete.json');plan=load('frozen_schedule.json');summ=load('summary.json');env=load('environment.json');rows=lines('raw.jsonl');events=lines('events.jsonl');conditions=lines('conditions.jsonl');errors=[];checks=0
initial_hashes={p.name:sha(p) for p in R.iterdir() if p.is_file()}
def ck(v,msg):
 global checks
 checks+=1
 if not v: errors.append(msg)
def eq(a,b):return math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-20)
def median(seq):return statistics.median(seq)
def quantile(seq,p):
 s=sorted(seq);x=(len(s)-1)*p;i=int(x);f=x-i
 return s[i]+f*(s[min(i+1,len(s)-1)]-s[i])
for f,k in [('raw.jsonl','raw_jsonl_sha256'),('events.jsonl','events_jsonl_sha256'),('conditions.jsonl','conditions_jsonl_sha256'),('summary.json','summary_json_sha256'),('frozen_schedule.json','schedule_sha256'),('frozen_analyse.py','analysis_sha256')]: ck(sha(R/f)==c[k],'hash '+f)
admission=json.loads((O/'028-candidate004-short516/admission.json').read_text());end=json.loads((O/'028-candidate004-short516/command-end.json').read_text());frozen=O/'028-candidate004-short516/frozen'
for f,h in admission['frozen_paths_sha256'].items():ck(sha(frozen/f)==h,'external freeze '+f)
ck(c['runner_sha256']==admission['frozen_paths_sha256']['short516_runner.py'],'runner binding')
ck(sha(R/'frozen_runner.py')==c['runner_sha256'],'campaign frozen runner')
ck(sha(R/'frozen_shared_helper.py')==env['source_guards']['shared_helper_sha256']==admission['frozen_paths_sha256']['diag72_runner.py'],'campaign frozen helper')
ck(end['exit_code']==0 and end['all_pins_stable'],'postcondition receipt')
ck(env['source_guards']==c['source_guards'],'start/end sourceguards')
ck(env['analyse_sha256']==c['analysis_sha256'] and env['plan_sha256']==c['schedule_sha256'],'environment hashes')
ck(c['completed'] is True and c['performance_qualified'] is False,'completion disposition')
prod=plan['producers'];brpath=Path(prod['candidate']['build_receipt_path']);br=json.loads(brpath.read_text())
ck(sha(brpath)==prod['candidate']['build_receipt_sha256'],'build receipt')
ck(sha(Path(prod['candidate']['build_events_path']))==prod['candidate']['build_events_sha256'],'build events')
ck(env['source_guards']['all_swiftjls_source_hashes']==prod['candidate']['all_swiftjls_source_hashes']==br['swiftjls_file_sha256'],'source inventory equality')
for arm,details in prod.items():ck(sha(Path(details['path']))==details['sha256']==env['source_guards']['binary_sha256'][arm],'binary '+arm)
for prefix in ['repo_snapshot_dir','arm_candidate_dir']:
 root=Path(br[prefix]);actual={str(p.relative_to(root)):sha(p) for p in (root/'Sources/SwiftJLS').rglob('*.swift')}
 ck(actual==br['swiftjls_file_sha256'] and len(actual)==38,'frozen production set '+prefix)
root=Path(br['repo_snapshot_dir']);actual={str(p.relative_to(root)):sha(p) for p in (root/'Tests/SwiftJLSTests').rglob('*.swift')}
ck(actual==br['test_file_sha256'] and len(actual)==31,'frozen test set')
ck(admission['source_and_test_pins']==br['swiftjls_file_sha256']|br['test_file_sha256'],'external full source/test pins')
ck(sha(Path(br['task_store_path']))==br['task_store_sha256'],'actual build task store')
ck(len(rows)==len(events)==plan['expected_processes']==9288,'process count')
expected=[(e,a) for e in plan['schedule'] for a in e['order']];known=set();data={};orders={};ops=['encode','decode','prepare','prepare_encode'];last_end=''
ck(len(expected)==9288 and len(plan['schedule'])==3096,'expanded schedule')
for i,(row,event,(entry,arm)) in enumerate(zip(rows,events,expected)):
 cid=entry['case']['id'];b=entry['block'];key=(cid,arm,b);ck(key not in known,'duplicate '+str(i));known.add(key)
 ck(row['case_id']==cid and row['block']==b and row['producer']==event['producer']==arm and event['entry']==entry,'schedule '+str(i));ck(row['order']==entry['order'] and row['position']==entry['position'] and row['permutation_index']==entry['permutation_index'],'order '+str(i));orders[b]=entry['order']
 ck(row['binary_sha256']==prod[arm]['sha256'],'binary '+str(i));ck(row['exit_code']==event['exit_code']==0 and row['stderr']==event['stderr']=='','exit '+str(i));ck(row['command']==event['command'],'command '+str(i))
 ck(row['command']==[prod[arm]['path'],'37','23',str(entry['case']['bits']),entry['case']['pattern'],'5','5',arm],'exact command '+str(i))
 raw=json.loads(event['stdout']);ck(all(row[k]==v for k,v in raw.items()),'stdout '+str(i))
 ck(all(row[k]==v for k,v in entry['case'].items() if k not in ['id','expected_encoded_bytes']),'profile '+str(i));ck(row['warmups']==row['iterations']==5 and row['end_to_end'] is True and row['encoded_bytes']==entry['case']['expected_encoded_bytes'] and row['label']==arm,'counts/fidelity '+str(i))
 ck(event['started_utc']>=last_end and event['completed_utc']>=event['started_utc'],'overlap '+str(i));last_end=event['completed_utc'];ck(all(row[k]==event[k] for k in ['started_utc','completed_utc','process_seconds']),'times '+str(i))
 for op in ops:
  vals=row[op+'_seconds'];ck(len(vals)==5 and all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in vals),'observations '+str(i));data[cid,arm,b,op]=vals
for i,q in enumerate([env['conditions']]+conditions+[c['end_conditions']]):
 ck(q['power']['exit_code']==0 and "Now drawing from 'AC Power'" in q['power']['output'],'power '+str(i));ck(q['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in q['thermal']['output'] and 'No performance warning level has been recorded' in q['thermal']['output'],'thermal '+str(i));ck(q['interfering_workload_matches']==[],'interference '+str(i));ck(q['simulator_inventory']['process_count']==0,'simulator '+str(i))
ck([q['completed_processes'] for q in conditions]==list(range(0,9289,18))+[9288],'condition cadence including duplicate final snapshot')
ck(collections.Counter(tuple(v) for v in orders.values())==collections.Counter({tuple(x):86 for x in plan['permutations']}),'permutation balance')
for b in range(516):
 es=[x for x in plan['schedule'] if x['block']==b]
 ck(len(es)==6 and len({x['case']['id'] for x in es})==6 and all(x['order']==orders[b] for x in es),'joint round '+str(b))
metrics={};cellcount=0;classification=collections.Counter()
for contrast,cases in summ.items():
 for case in cases:
  cid=case['case']['id']
  for op,m in case['operations'].items():
   ref=m['reference_arm'];cand=m['candidate_arm'];med={arm:median(v for b in range(516) for v in data[cid,arm,b,op]) for arm in plan['arms']};rat=med[cand]/med[ref]
   ck(all(eq(m['pooled_median_seconds'][arm],v) for arm,v in med.items()),'median '+contrast+cid+op);ck(eq(m['pooled_ratio'],rat),'ratio '+contrast+cid+op)
   pair=[median(data[cid,cand,b,op])/median(data[cid,ref,b,op]) for b in range(516)];deltas=[median(data[cid,cand,b,op])-median(data[cid,ref,b,op]) for b in range(516)]
   ck(eq(m['median_block_ratio'],median(pair)) and eq(m['median_block_delta_seconds'],median(deltas)),'paired summary '+contrast+cid+op)
   ck(all(eq(x,y) for x,y in zip(m['ratio_range'],[min(pair),max(pair)])) and all(eq(x,y) for x,y in zip(m['ratio_iqr'],[quantile(pair,.25),quantile(pair,.75)])) and m['blocks_above_1_05']==sum(x>1.05 for x in pair),'paired spread '+contrast+cid+op)
   ck(m['observations_per_arm']==2580 and m['paired_rounds']==516 and len(m['pairs'])==516,'point counts '+contrast+cid+op)
   for b,p in enumerate(m['pairs']):ck(p['block']==b and p['order']==orders[b] and eq(p['ratio'],pair[b]) and eq(p['delta_seconds'],deltas[b]) and eq(p['reference_median_seconds'],median(data[cid,ref,b,op])) and eq(p['candidate_median_seconds'],median(data[cid,cand,b,op])),'pair '+contrast+cid+op+str(b))
   def check_group(g,bs,tag):
    ck(eq(g['pooled_ratio'],median(v for b in bs for v in data[cid,cand,b,op])/median(v for b in bs for v in data[cid,ref,b,op])) and eq(g['median_block_ratio'],median(pair[b] for b in bs)),tag+contrast+cid+op)
   for label,g in m['order_groups'].items():
    a,z=label.split('_before_');bs=[b for b in range(516) if orders[b].index(a)<orders[b].index(z)];ck(g['rounds']==len(bs)==258,'order count');check_group(g,bs,'order ')
   for label,g in m['permutation_groups'].items():
    bs=[b for b in range(516) if '->'.join(orders[b])==label];ck(g['rounds']==len(bs)==86,'permutation count');check_group(g,bs,'permutation ')
   for g in m['temporal_groups']:check_group(g,list(range(g['first_round'],g['last_round']+1)),'temporal ')
   lo,hi=m['familywise_bonferroni_48_95'];status='within_measured_gate' if hi<=1.05 else ('confirmed_regression' if lo>1.05 else 'unresolved');ck(status==m['interpretation_family48'],'classification '+contrast+cid+op)
   key='|'.join([contrast,cid,op]);classification[status]+=1;metrics[key]={k:m[k] for k in ['pooled_ratio','pooled_median_seconds','familywise_bonferroni_48_95','interpretation_family48']};cellcount+=1
oldpath=Path('/Users/pushparaj/projects/SwiftJLS/Documentation/Engineering/CodecMigration/results/factory-qualification-2026-10-22/performance/short516-3arms-002/summary.json.gz')
old=json.loads(gzip.decompress(oldpath.read_bytes()));oldopen={};protected={}
for contrast,cases in old.items():
 for case in cases:
  for op,m in case['operations'].items():
   key='|'.join([contrast,case['case']['id'],op]);target=protected if m['interpretation_family48']=='within_measured_gate' else oldopen;target[key]={'previous':m['interpretation_family48'],'current':metrics[key]}
ck(len(oldopen)==11 and len(protected)==37,'historical partition')
replay=json.loads((O/'candidate004-short516-bootstrap-replay/replay-receipt.json').read_text());ck(replay['exit_code']==0 and all(v['byte_identical'] for v in replay['comparisons'].values()),'exact replay')
partials={}
for name in ['diag72-001','short516-001','larger15-001']:
 d=R.parents[2]/'campaigns/runs'/name;it=json.loads((d/'interrupted.json').read_text());files={p.name:{'bytes':p.stat().st_size,'sha256':sha(p)} for p in d.iterdir() if p.is_file()};n=sum(1 for _ in (d/'raw.jsonl').open());partials[name]={'retained_processes':n,'complete_json_present':(d/'complete.json').exists(),'interrupted_keys':list(it),'files':files};ck(not (d/'complete.json').exists(),'partial complete '+name)
ck(all(sha(R/f)==h for f,h in initial_hashes.items()),'campaign unchanged during audit')
unresolved=summ['candidate_vs_three_change'][2]['operations']['decode'];ck(summ['candidate_vs_three_change'][2]['case']['id']=='p12-noise','unresolved index')
res={'campaign':str(R),'checks':checks,'errors':errors,'processes':len(rows),'conditions':len(conditions),'metrics_recomputed':cellcount,'pair_records_recomputed':cellcount*516,'counts':dict(classification),'original_11_now_pass':sum(v['current']['interpretation_family48']=='within_measured_gate' for v in oldopen.values()),'protected_37_now_counts':dict(collections.Counter(v['current']['interpretation_family48'] for v in protected.values())),'original_findings':oldopen,'all48_metrics':metrics,'unresolved_detail':{k:v for k,v in unresolved.items() if k!='pairs'},'wall_seconds':(datetime.datetime.fromisoformat(events[-1]['completed_utc'])-datetime.datetime.fromisoformat(events[0]['started_utc'])).total_seconds(),'cpu_sum_ps_min_max':[min(q['summed_cpu_percent'] for q in conditions),max(q['summed_cpu_percent'] for q in conditions)],'source_guards':env['source_guards'],'bootstrap_replay_receipt':str(O/'candidate004-short516-bootstrap-replay/replay-receipt.json'),'partial_runs_retained_without_outcome_analysis':partials,'campaign_hashes':initial_hashes,'historical_summary_sha256':sha(oldpath)}
(O/'candidate004-short516-independent-results.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps({k:res[k] for k in ['checks','errors','processes','conditions','metrics_recomputed','pair_records_recomputed','counts','original_11_now_pass','protected_37_now_counts','wall_seconds','cpu_sum_ps_min_max']},indent=2))
print('partials', {k:v['retained_processes'] for k,v in partials.items()})
