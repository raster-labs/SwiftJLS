#!/usr/bin/env python3
"""Independent candidate005 evidence audit. Collection must finish before non-synthetic execution."""
import argparse,collections,datetime,hashlib,importlib.util,json,math,pathlib,statistics,subprocess,sys
OPS=['encode','decode','prepare','prepare_encode']
FREEZE='71487cb4d5272ef0791e04aeeada506ec94ade2fa244f3ec2791539674b0a948'
PYTHON='/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3'
def require(v,m):
 if not v:raise RuntimeError(m)
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(pathlib.Path(p).read_text())
def lines(p):return [json.loads(x) for x in pathlib.Path(p).read_text().splitlines()]
def write(p,v):pathlib.Path(p).write_text(json.dumps(v,indent=2)+'\n')
def close(x,y):return math.isclose(x,y,rel_tol=1e-13,abs_tol=0.)
def status(ci):return 'within_measured_gate' if ci[1]<=1.05 else 'confirmed_regression' if ci[0]>1.05 else 'unresolved'
def profile(report,case,label,size=None):
 for k in ['width','height','bits','pattern','components','near','interleave']:require(report[k]==case[k],'Profile '+k)
 require(report['label']==label and report['warmups']==5 and report['iterations']==5 and report['end_to_end'] is True,'Consumer boundary/repetition')
 require(report['resource_profile']=='successor-workspace-1GiB-memory-2GiB-v1','Resource profile')
 require(type(report['peak_process_rss_bytes']) is int and report['peak_process_rss_bytes']>0,'Full-process RSS')
 if size is not None:require(report['encoded_bytes']==size,'Encoded size')
 for op in OPS:
  vs=report[op+'_seconds'];require(len(vs)==5 and all(type(v) in (int,float) and math.isfinite(v) and v>0 for v in vs),'Five finite positive samples')
 require(all(a>=b for a,b in zip(report['prepare_encode_seconds'],report['prepare_seconds'])),'Combined timing')
def compare_report(report,row):
 for k,v in report.items():require(k in row and row[k]==v,'Raw changed from stdout: '+k)
def counts_and_events(kind,run,plan,raw,events):
 expected=18576 if kind=='short' else 120 if kind=='larger' else 2112
 require(len(raw)==len(events)==expected,'Complete counts '+kind)
 if kind=='rss':scheduled=plan['processes']
 else:scheduled=[(e,arm) for e in plan['schedule'] for arm in e['order']]
 require(len(scheduled)==expected,'Schedule count')
 previous_end=None
 for n,(r,e,s) in enumerate(zip(raw,events,scheduled)):
  require(e['exit_code']==0,'Nonzero process');report=json.loads(e['stdout'])
  require(e['started_utc']<=e['completed_utc'] and e['process_seconds']>=0,'Process chronology')
  if previous_end is not None:require(previous_end<=e['started_utc'],'Overlapping processes')
  previous_end=e['completed_utc']
  if kind=='rss':
   require(e['entry']==s,'RSS schedule/event order');require(all(r[k]==v for k,v in s.items()),'RSS raw schedule')
   require(r['report']==report,'RSS raw/stdout');profile(report,plan['fixture'],s['label'],410542)
   command=[s['binary_path'],'512','512','12','noise','5','5',s['label'],'1','0','0']
  else:
   entry,arm=s;case=entry['case'];require(e['entry']==entry and e['producer']==arm,'Schedule/event order')
   require(r['producer']==arm and r['case_id']==case['id'] and r['block']==entry['block'] and r['position']==entry['position'] and r['order']==entry['order'],'Raw schedule order')
   require(r['binary_sha256']==plan['producers'][arm]['sha256'],'Raw binary')
   require(r['exit_code']==0 and r['stderr']==e['stderr'],'Raw process receipt')
   compare_report(report,r);profile(report,case,arm,case['expected_encoded_bytes'] if kind=='short' else None)
   command=[plan['producers'][arm]['path'],str(case['width']),str(case['height']),str(case['bits']),case['pattern'],'5','5',arm]
   if kind=='larger':command += [str(case['components']),str(case['near']),str(case['interleave'])]
   require(r['command']==command,'Raw command')
  require(e['command']==command,'Executed command')
  for k in ['started_utc','completed_utc','process_seconds']:require(r[k]==e[k],'Raw/event receipt '+k)
 return {'records':expected,'all_scheduled_processes_retained':True,'event_raw_report_identity':True,'all_five_observations_retained':True,'fidelity_checks_exit_zero':True,'elapsed_process_window_seconds':(datetime.datetime.fromisoformat(events[-1]['completed_utc'])-datetime.datetime.fromisoformat(events[0]['started_utc'])).total_seconds()}
