#!/usr/bin/env python3
"""Compact all-outcome report; no benchmark execution or acceptance substitution."""
from pathlib import Path
import collections,hashlib,json,statistics
p=Path(__file__).resolve().parent
names=['direct-short16','pinned-short128','pinned-deep16']; combined={}; total=0; power=[]; median_checks=0; pair_checks=0
for name in names:
 q=p/'results'/name; summary=json.loads((q/'summary.json').read_text()); complete=json.loads((q/'complete.json').read_text()); rows=[json.loads(x) for x in (q/'raw.jsonl').read_text().splitlines()]
 assert complete['completed'] and complete['processes']==len(rows)==(1536 if name=='pinned-short128' else 192)
 total+=len(rows)
 conditions=[json.loads(x) for x in (q/'conditions.jsonl').read_text().splitlines()]+[json.loads((q/'environment.json').read_text())['conditions'],complete['end_conditions']]
 power+=conditions
 lookup={(r['case_id'],r['producer'],r['block']):r for r in rows}; assert len(lookup)==len(rows)
 for c in summary:
  for op,d in c['operations'].items():
   med={producer:statistics.median(v for row in rows if row['case_id']==c['case']['id'] and row['producer']==producer for v in row[op+'_seconds']) for producer in ['reference','candidate']}
   assert med==d['pooled_median_seconds'] and med['candidate']/med['reference']==d['pooled_ratio'];median_checks+=2
   for pair in d['pairs']:
    block=pair['block']; reference=statistics.median(lookup[c['case']['id'],'reference',block][op+'_seconds']); candidate=statistics.median(lookup[c['case']['id'],'candidate',block][op+'_seconds'])
    assert reference==pair['reference_median_seconds'] and candidate==pair['candidate_median_seconds'] and candidate/reference==pair['ratio'];pair_checks+=1
 combined[name]=summary
assert total==1920 and median_checks==144 and pair_checks==3840
assert all("Now drawing from 'AC Power'" in c['power']['output'] for c in power)
assert all('No thermal warning level has been recorded' in c['thermal']['output'] and 'No performance warning level has been recorded' in c['thermal']['output'] for c in power)
commands=json.loads((p/'commands.json').read_text());assert len(commands)==3 and all(c['exit_code']==0 for c in commands)
verification=json.loads((p/'results/pinned-short128/verification.json').read_text());assert verification['passed']
classification=collections.Counter(d['interpretation'] for c in combined['pinned-short128'] for d in c['operations'].values())
result=dict(candidate_status='Unpromoted; explicit coordinator review required',ratio_direction='new admission candidate / specified reference',comparisons=combined,processes=total,condition_observations=len(power),all_ac=True,no_recorded_warnings=True,raw_pooled_medians_recomputed=median_checks,paired_metric_ratios_recomputed=pair_checks,primary128_classification=dict(classification),primary128_verification=verification,plan_sha256=hashlib.sha256((p/'plan.json').read_bytes()).hexdigest())
(p/'combined-summary.json').write_text(json.dumps(result,indent=2)+'\n')
lines=['# Distinct owned-admission candidate measurements','',f"All three predeclared campaigns completed once: {total} processes; {len(power)} AC observations with no recorded thermal/performance warnings. Source, patch, original Consumer and binary identities passed before and after each campaign. No promotion, count extension, excluded outcomes or automatic waiver.",'', 'Ratios are new admission candidate / reference. The direct short comparison uses the previous three-change candidate; both other comparisons use the pinned predecessor. E=encode,D=decode,P=prepare,PE=prepare plus encode.','', '| Comparison | Case | E | D | P | PE |','|---|---|---:|---:|---:|---:|']
for name,cases in combined.items():
 for c in cases:lines.append('| '+name+' | '+c['case']['id']+' | '+' | '.join(f"{d['pooled_ratio']:.5f}" for d in c['operations'].values())+' |')
lines += ['',f"The unchanged128-round familywise rule yields {classification['within_measured_gate']} within the measured gate, {classification['unresolved']} unresolved and {classification['confirmed_regression']} confirmed regressions.",'', '| Case | Operation | Pooled ratio | Familywise interval | Classification |','|---|---|---:|---|---|']
for c in combined['pinned-short128']:
 for op,d in c['operations'].items():
  ci=d['familywise_bonferroni_95'];lines.append(f"| {c['case']['id']} | {op} | {d['pooled_ratio']:.5f} | {ci[0]:.5f}–{ci[1]:.5f} | {d['interpretation']} |")
lines += ['', 'The primary short analysis is byte-identical to the prior frozen method: original pooled-median estimand, seed20261021,50,000 joint whole-paired-round bootstrap resamples,64/64 producer-first strata,24-metric family and Bonferroni tail quantiles1/960 and959/960. The prior dataset is separate and was neither extended nor replaced.','', 'All144 pooled medians and3,840 paired metric ratios were independently recomputed from raw JSON. The primary128 verification also checked408 scalar bootstrap ratios and the full draw digest/stratum balance. All marginal intervals, block/order/temporal spread and raw outcomes remain in `combined-summary.json` and `results/`.','', 'Direct16 and deep16 evidence are distinct contexts and do not replace unresolved primary short metrics. Nominal bootstrap coverage assumes exchangeable independent rounds within strata; temporal correlation within a single host/session and finite bootstrap approximation remain limitations.']
(p/'conclusions.md').write_text('\n'.join(lines)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['comparisons','primary128_verification']},indent=2))
for name,cases in combined.items():
 print(name)
 for c in cases:print(c['case']['id'],{op:round(d['pooled_ratio'],5) for op,d in c['operations'].items()})
