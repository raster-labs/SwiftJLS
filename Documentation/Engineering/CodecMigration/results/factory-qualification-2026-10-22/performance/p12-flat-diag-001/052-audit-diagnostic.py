from pathlib import Path
import json,hashlib,statistics,math,collections,random,datetime
D=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/campaigns/p12-flat-diag-001');O=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022');S=D.parent.parent/'p12_flat_prepare_encode_diag_001'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest();read=lambda n:json.loads((D/n).read_text());jl=lambda n:[json.loads(x) for x in (D/n).read_text().splitlines()]
errors=[]
def ck(x,m):
 if not x:errors.append(m)
def eq(a,b,m):ck(math.isclose(a,b,rel_tol=2e-14,abs_tol=1e-18),m)
def med(v):return statistics.median(v)
def quant(v,q):
 x=sorted(v);pos=(len(x)-1)*q;a=int(pos);return x[a]+(x[min(a+1,len(x)-1)]-x[a])*(pos-a)
plan=read('frozen_schedule.json');done=read('complete.json');env=read('environment.json');summary=read('summary.json');meta=read('bootstrap-metadata.json');rows=jl('raw.jsonl');events=jl('events.jsonl');conditions=jl('conditions.jsonl');approved=json.loads((O/'049-runner-independent-preflight.json').read_text())['pins_after'];prep=json.loads((S/'prepare-receipt.json').read_text())
for f,k in [('raw.jsonl','raw_jsonl_sha256'),('events.jsonl','events_jsonl_sha256'),('conditions.jsonl','conditions_jsonl_sha256'),('summary.json','summary_json_sha256'),('bootstrap-metadata.json','bootstrap_metadata_json_sha256'),('frozen_schedule.json','schedule_sha256'),('frozen_runner.py','runner_sha256'),('frozen_analyse.py','analysis_sha256')]:ck(sha(D/f)==done[k],f+' complete hash')
for f,a in [('frozen_runner.py','p12_flat_diag_runner.py'),('frozen_analyse.py','p12_flat_diag_analyse.py'),('frozen_schedule.json','p12-flat-diag-001.json')]:ck(sha(D/f)==approved[a],f+' approved pin')
ck(done['completed'] and done['processes']==504 and len(rows)==len(events)==504,'exact completed count');ck(done['source_guards']==env['source_guards'],'source guards start/end')
for arm,a in prep['arms'].items():
 root=Path(a['package_dir']);actual={str(f.relative_to(root)):sha(f) for f in sorted((root/'Sources/SwiftJLS').rglob('*.swift'))};ck(actual==a['swiftjls_files'],arm+' source set/hashes')
 for p,h in [(a['copied_binary_path'],a['binary_sha256']),(a['built_binary_path'],a['binary_sha256']),(a['task_store_path'],a['task_store_sha256']),(a['consumer_path'],a['consumer_sha256']),(root/'Package.swift',a['package_swift_sha256'])]:ck(sha(p)==h,arm+' file pin '+str(p))
 for v in a['patches'].values():ck(sha(v['path'])==v['sha256'],arm+' patch')
 ck(env['source_guards']['arms_verified'][arm]['binary_sha256']==a['binary_sha256']==plan['producers'][arm]['sha256'],arm+' campaign binding')