def conditions_review(run):
 cs=lines(run/'conditions.jsonl');env=load(run/'environment.json');complete=load(run/'complete.json');extras=[]
 for container in [env,complete]:
  for k in ['conditions','start_conditions','end_conditions']:
   if k in container:extras.append(container[k])
 require(cs,'No conditions')
 hot={};cpu=[];completed=[]
 for c in cs+extras:
  require(c['power']['exit_code']==0 and "Now drawing from 'AC Power'" in c['power']['output'],'AC conditions')
  require(c['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in c['thermal']['output'] and 'No performance warning level has been recorded' in c['thermal']['output'],'Thermal conditions')
  require(not c.get('interfering_workload_matches',[]),'Recorded host guard violation')
  cpu.append(c['summed_cpu_percent'])
  if 'completed_processes' in c:completed.append(c['completed_processes'])
  for p in c.get('processes_above_10_percent',[]):
   key=(p.get('exe_name',''),p.get('full_command',''))
   hot[key]=max(hot.get(key,0),p['cpu'])
 require(completed==sorted(completed),'Condition record completion order')
 return {'condition_records':len(cs),'all_recorded_admissions_passed':True,'summed_ps_cpu_percent_range':[min(cpu),max(cpu)],'highest_observed_process_cpu':[{'exe':k[0],'command':k[1],'max_ps_cpu_percent':v} for k,v in sorted(hot.items(),key=lambda x:x[1],reverse=True)[:12]],'host_scope':'Shared services active; sampled guard admission is not proof of host idleness; ps CPU and container CPU have different scopes.'}
def freeze_check(kind,run,package):
 require(sha(run/'campaign-freeze.json')==sha(package/'campaign-freeze.json')==FREEZE,'Package freeze mismatch')
 mapping={'frozen_schedule.json':f'schedules/{"short1032-3arms" if kind=="short" else "larger15-guard" if kind=="larger" else "rss528-4arms"}-005.json'}
 if kind=='rss':mapping.update({n:n for n in ['rss528_runner.py','rss528_analyse.py','diag72_runner.py','campaign_identity.py','identity.json']})
 else:
  mapping.update({'frozen_runner.py':'short1032_runner.py' if kind=='short' else 'larger15_runner.py','frozen_shared_helper.py':'diag72_runner.py','campaign_identity.py':'campaign_identity.py','identity.json':'identity.json'})
  if kind=='short':mapping['frozen_analyse.py']='short1032_analyse.py'
  else:mapping['frozen_larger_guard_plan.json']='larger-guard-plan.json'
 for a,b in mapping.items():require(sha(run/a)==sha(package/b),'Frozen copy differs '+a)
 complete=load(run/'complete.json');require(complete['completed'] is True,'Incomplete run')
 hashes={n:sha(run/n) for n in ['raw.jsonl','events.jsonl','conditions.jsonl','summary.json','frozen_schedule.json']}
 keys={'raw.jsonl':'raw_jsonl_sha256','events.jsonl':'events_jsonl_sha256','conditions.jsonl':'conditions_jsonl_sha256','summary.json':'summary_json_sha256'}
 for n,h in hashes.items():
  if kind=='rss':require(complete['hashes'][n]==h,'Complete hash '+n)
  elif n in keys:require(complete[keys[n]]==h,'Complete hash '+n)
 require(complete['processes']==(18576 if kind=='short' else 120 if kind=='larger' else 2112),'Complete count')
 return hashes

def replay(kind,run,out):
 target=out/(kind+'-replay');target.mkdir()
 if kind=='short':
  (target/'raw.jsonl').symlink_to(run/'raw.jsonl');cmd=[PYTHON,str(run/'frozen_analyse.py'),'--output',str(target),'--schedule',str(run/'frozen_schedule.json')]
 else:cmd=[PYTHON,str(run/'rss528_analyse.py'),'--raw',str(run/'raw.jsonl'),'--output',str(target/'summary.json')]
 with (target/'stdout').open('w') as o,(target/'stderr').open('w') as e:p=subprocess.run(cmd,stdout=o,stderr=e)
 write(target/'command.json',{'command':cmd,'exit_code':p.returncode});require(p.returncode==0,'Frozen replay failed '+kind)
 require(load(target/'summary.json')==load(run/'summary.json'),'Replay summary differs '+kind)
 if kind=='short':require(load(target/'bootstrap-metadata.json')==load(run/'bootstrap-metadata.json'),'Bootstrap metadata differs')
 return {'exact_replay_equal':True,'replay_summary_sha256':sha(target/'summary.json')}

def short_metrics(raw,summary):
 grouped=collections.defaultdict(list)
 for r in raw:
  for op in OPS:grouped[(r['case_id'],op,r['producer'])].extend(r[op+'_seconds'])
 result=[]
 process_rows={(r['case_id'],r['producer'],r['block']):r for r in raw}
 for comp,cases in summary.items():
  ref='pinned' if comp=='candidate_vs_pinned' else 'three_change'
  for case in cases:
   cid=case['case']['id']
   for op,v in case['operations'].items():
    require(v['observations_per_arm']==5160 and v['paired_rounds']==1032,'Short sample count')
    for arm in ['pinned','three_change','candidate']:require(statistics.median(grouped[(cid,op,arm)])==v['pooled_median_seconds'][arm],'Independent short median')
    ratio=statistics.median(grouped[(cid,op,'candidate')])/statistics.median(grouped[(cid,op,ref)])
    require(ratio==v['pooled_ratio'],'Independent short ratio');ci=v['familywise_bonferroni_48_95'];require(status(ci)==v['interpretation_family48'],'Independent48 classification')
    require(len(v['pairs'])==1032 and all(g['rounds']==172 for g in v['permutation_groups'].values()) and all(g['rounds']==516 for g in v['order_groups'].values()),'Short diagnostic counts')
    require(len(v['temporal_groups'])==12,'Short temporal groups')
    for pair in v['pairs']:
     b=pair['block'];x=statistics.median(process_rows[(cid,ref,b)][op+'_seconds']);y=statistics.median(process_rows[(cid,'candidate',b)][op+'_seconds'])
     require(pair['reference_median_seconds']==x and pair['candidate_median_seconds']==y and pair['ratio']==y/x,'Independent short paired medians')
    result.append({'comparison':comp,'case':cid,'operation':op,'ratio':ratio,'family48_interval':ci,'status':status(ci),'order_ratios':{k:g['pooled_ratio'] for k,g in v['order_groups'].items()},'temporal_ratio_range':[min(g['pooled_ratio'] for g in v['temporal_groups']),max(g['pooled_ratio'] for g in v['temporal_groups'])]})
 require(len(result)==48,'Missing48 family')
 return {'counts':dict(collections.Counter(x['status'] for x in result)),'findings':[x for x in result if x['status']!='within_measured_gate'],'all48':result}
def larger_metrics(raw,summary):
 points=[];sizes=[]
 for case in summary:
  cid=case['case']['id'];rs=[r for r in raw if r['case_id']==cid];require(len(rs)==8,'Larger case count')
  for arm in ['reference','candidate']:
   require({r['block'] for r in rs if r['producer']==arm}==set(range(4)),'Larger complete blocks')
   require({r['encoded_bytes'] for r in rs if r['producer']==arm}=={case['encoded_bytes'][arm]},'Larger size summary')
  sizes.append({'case':cid,**case['encoded_bytes']})
  for op,v in case['operations'].items():
   meds={arm:statistics.median(x for r in rs if r['producer']==arm for x in r[op+'_seconds']) for arm in ['reference','candidate']}
   require(meds==v['pooled_median_seconds'] and meds['candidate']/meds['reference']==v['pooled_ratio'],'Independent larger pooled median')
   for pair in v['pairs']:
    pr={r['producer']:statistics.median(r[op+'_seconds']) for r in rs if r['block']==pair['block']};require(pr['candidate']/pr['reference']==pair['ratio'],'Independent larger pair')
   require(v['observations_per_producer']==20 and len(v['pairs'])==4,'Larger sample count')
   points.append({'case':cid,'operation':op,'ratio':v['pooled_ratio'],'max_pair_ratio':max(x['ratio'] for x in v['pairs']),'order_median_ratios':v['median_ratio_by_first_producer']})
 require(len(points)==60,'Larger60 points')
 return {'points':60,'pooled_above_1_05':[p for p in points if p['ratio']>1.05],'maximum_pooled_point':max(points,key=lambda p:p['ratio']),'unexpected_sizes':[s for s in sizes if s['unexpected_from_archived_sizes_flag']],'sizes':sizes,'all60':points}
def rss_metrics(raw,summary):
 vals={label:[r['report']['peak_process_rss_bytes'] for r in raw if r['label']==label] for label in ['62309d3','e66f7da','candidate','candidate-copy']}
 for label,x in vals.items():require(len(x)==528 and {r['block'] for r in raw if r['label']==label}==set(range(528)),'RSS528 complete blocks')
 contrasts=summary['contrasts'];aa=contrasts['candidate_copy_vs_candidate'];ci=aa['bonferroni_95_interval'];review=not(ci[0]<=1<=ci[1]) or abs(aa['median_rss_ratio']-1)>0.05 or abs(aa['overall_max_rss_ratio']-1)>0.05 or ci[0]>1.05 or ci[1]<1/1.05
 result={}
 for name,v in contrasts.items():
  x=vals[v['reference_label']];y=vals[v['candidate_label']];require(statistics.median(y)/statistics.median(x)==v['median_rss_ratio'] and max(y)/max(x)==v['overall_max_rss_ratio'],'Independent RSS median/maximum')
  ci=v['bonferroni_95_interval']
  if name=='candidate_copy_vs_candidate':state='control_review_required' if review else 'control_within_expected_unity'
  elif ci[0]>1.05:state='confirmed_measured_regression'
  elif ci[1]<=1.05 and max(y)/max(x)<=1.05:state='open_blocked_by_aa_control_review' if review else 'within_finite_criterion'
  else:state='open_interval_overlap_or_max_trigger'
  require(state==v['disposition'],'Independent RSS classification')
  result[name]={'median_ratio':v['median_rss_ratio'],'interval':ci,'overall_max_ratio':v['overall_max_rss_ratio'],'disposition':state}
 both=all(result[n]['disposition']=='within_finite_criterion' for n in ['candidate_vs_623','candidate_vs_e66']);require(both==summary['disposition_summary']['candidate_within_finite_criterion_vs_both_baselines'],'RSS final criterion')
 return {'contrasts':result,'aa_control_review_required':review,'candidate_within_finite_criterion_vs_both_baselines':both}

def self_test():
 require(status([.9,1.05])=='within_measured_gate' and status([1.050001,1.2])=='confirmed_regression' and status([1.05,1.2])=='unresolved','Threshold controls')
 c={'width':37,'height':23,'bits':12,'pattern':'noise','components':1,'near':0,'interleave':0};r=dict(c,label='candidate',warmups=5,iterations=5,end_to_end=True,resource_profile='successor-workspace-1GiB-memory-2GiB-v1',peak_process_rss_bytes=12345,encoded_bytes=1574,**{op+'_seconds':[1.,2.,3.,4.,5.] for op in OPS});profile(r,c,'candidate',1574);compare_report(r,dict(r,producer='candidate'))
 bad=dict(r,decode_seconds=[1.,2.])
 try:profile(bad,c,'candidate',1574)
 except RuntimeError:pass
 else:raise RuntimeError('Censoring control failed')
 try:compare_report(r,dict(r,encoded_bytes=1))
 except RuntimeError:pass
 else:raise RuntimeError('Report alteration control failed')
 print(json.dumps({'passed':True,'synthetic_only':True,'real_campaign_files_read':False,'controls':['strict five samples','raw/stdout exact identity','5% interpretation boundaries']},indent=2))
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--self-test',action='store_true');p.add_argument('--timing-complete',action='store_true');p.add_argument('--package',type=pathlib.Path);p.add_argument('--short',type=pathlib.Path);p.add_argument('--larger',type=pathlib.Path);p.add_argument('--rss',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
 if a.self_test:self_test();return
 require(a.timing_complete,'Do not run until ALL timing is complete');require(all([a.package,a.short,a.larger,a.rss,a.output]),'All paths required')
 for run in [a.short,a.larger,a.rss]:require((run/'complete.json').exists() and load(run/'complete.json')['completed'] is True,'All campaigns must be complete before reading any outcome')
 require(not a.output.exists(),'Fresh audit output directory required');a.output.mkdir(parents=True)
 require(sha(a.package/'campaign-freeze.json')==FREEZE,'Expected accepted package')
 for n,h in load(a.package/'campaign-freeze.json')['files'].items():require(sha(a.package/n)==h,'Package source changed '+n)
 identity=load(a.package/'identity.json')
 for path,h in identity['artifacts'].items():require(sha(path)==h,'Immutable build artifact changed '+path)
 for label,b in identity['binaries'].items():require(sha(b['path'])==b['sha256'],'Immutable binary changed '+label)
 report={'scope':'candidate005 fixed1032/larger15/RSS528; shared host; all prior evidence retained','audit_script_sha256':sha(__file__),'package_freeze_sha256':FREEZE,'runs':{}}
 prior_receipt=pathlib.Path(__file__).parent/'006-short1032-interruption-policy.json'
 if prior_receipt.exists():
  prior=load(prior_receipt)
  for name,h in prior['preservation_hashes'].items():require(sha(pathlib.Path(prior['interrupted_run'])/name)==h,'Prior incomplete attempt modified '+name)
  report['retained_environment_interruption']={'receipt_sha256':sha(prior_receipt),'completed_processes':prior['completed_processes'],'completed_rounds':prior['completed_rounds'],'hashes_unchanged':True,'not_pooled_or_analysed':True}
 for kind,run in [('short',a.short),('larger',a.larger),('rss',a.rss)]:
  hashes=freeze_check(kind,run,a.package);raw=lines(run/'raw.jsonl');events=lines(run/'events.jsonl');plan=load(run/'frozen_schedule.json')
  result={'hashes':hashes,**counts_and_events(kind,run,plan,raw,events),'conditions':conditions_review(run)}
  if kind in ['short','rss']:result['replay']=replay(kind,run,a.output)
  summary=load(run/'summary.json')
  if kind=='short':
   meta=load(run/'bootstrap-metadata.json');require(meta['rounds']==1032 and meta['rounds_per_permutation_stratum']==172 and meta['resamples']==50000 and meta['seed']==20261022 and meta['family_size_combined']==48,'Short inference family/counts')
  if kind=='rss':
   meta=summary['bootstrap_metadata'];require(meta['resamples']==50000 and meta['seed']==20261022 and meta['family_size']==4 and meta['bonferroni_95_quantiles']==[.00625,.99375],'RSS inference family/counts')
  result['results']=(short_metrics if kind=='short' else larger_metrics if kind=='larger' else rss_metrics)(raw,summary)
  report['runs'][kind]=result;write(a.output/'audit.json',report)
 print(json.dumps({'audit':str(a.output/'audit.json'),'short_counts':report['runs']['short']['results']['counts'],'larger_above_gate':len(report['runs']['larger']['results']['pooled_above_1_05']),'rss_within_finite_criterion':report['runs']['rss']['results']['candidate_within_finite_criterion_vs_both_baselines']},indent=2))
if __name__=='__main__':main()
