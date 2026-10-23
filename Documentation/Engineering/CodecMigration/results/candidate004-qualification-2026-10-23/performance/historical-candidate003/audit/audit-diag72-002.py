from pathlib import Path
import collections,datetime,hashlib,json,math,statistics
R=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/campaigns/runs/diag72-002')
O=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
load=lambda f:json.loads((R/f).read_text())
lines=lambda f:[json.loads(l) for l in (R/f).read_text().splitlines()]
c=load('complete.json');plan=load('frozen_schedule.json');summ=load('summary.json');env=load('environment.json');rows=lines('raw.jsonl');events=lines('events.jsonl');conditions=lines('conditions.jsonl');errors=[]
def ck(v,msg):
 if not v:errors.append(msg)
def eq(a,b):return math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-20)
for f,k in [('raw.jsonl','raw_jsonl_sha256'),('events.jsonl','events_jsonl_sha256'),('conditions.jsonl','conditions_jsonl_sha256'),('summary.json','summary_json_sha256'),('frozen_schedule.json','schedule_sha256'),('frozen_runner.py','runner_sha256'),('frozen_analyse.py','analysis_sha256'),('frozen_preflight_receipt.json','preflight_receipt_sha256')]:ck(sha(R/f)==c[k],'hash '+f)
ck(len(rows)==len(events)==1728,'process count');expected=[(e,a) for e in plan['schedule'] for a in e['order']];known=set();data={};ops=['encode','decode','prepare','prepare_encode'];last_end=''
for i,(row,event,(entry,arm)) in enumerate(zip(rows,events,expected)):
 key=(row['case_id'],arm,row['block']);ck(key not in known,'duplicate '+str(i));known.add(key)
 ck(row['producer']==event['producer']==arm and event['entry']==entry,'schedule '+str(i));ck(row['order']==entry['order'] and row['position']==entry['position'] and row['permutation_index']==entry['permutation_index'],'order '+str(i))
 ck(row['binary_sha256']==plan['producers'][arm]['sha256'],'binary '+str(i));ck(row['exit_code']==event['exit_code']==0 and row['stderr']==event['stderr']=='','exit '+str(i));ck(row['command']==event['command'],'command '+str(i))
 ck(row['command']==[plan['producers'][arm]['path'],'37','23',str(entry['case']['bits']),entry['case']['pattern'],'5','5',arm],'exact command '+str(i))
 raw=json.loads(event['stdout']);ck(all(row[k]==v for k,v in raw.items()),'stdout '+str(i))
 ck(all(row[k]==v for k,v in entry['case'].items() if k not in ['id','expected_encoded_bytes']),'profile '+str(i));ck(row['warmups']==row['iterations']==5 and row['end_to_end'] is True and row['encoded_bytes']==entry['case']['expected_encoded_bytes'],'counts/fidelity '+str(i))
 ck(event['started_utc']>=last_end,'overlap '+str(i));last_end=event['completed_utc'];ck(row['started_utc']==event['started_utc'] and row['completed_utc']==event['completed_utc'],'times '+str(i))
 for op in ops:
  vals=row[op+'_seconds'];ck(len(vals)==5 and all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in vals),'observations '+str(i));data[(row['case_id'],arm,row['block'],op)]=vals
 data[(row['case_id'],arm,row['block'],'fresh_encode')]=[a-b for a,b in zip(row['prepare_encode_seconds'],row['prepare_seconds'])]
for i,q in enumerate([env['conditions']]+conditions+[c['end_conditions']]):
 ck(q['power']['exit_code']==0 and "Now drawing from 'AC Power'" in q['power']['output'],'power '+str(i));ck(q['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in q['thermal']['output'] and 'No performance warning level has been recorded' in q['thermal']['output'],'thermal '+str(i));ck(q['interfering_workload_matches']==[],'interference '+str(i))
 ck(q['simulator_inventory']['process_count']==0,'simulator '+str(i))
metrics={};cellcount=0
for contrast,cases in summ['comparisons'].items():
 metrics[contrast]={}
 for case in cases:
  cid=case['case']['id']
  for op,m in case['operations'].items():
   ref=m['reference_arm'];cand=m['candidate_arm'];med={arm:statistics.median(v for b in range(72) for v in data[cid,arm,b,op]) for arm in plan['arms']};rat=med[cand]/med[ref]
   ck(all(eq(m['pooled_median_seconds'][arm],v) for arm,v in med.items()),'median '+contrast+cid+op);ck(eq(m['pooled_ratio'],rat),'ratio '+contrast+cid+op)
   pair=[statistics.median(data[cid,cand,b,op])/statistics.median(data[cid,ref,b,op]) for b in range(72)]
   ck(eq(m['median_block_ratio'],statistics.median(pair)) and all(eq(x,y) for x,y in zip(m['ratio_range'],[min(pair),max(pair)])),'paired summary '+contrast+cid+op)
   ck(len(m['pairs'])==72 and all(eq(p['ratio'],pair[b]) and p['block']==b for b,p in enumerate(m['pairs'])),'pairs '+contrast+cid+op)
   for group in m['order_groups'].values():ck(group['rounds']==36,'order count')
   if op in ops:metrics[contrast][cid+'--'+op]=rat
   cellcount+=1
res={'errors':errors,'processes':len(rows),'conditions':len(conditions),'pooled_and_paired_metrics_recomputed':cellcount,'descriptive_primary_points':metrics,'candidate_vs_three_max':max(metrics['candidate_vs_three_change'].values()),'aa_points_over_1_05':{k:v for k,v in metrics['factory_002_aa_vs_factory_002'].items() if v>1.05},'aa_min_max':[min(metrics['factory_002_aa_vs_factory_002'].values()),max(metrics['factory_002_aa_vs_factory_002'].values())],'candidate_combined_vs_factory':{k:v for k,v in metrics['candidate_vs_factory_002'].items() if k.endswith('--prepare_encode')},'aa_combined':{k:v for k,v in metrics['factory_002_aa_vs_factory_002'].items() if k.endswith('--prepare_encode')},'wall_seconds':(datetime.datetime.fromisoformat(events[-1]['completed_utc'])-datetime.datetime.fromisoformat(events[0]['started_utc'])).total_seconds(),'cpu_sum_min_max':[min(q['summed_cpu_percent'] for q in conditions),max(q['summed_cpu_percent'] for q in conditions)],'summary_sha256':sha(R/'summary.json'),'raw_sha256':sha(R/'raw.jsonl')}
(O/'diag72-002-independent-results.json').write_text(json.dumps(res,indent=2)+'\n')
print(json.dumps({k:v for k,v in res.items() if k!='descriptive_primary_points'},indent=2))