ck(sha(S/'prepare-receipt.json')==env['source_guards']['prepare_receipt_sha256'],'prepare pin')
for name,h in [('build_events_jsonl','build_events_sha256'),('smoke_receipts_json','smoke_receipts_sha256')]:ck(sha(prep[name])==prep[h],name+' pin')
arms=plan['arms'];orders=[arms[i:]+arms[:i] for i in range(6)];rev=arms[::-1];orders +=[rev[i:]+rev[:i] for i in range(6)];exp=[{'stratum_index':i,'order':order} for i,order in enumerate(orders) for k in range(7)];random.Random(20261022045).shuffle(exp)
for b,(a,z) in enumerate(zip(plan['schedule'],exp)):ck(a['block']==b and a['stratum_index']==z['stratum_index'] and a['order']==z['order'],'schedule '+str(b))
lookup={};sizecounts=collections.Counter();durations={};timeline=[]
extra=['case_id','producer','block','position','stratum_index','order','binary_sha256','command','exit_code','stderr','started_utc','process_seconds','completed_utc']
for i,(row,event) in enumerate(zip(rows,events)):
 b,pos=divmod(i,6);entry=plan['schedule'][b];arm=entry['order'][pos];key=(b,arm);ck(key not in lookup,'unique'+str(key));lookup[key]=row
 ck(event['sequence']==i and event['entry']==entry and event['position']==pos and event['producer']==arm,'event schedule '+str(i))
 cmd=[plan['producers'][arm]['path'],'37','23','12','flat','5','5',arm];ck(row['command']==event['command']==cmd,'command'+str(i));ck(row['binary_sha256']==event['binary_sha256']==plan['producers'][arm]['sha256'],'binary'+str(i));ck(row['exit_code']==event['exit_code']==0 and row['stderr']==event['stderr']=='','exit/stderr'+str(i))
 out=json.loads(event['stdout']);ck({k:v for k,v in row.items() if k not in extra}==out,'raw stdout'+str(i))
 for k in ['started_utc','completed_utc','process_seconds']:ck(row[k]==event[k],k+str(i))
 ck(row['block']==b and row['position']==pos and row['order']==entry['order'] and row['stratum_index']==entry['stratum_index'],'raw schedule'+str(i))
 for k,v in {'case_id':'p12-flat','width':37,'height':23,'bits':12,'pattern':'flat','components':1,'near':0,'interleave':0,'warmups':5,'iterations':5,'end_to_end':True,'encoded_bytes':56,'label':arm,'resource_profile':'successor-workspace-1GiB-memory-2GiB-v1'}.items():ck(row[k]==v,k+str(i))
 vecs=['encode','decode','prepare','prepare_encode']+(['fresh_entry','fresh_body','fresh_exit'] if arm.endswith('_inst') else [])
 for op in vecs:ck(len(row[op+'_seconds'])==5 and all(math.isfinite(v) for v in row[op+'_seconds']),op+str(i))
 row['fresh_encode_seconds']=[a-b for a,b in zip(row['prepare_encode_seconds'],row['prepare_seconds'])]
 if arm.endswith('_inst'):
  for k in range(5):eq(row['fresh_encode_seconds'][k],sum(row[op+'_seconds'][k] for op in ['fresh_entry','fresh_body','fresh_exit']),f'telescoping {i}/{k}')
 ck(row['started_utc']<row['completed_utc'],'timestamps'+str(i));timeline.append((row['started_utc'],row['completed_utc']));sizecounts[(arm,row['encoded_bytes'])]+=1
for a,b in zip(timeline,timeline[1:]):ck(a[1]<=b[0],'no overlap')
def samples(arm,op,blocks=range(84)):return [v for b in blocks for v in lookup[b,arm][op+'_seconds']]
for arm in arms:durations[arm]={op:med(samples(arm,op)) for op in ['encode','decode','prepare','fresh_encode','prepare_encode']}
endpoint_values=[]
for contrast,ops in summary['ordinary_contrasts'].items():
 for op,s in ops.items():
  ref=s['reference_arm'];cand=s['candidate_arm'];rv=samples(ref,op);cv=samples(cand,op);ratio=med(cv)/med(rv);deltas=[];pairrat=[]
  eq(med(rv),s['pooled_median_seconds'][ref],contrast+op+' refmed');eq(med(cv),s['pooled_median_seconds'][cand],contrast+op+' candmed');eq(ratio,s['pooled_ratio'],contrast+op+' pooledratio')
  for b,p in enumerate(s['pairs']):
   rm=med(lookup[b,ref][op+'_seconds']);cm=med(lookup[b,cand][op+'_seconds']);pairrat.append(cm/rm);deltas.append(cm-rm);eq(rm,p['reference_median_seconds'],'rmed');eq(cm,p['candidate_median_seconds'],'cmed');eq(cm/rm,p['ratio'],'pairratio');eq(cm-rm,p['delta_seconds'],'delta')
  eq(med(pairrat),s['median_block_ratio'],'pairedmedian');eq(med(deltas),s['median_block_delta_seconds'],'deltamedian');ck([min(pairrat),max(pairrat)]==s['ratio_range'],'range');ck(sum(v>1.05 for v in pairrat)==s['blocks_above_1_05'],'countslower');
  for q,x in zip([.25,.75],s['ratio_iqr']):eq(quant(pairrat,q),x,'iqr')
  for key,g in s['order_groups'].items():
   refbefore=key.startswith(ref+'_before_');bs=[b for b in range(84) if (plan['schedule'][b]['order'].index(ref)<plan['schedule'][b]['order'].index(cand))==refbefore];ck(len(bs)==g['blocks']==42,'order count');eq(med(samples(cand,op,bs))/med(samples(ref,op,bs)),g['pooled_ratio'],'order med')
  for key,g in s['stratum_groups'].items():
   sn=int(key.split('_')[1]);bs=[b for b in range(84) if plan['schedule'][b]['stratum_index']==sn];ck(len(bs)==g['blocks']==7,'stratum count');eq(med(samples(cand,op,bs))/med(samples(ref,op,bs)),g['pooled_ratio'],'stratum med')
  for g in s['temporal_groups']:
   bs=range(g['first_block'],g['last_block']+1);eq(med(samples(cand,op,bs))/med(samples(ref,op,bs)),g['pooled_ratio'],'temporal med')
