#!/usr/bin/env python3
"""Verify every original larger-guard observation and report descriptive outcomes."""
from pathlib import Path
import collections,hashlib,json,statistics
p=Path(__file__).resolve().parent; q=p/'larger-guards'; sha=lambda f:hashlib.sha256(f.read_bytes()).hexdigest()
plan=json.loads((p/'larger-guard-plan.json').read_text());schedule=json.loads((p/'larger-guard-schedule.json').read_text());readiness=json.loads((p/'larger-guard-readiness.json').read_text())
assert sha(p/'larger-guard-plan.json')==readiness['larger_guard_plan_sha256']==schedule['larger_guard_plan_sha256']
assert sha(p/'larger-guard-schedule.json')==readiness['schedule_sha256'] and sha(p/'run-larger-guards.py')==readiness['runner_sha256']
rows=[json.loads(x) for x in (q/'raw.jsonl').read_text().splitlines()];complete=json.loads((q/'complete.json').read_text());summary=json.loads((q/'summary.json').read_text());env=json.loads((q/'environment.json').read_text())
assert len(rows)==complete['processes']==120 and complete['completed'] and len(summary)==15
assert env['larger_guard_plan_sha256']==complete['larger_guard_plan_sha256']==readiness['larger_guard_plan_sha256']
lookup={(r['case_id'],r['producer'],r['block']):r for r in rows};assert len(lookup)==120
results=[];pooled_checks=0;pair_checks=0;outliers=[];size_outliers=[];rss_outliers=[]
for c in summary:
 case=c['case'];selected=[r for r in rows if r['case_id']==case['id']];assert len(selected)==8
 for op,d in c['operations'].items():
  med={producer:statistics.median(v for r in selected if r['producer']==producer for v in r[op+'_seconds']) for producer in ['reference','candidate']}
  assert med==d['pooled_median_seconds'] and med['candidate']/med['reference']==d['pooled_ratio'];pooled_checks+=2
  for pair in d['pairs']:
   rm=statistics.median(lookup[case['id'],'reference',pair['block']][op+'_seconds']);cm=statistics.median(lookup[case['id'],'candidate',pair['block']][op+'_seconds'])
   assert rm==pair['reference_median_seconds'] and cm==pair['candidate_median_seconds'] and cm/rm==pair['ratio'];pair_checks+=1
  if d['pooled_ratio']>1.05:outliers.append(dict(case=case['id'],operation=op,pooled_ratio=d['pooled_ratio'],pair_ratios=[x['ratio'] for x in d['pairs']],order=d['median_ratio_by_first_producer']))
 encoded={producer:{r['encoded_bytes'] for r in selected if r['producer']==producer} for producer in ['reference','candidate']};assert all(len(v)==1 for v in encoded.values());encoded={k:next(iter(v)) for k,v in encoded.items()}
 rss={producer:statistics.median(r['peak_process_rss_bytes'] for r in selected if r['producer']==producer) for producer in ['reference','candidate']}
 item=dict(case=case,operations=c['operations'],encoded_bytes=encoded,encoded_byte_delta=encoded['candidate']-encoded['reference'],encoded_ratio=encoded['candidate']/encoded['reference'],median_peak_process_rss_bytes=rss,rss_ratio=rss['candidate']/rss['reference'])
 if item['encoded_ratio']>1.01:size_outliers.append(dict(case=case['id'],ratio=item['encoded_ratio'],delta=item['encoded_byte_delta']))
 if item['rss_ratio']>1.10:rss_outliers.append(dict(case=case['id'],ratio=item['rss_ratio']))
 results.append(item)
conditions=[json.loads(x) for x in (q/'conditions.jsonl').read_text().splitlines()]+[env['conditions'],complete['end_conditions']]
assert all("Now drawing from 'AC Power'" in c['power']['output'] for c in conditions)
assert all('No thermal warning level has been recorded' in c['thermal']['output'] and 'No performance warning level has been recorded' in c['thermal']['output'] for c in conditions)
assert pooled_checks==120 and pair_checks==240
report=dict(source=complete['source_guards']['source_commit'],candidate_binary_sha256=complete['source_guards']['candidate_binary_sha256'],larger_guard_plan_sha256=readiness['larger_guard_plan_sha256'],schedule_sha256=readiness['schedule_sha256'],processes=120,paired_blocks=4,cases=15,condition_observations=len(conditions),all_ac=True,no_recorded_warnings=True,all120_pooled_medians_recomputed=True,all240_pair_ratios_recomputed=True,raw_sha256=sha(q/'raw.jsonl'),timing_outliers=outliers,size_outliers=size_outliers,rss_outliers=rss_outliers,rows=results,limitations='Four paired blocks provide descriptive spread/order evidence only. No automatic acceptance or waiver. RSS is process high water, not algorithm workspace. All final-source short uncertainty remains separate.')
(p/'larger-guard-summary.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='rows'},indent=2))
for row in results:print(row['case']['id'],{op:round(d['pooled_ratio'],5) for op,d in row['operations'].items()},'size_delta',row['encoded_byte_delta'])
