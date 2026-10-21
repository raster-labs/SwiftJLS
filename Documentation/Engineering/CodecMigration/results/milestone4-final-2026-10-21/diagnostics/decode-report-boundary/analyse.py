#!/usr/bin/env python3
import importlib.util,json,pathlib,statistics,sys
HERE=pathlib.Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('common',HERE.parent/'tiny-confirmatory/run.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
out=HERE/(sys.argv[1] if len(sys.argv)>1 else 'results-3')
complete=json.loads((out/'complete.json').read_text());assert complete['completed'] and complete['decode_processes']==128 and complete['micro_processes']==96
rows=[json.loads(line) for line in (out/'decode-raw.jsonl').read_text().splitlines()]
micro=[json.loads(line) for line in (out/complete.get('micro_raw','micro-raw.jsonl')).read_text().splitlines()]
def describe(values,seed):
 assert len(values)==16
 return dict(median=statistics.median(values),minimum=min(values),maximum=max(values),values=values,intervals=common.intervals(values,seed))
stages=[];comparisons=[];controls=[];micro_results=[]
for mode_index,mode in enumerate(['short','long']):
 for bits in [12,16]:
  selected=sorted([r for r in rows if r['entry']['mode']==mode and r['bits']==bits and r['control']=='report'],key=lambda r:r['entry']['block'])
  categories={
   'outer':[r['decode_seconds'] for r in selected],
   'reported':[r['reported_decode_seconds'] for r in selected],
   'outer_minus_reported':[[a-b for a,b in zip(r['decode_seconds'],r['reported_decode_seconds'])] for r in selected]
  }
  values={name:dict(pooled_median_seconds=statistics.median(v for row in arrays for v in row),blocks=describe([statistics.median(row) for row in arrays],20261022+mode_index*100+bits*10+i)) for i,(name,arrays) in enumerate(categories.items())}
  stages.append(dict(mode=mode,bits=bits,stages=values,observations_per_process=selected[0]['iterations'],negative_residual_observations=sum(v<0 for row in categories['outer_minus_reported'] for v in row)))
  for op in ['encode','decode','prepare','prepare_encode']:
   ratios=[]
   for block in range(16):
    pair={r['control']:r for r in rows if r['entry']['mode']==mode and r['bits']==bits and r['entry']['block']==block}
    ratios.append(statistics.median(pair['report'][op+'_seconds'])/statistics.median(pair['zero'][op+'_seconds']))
   controls.append(dict(mode=mode,bits=bits,operation=op,report_over_zero=describe(ratios,20262000+mode_index*100+bits)))
for bits in [12,16]:
 s={r['mode']:r for r in stages if r['bits']==bits}
 for stage in ['outer','reported','outer_minus_reported']:
  a=s['short']['stages'][stage]['blocks']['values'];b=s['long']['stages'][stage]['blocks']['values']
  comparisons.append(dict(bits=bits,stage=stage,short_minus_long_seconds=describe([x-y for x,y in zip(a,b)],20263000+bits),short_over_long=describe([x/y for x,y in zip(a,b)],20264000+bits)))
for mode_index,mode in enumerate(['short','long']):
 for ci,constructor in enumerate(['uuid','reference','random']):
  selected=sorted([r for r in micro if r['entry']['mode']==mode and r['mode']==constructor],key=lambda r:r['entry']['block'])
  med=[statistics.median(r['seconds']) for r in selected]
  micro_results.append(dict(mode=mode,constructor=constructor,pooled_median_seconds=statistics.median(v for r in selected for v in r['seconds']),blocks=describe(med,20265000+mode_index*10+ci)))
conditions=[json.loads(l) for l in (out/'conditions.jsonl').read_text().splitlines()]
if (out/'resume-conditions.jsonl').exists():conditions += [json.loads(l) for l in (out/'resume-conditions.jsonl').read_text().splitlines()]
conditions+=[json.loads((out/'environment.json').read_text())['conditions'],complete['conditions']]
result=dict(source='bee49a2ad47eae4ea149bdced2043b7a45df3dae',performance_qualified=False,stages=stages,short_long_comparisons=comparisons,report_zero_controls=controls,micro=micro_results,conditions=dict(snapshots=len(conditions),all_ac=all("Now drawing from 'AC Power'" in c['power']['output'] for c in conditions),no_recorded_warnings=all('No thermal warning level has been recorded' in c['thermal']['output'] and 'No performance warning level has been recorded' in c['thermal']['output'] for c in conditions)),limitations='Report/zero use same timed code and different post-timer output masking. Changed Double-return ABI is diagnostic; outer-report includes checks/destruction and is not pure executor cost. Intervals assume independent/exchangeable blocks; same-host correlation and multiple metrics limit inference. Micro includes consumption/destruction, call and timer costs; reference forbidden by contract; random unavailable at26.0 floor.')
common.write(out/'analysis.json',result)
lines=['# Decode boundary diagnostic results','','All128 decode and96 micro processes completed; all observations retained. The micro validator initially rejected legitimate clock-resolution zeros; its completed fifth process was recovered unchanged and only91 unstarted entries continued. No reruns or epsilon replacement. No production code changed. No automatic acceptance.','','| Mode | Bits | Outer pooled µs | Reported pooled µs | Residual pooled µs |','| --- | ---: | ---: | ---: | ---: |']
for r in stages:
 vals=r['stages'];lines.append(f"| {r['mode']} | {r['bits']} | {vals['outer']['pooled_median_seconds']*1e6:.4f} | {vals['reported']['pooled_median_seconds']*1e6:.4f} | {vals['outer_minus_reported']['pooled_median_seconds']*1e6:.4f} |")
lines+=['','Paired block short-minus-long differences:','','| Bits | Interval | Median difference µs | Bootstrap95% µs | Exact conservative interval µs |','| ---: | --- | ---: | --- | --- |']
for r in comparisons:
 d=r['short_minus_long_seconds'];ci=d['intervals'];fmt=lambda v:', '.join(f'{x*1e6:.4f}' for x in v)
 lines.append(f"| {r['bits']} | {r['stage']} | {d['median']*1e6:.4f} | {fmt(ci['percentile_bootstrap_95'])} | {fmt(ci['exact_conservative_nominal_95'])} |")
lines+=['','| Mode | Micro constructor | Pooled ns | Block median ns | Bootstrap95% ns |','| --- | --- | ---: | ---: | --- |']
for r in micro_results:
 d=r['blocks'];lines.append(f"| {r['mode']} | {r['constructor']} | {r['pooled_median_seconds']*1e9:.1f} | {d['median']*1e9:.1f} | {', '.join(f'{x*1e9:.1f}' for x in d['intervals']['percentile_bootstrap_95'])} |")
lines+=['','Report/zero operation controls (same timed path):','','| Mode | Bits | Operation | Median report/zero block ratio | Bootstrap95% |','| --- | ---: | --- | ---: | --- |']
for r in controls:
 d=r['report_over_zero'];lines.append(f"| {r['mode']} | {r['bits']} | {r['operation']} | {d['median']:.5f} | {', '.join(f'{x:.5f}' for x in d['intervals']['percentile_bootstrap_95'])} |")
lines+=['',result['limitations'],'',f"Captured conditions: {result['conditions']}",'','All block values, interval/spread details and same-invocation residuals are retained in `analysis.json`; raw files retain every observation and command. Bootstrap95% intervals and conservative exact97.8729% intervals use16 process blocks, not individual iterations. No cause or waiver follows automatically.','']
(HERE/'RESULTS.md').write_text('\n'.join(lines))
for r in stages:print(r['mode'],r['bits'],{k:round(v['pooled_median_seconds']*1e6,4) for k,v in r['stages'].items()})
for r in comparisons:print('short-long',r['bits'],r['stage'],r['short_minus_long_seconds']['median']*1e6,r['short_minus_long_seconds']['intervals']['percentile_bootstrap_95'])
for r in micro_results:print('micro',r['mode'],r['constructor'],r['pooled_median_seconds']*1e9)
print(result['conditions'])