for phase,s in summary['instrumented_subphases'].items():
 ref=s['reference_arm'];cand=s['candidate_arm'];d=[(med(lookup[b,cand][phase+'_seconds'])-med(lookup[b,ref][phase+'_seconds']))*1e9 for b in range(84)]
 eq(med(samples(cand,phase))/med(samples(ref,phase)),s['pooled_ratio'],'inst ratio');eq(med(d),s['median_block_delta_ns'],'inst delta');ck('pooled_delta_ns_familywise_bonferroni_29_95' not in s,'no undeclared inference')
 for b,p in enumerate(s['pairs']):eq(d[b],p['delta_ns'],'inst paired delta')
for name,ops in summary['descriptive_instrumentation_perturbation'].items():
 for op,s in ops.items():
  ref=s['control_arm'];cand=s['instrumented_arm'];eq(med(samples(cand,op))/med(samples(ref,op)),s['pooled_ratio'],'perturbationratio');ck(s['descriptive_only'],'perturbationdescriptive')
for i,e in enumerate(summary['declared_29_endpoints'],1):
 ck(e['endpoint_index']==i and e['available'],'endpoint index/available');lo,hi=e['familywise_bonferroni_29_95'];expected=('within_measured_gate' if hi<=1.05 else 'confirmed_regression' if lo>1.05 else 'unresolved') if e['type']=='ratio' else ('positive_delta_confirmed' if lo>0 else 'negative_delta_confirmed' if hi<0 else 'spans_zero');ck(e['interpretation_family29']==expected,'decision '+str(i));endpoint_values.append(e)
ck(len(endpoint_values)==29,'family29');ck(meta['resamples']==50000 and meta['seed']==20261022 and meta['simultaneous_family_29']==29 and meta['strata']==12 and meta['blocks_per_stratum']==7 and meta['observations_per_process']==5,'bootstrap params');eq(meta['tail_probability_29'],.05/58,'tail');ck(meta['raw_sha256']==sha(D/'raw.jsonl') and meta['summary_sha256']==sha(D/'summary.json') and meta['schedule_sha256']==sha(D/'frozen_schedule.json'),'metadatahashes')
allcond=[env['conditions']]+conditions+[done['end_conditions']]
for c in allcond:ck(c['power']['exit_code']==0 and "Now drawing from 'AC Power'" in c['power']['output'] and c['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in c['thermal']['output'] and 'No performance warning level has been recorded' in c['thermal']['output'],'condition admission')
ck([c['completed_processes'] for c in conditions]==list(range(0,505,72)),'condition coverage')
cpu=collections.defaultdict(float)
for c in allcond:
 for q in c['processes_above_10_percent']:cpu[q['comm']]=max(cpu[q['comm']],q['cpu'])
r={'errors':errors,'counts':{'raw':len(rows),'events':len(events),'conditions':len(conditions),'endpoints':len(endpoint_values)},'first_start':timeline[0][0],'last_finish':timeline[-1][1],'dispositions':dict(collections.Counter(e['interpretation_family29'] for e in endpoint_values)),'ordinary_medians_seconds':durations,'endpoints':endpoint_values,'instrumentation_perturbation':summary['descriptive_instrumentation_perturbation'],'summed_cpu_range':[min(c['summed_cpu_percent'] for c in allcond),max(c['summed_cpu_percent'] for c in allcond)],'top_cpu_processes':sorted(cpu.items(),key=lambda x:x[1],reverse=True)[:8],'complete_sha256':sha(D/'complete.json')}
(O/'052-independent-results.json').write_text(json.dumps(r,indent=2)+'\n');print('errors',errors);print('counts',r['counts'],'dispositions',r['dispositions']);print('CPU',r['summed_cpu_range']);print('timing',r['first_start'],r['last_finish'])
