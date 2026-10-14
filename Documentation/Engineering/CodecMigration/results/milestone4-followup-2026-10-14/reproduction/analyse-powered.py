import pathlib,json,statistics,collections,re
root=pathlib.Path.cwd();out=root/'work/m4-2026-10-14/powered'
keys=['width','height','bits','pattern','components','near','interleave'];operations=['encode','decode','prepare','prepare_encode'];result={}
for kind in ['scalar','colour']:
 paths=[out/kind/'raw.jsonl']
 groups=collections.defaultdict(list);excluded=[]
 for path in paths:
  if not path.exists():continue
  local=collections.defaultdict(list)
  for line in path.read_text().splitlines():
   row=json.loads(line);local[tuple(row[k] for k in keys)].append(row)
  for key,rows in local.items():
   expected={(b,l) for b in range(4) for l in ['predecessor','successor']}
   if len(rows)!=8 or {(r['block'],r['label']) for r in rows}!=expected:
    excluded.append(dict(case=list(key),source=str(path.relative_to(root)),observations=len(rows),reason='Incomplete case; deliberately interrupted grid or still running'));continue
   assert key not in groups,'Duplicate completed case'
   groups[key]=rows
 cases=[]
 for key,rows in groups.items():
  case=dict(zip(keys,key));case['producers']={}
  for label in ['predecessor','successor']:
   runs=[r for r in rows if r['label']==label];assert len({r['encoded_bytes'] for r in runs})==1
   metrics=dict(encoded_bytes=runs[0]['encoded_bytes'],process_rss_peak_bytes=max(r['peak_process_rss_bytes'] for r in runs))
   for op in operations:
    vals=sorted(v for r in runs for v in r[op+'_seconds']);assert len(vals)==20
    metrics[op]=dict(median_seconds=statistics.median(vals),p95_seconds=vals[int(.95*(len(vals)-1))],min_seconds=min(vals),max_seconds=max(vals),samples=len(vals))
   case['producers'][label]=metrics
  case['comparisons']={}
  for op in operations:
   ratios=[]
   for block in range(4):
    pair={r['label']:r for r in rows if r['block']==block}
    ratios.append(statistics.median(pair['successor'][op+'_seconds'])/statistics.median(pair['predecessor'][op+'_seconds']))
   pooled=case['producers']['successor'][op]['median_seconds']/case['producers']['predecessor'][op]['median_seconds']
   case['comparisons'][op]=dict(median_ratio=pooled,paired_block_ratios=ratios,all_blocks_over_5_percent=all(r>1.05 for r in ratios))
  case['rss_ratio']=case['producers']['successor']['process_rss_peak_bytes']/case['producers']['predecessor']['process_rss_peak_bytes']
  case['encoded_size_ratio']=case['producers']['successor']['encoded_bytes']/case['producers']['predecessor']['encoded_bytes']
  cases.append(case)
 result[kind]=dict(complete_cases=len(cases),excluded_cases=excluded,cases=cases)
print('Completed cases:',{k:v['complete_cases'] for k,v in result.items()})
for kind,section in result.items():
 for op in ['encode','decode','prepare_encode']:
  large=[c for c in section['cases'] if c['width']>=512];ratios=[c['comparisons'][op]['median_ratio'] for c in large]
  print(kind,op, 'ratios',round(min(ratios),3),round(max(ratios),3),'pooled >5%',sum(r>1.05 for r in ratios),'all four >5%',sum(c['comparisons'][op]['all_blocks_over_5_percent'] for c in large),'/',len(large))
(out/'combined-analysis.json').write_text(json.dumps(result,indent=2)+'\n')
