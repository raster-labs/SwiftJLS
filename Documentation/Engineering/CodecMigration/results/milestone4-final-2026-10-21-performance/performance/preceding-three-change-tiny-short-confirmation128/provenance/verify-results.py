#!/usr/bin/env python3
"""Independent raw-statistic and cluster-draw verification; no benchmark execution."""
from pathlib import Path
import hashlib, importlib.util, json, math, statistics
import numpy as np
p=Path(__file__).resolve().parent; q=p/'results'; h=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
plan=json.loads((p/'plan.json').read_text()); schedule=json.loads((p/'schedules/short-pinned.json').read_text())
assert h(p/'run.py')==plan['runner_sha256'] and h(p/'analyse.py')==plan['analysis_sha256'] and h(p/'schedules/short-pinned.json')==plan['schedule_sha256']
rows=[json.loads(x) for x in (q/'raw.jsonl').read_text().splitlines()]; assert len(rows)==1536
lookup={(r['case_id'],r['producer'],r['block']):r for r in rows}; assert len(lookup)==1536
ops=['encode','decode','prepare','prepare_encode']; producers=['reference','candidate']
data=np.array([[[[lookup[c['id'],producer,b][op+'_seconds'] for b in range(128)] for producer in producers] for op in ops] for c in schedule['cases']])
assert data.shape==(6,4,2,128,5)
spec=importlib.util.spec_from_file_location('analysis',p/'analyse.py'); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
indices=module.draws(); metadata=json.loads((q/'bootstrap-metadata.json').read_text())
assert hashlib.sha256(indices.tobytes()).hexdigest()==metadata['resample_indices_sha256']
assert np.all((indices%2==0).sum(axis=1)==64)
# Select a declared spread of draw indices, not observations based on outcomes.
selected=[0,1,2,3,4,100,999,1000,4999,9999,19999,24999,29999,39999,44999,49998,49999]
actual=module.ratios(data,indices[selected]); checked=0
for pos,b in enumerate(selected):
 for c,case in enumerate(schedule['cases']):
  for o,op in enumerate(ops):
   med=[statistics.median(v for r in indices[b] for v in lookup[case['id'],producer,int(r)][op+'_seconds']) for producer in producers]
   assert math.isclose(actual[pos,c,o],med[1]/med[0],rel_tol=1e-14); checked+=1
summary=json.loads((q/'summary.json').read_text())
for c in summary:
 for op,d in c['operations'].items():
  med={producer:statistics.median(v for row in rows if row['case_id']==c['case']['id'] and row['producer']==producer for v in row[op+'_seconds']) for producer in producers}
  assert med==d['pooled_median_seconds'] and med['candidate']/med['reference']==d['pooled_ratio']
  assert d['interpretation']==module.disposition(d['familywise_bonferroni_95'])
  for b,pair in enumerate(d['pairs']):
   rm=statistics.median(lookup[c['case']['id'],'reference',b][op+'_seconds']); cm=statistics.median(lookup[c['case']['id'],'candidate',b][op+'_seconds'])
   assert rm==pair['reference_median_seconds'] and cm==pair['candidate_median_seconds'] and cm/rm==pair['ratio']
conditions=[json.loads(x) for x in (q/'conditions.jsonl').read_text().splitlines()]+[json.loads((q/'environment.json').read_text())['conditions'],json.loads((q/'complete.json').read_text())['end_conditions']]
assert all("Now drawing from 'AC Power'" in x['power']['output'] for x in conditions)
assert all('No thermal warning level has been recorded' in x['thermal']['output'] and 'No performance warning level has been recorded' in x['thermal']['output'] for x in conditions)
proof=dict(passed=True,plan_sha256=h(p/'plan.json'),raw_sha256=h(q/'raw.jsonl'),summary_sha256=h(q/'summary.json'),processes=1536,all48_raw_pooled_medians_recomputed=True,all3072_paired_metric_ratios_recomputed=True,bootstrap_ratios_independently_recomputed=checked,selected_resample_indices=selected,all50000_draws_have64_64_balance=True,full_resample_index_digest_matches=True,condition_observations=len(conditions),all_ac=True,no_recorded_warnings=True,measurement_reruns=0)
(q/'verification.json').write_text(json.dumps(proof,indent=2)+'\n'); print(json.dumps(proof,indent=2))
