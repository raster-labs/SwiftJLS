from pathlib import Path
import sys,json,hashlib,gzip,importlib.util,collections,datetime
sys.dont_write_bytecode=True
s=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch');orig=s/'campaigns/workspace89-linux-005';new=s/'campaigns/workspace89-linux-005-replay-043';audit=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022');repo=Path('/Users/pushparaj/projects/SwiftJLS');h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();rd=lambda p:json.loads(p.read_text())
base=rd(audit/'043-workspace-results.json');complete=rd(new/'complete.json');rec=rd(new/'profiles/reconciliation-summary.json');deltas=rd(new/'category-transfer-deltas.json');cl=new/'frozen_measure_operation.py';ch=h(cl);assert ch==complete['new_classifier_sha256']==h(repo/'Scripts/StorageEvidence/measure-operation.py')=='8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452'
assert h(orig/'WorkspaceProbe')==base['binary_sha256']==rec['built_workspace_probe_binary_sha256'];assert h(orig/'outer-command-receipt.json')==base['outer_receipt_sha256'];assert h(orig/'profiles/reconciliation-summary.json')==base['aggregate_sha256'];assert h(orig/'frozen_source_manifest.json')==base['source_manifest_sha256']
for p,k in [('profiles/reconciliation-summary.json','reconciliation_summary_sha256'),('category-transfer-deltas.json','category_transfer_deltas_sha256'),('profiles/matrix.json','matrix_json_sha256')]:assert h(new/p)==complete[k]
spec=importlib.util.spec_from_file_location('audit047',cl);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.self_test();cases=rd(orig/'profiles/matrix.json')['cases'];assert rd(new/'profiles/matrix.json')['cases']==cases;assert len(cases)==89;assert len(rec['cases'])==89
changed=[];old_counts=collections.Counter();new_counts=collections.Counter();rows=[]
for name,args in cases:
 od=orig/'profiles'/name;nd=new/'profiles'/name;a=rd(od/'operation.json');b=rd(nd/'operation.json');row=next(x for x in rec['cases'] if x['case']==name);prior=next(x for x in base['cases'] if x['case']==name)
 assert h(od/'allocations.gz')==a['profile_sha256']==b['profile_sha256']==row['profile_sha256']==prior['profile_sha256'];assert h(od/'operation.json')==prior['operation_sha256']==row['orig_operation_json_sha256'];assert h(nd/'operation.json')==row['replayed_operation_json_sha256'];assert h(od/'commands.json')==row['orig_commands_json_sha256'];assert h(od/'summary.json')==row['orig_trace_summary_json_sha256'];assert row['binary_sha256']==base['binary_sha256'];assert row['args']==args
 fresh=m.replay(gzip.open(od/'allocations.gz','rt').readlines());assert fresh=={k:v for k,v in b.items() if k not in ['revision','profile_sha256']},name
 assert b['codec_heap_attribution_complete'] and not b['pure_algorithm_workspace_complete'];assert b['stack_peak_bytes'] is None and b['allocator_overhead_bytes'] is None
 for key in ['phase_total_requested_heap_peak_bytes','baseline_total_requested_heap_bytes','phase_total_peak_above_baseline_bytes','process_requested_heap_peak_bytes']:assert a[key]==b[key]
 for key in ['phase_allocation_calls','phase_allocated_bytes','baseline_live_bytes','end_live_bytes']:assert sum(x[key] for x in a['groups'].values())==sum(x[key] for x in b['groups'].values())
 for k,v in a['groups'].items():old_counts[k]+=v['phase_allocation_calls']
 for k,v in b['groups'].items():new_counts[k]+=v['phase_allocation_calls']
 transfer=[]
 for idx,v in a['allocation_stacks'].items():
  w=b['allocation_stacks'][idx];aa=dict(v);bb=dict(w);aa.pop('category');bb.pop('category');assert aa==bb
  if v['category']!=w['category']:assert v['category']=='compressed_buffer' and w['category']=='algorithm_state' and v['allocation_calls']==1 and v['requested_size_counts']=={'64':1};transfer.append(idx)
 same={k:v for k,v in a.items() if k not in ['revision','groups','simultaneous_categories_at_phase_peak_bytes','allocation_stacks']};assert same=={k:v for k,v in b.items() if k not in ['revision','groups','simultaneous_categories_at_phase_peak_bytes','allocation_stacks']}
 if transfer:
  assert len(transfer)==1;changed.append(name)
  for group in a['groups']:
   if group not in ['algorithm_state','compressed_buffer']:assert a['groups'][group]==b['groups'][group]
  for group,sign in [('algorithm_state',1),('compressed_buffer',-1)]:
   aa=a['groups'][group];bb=b['groups'][group];assert bb['phase_allocation_calls']-aa['phase_allocation_calls']==sign;assert bb['phase_allocated_bytes']-aa['phase_allocated_bytes']==sign*64;assert bb['baseline_live_bytes']==aa['baseline_live_bytes'];assert bb['end_live_bytes']==aa['end_live_bytes'];assert bb['peak_live_bytes']-aa['peak_live_bytes']==sign*64;assert bb['peak_above_baseline_bytes']-aa['peak_above_baseline_bytes']==sign*64
  for group in a['simultaneous_categories_at_phase_peak_bytes']:assert b['simultaneous_categories_at_phase_peak_bytes'][group]-a['simultaneous_categories_at_phase_peak_bytes'][group]==(64 if group=='algorithm_state' else -64 if group=='compressed_buffer' else 0)
 else:assert {k:v for k,v in a.items() if k!='revision'}=={k:v for k,v in b.items() if k!='revision'}
 rows.append({'case':name,'replayed_report_sha256':h(nd/'operation.json'),'transferred_calls':len(transfer)})
expected={'17-1-0-owned','17-1-3-owned','512-1-0-owned','512-1-3-owned','p16-1-0-owned','preset-1-3-owned','extended-p12-65537x2-owned'};assert set(changed)==expected;assert len(changed)==7;assert sum(old_counts.values())==sum(new_counts.values())==4432;assert dict(old_counts)==rec['phase_allocation_calls_by_category_old_6c'];assert dict(new_counts)==rec['phase_allocation_calls_by_category_new_80'];assert deltas['transferred_bytes']==448
assert h(cl)==ch==h(repo/'Scripts/StorageEvidence/measure-operation.py')
out={'status':'accepted','at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'cases_replayed':89,'changed_cases':changed,'unchanged_cases':82,'transferred_calls':7,'transferred_bytes':448,'phase_total_calls':4432,'old_category_counts':dict(old_counts),'corrected_category_counts':dict(new_counts),'total_peaks_unchanged':True,'source_binary_raw_original_reports_preserved':True,'classifier_sha256':ch,'replay_complete_sha256':h(new/'complete.json'),'replay_aggregate_sha256':h(new/'profiles/reconciliation-summary.json'),'delta_sha256':h(new/'category-transfer-deltas.json'),'rows':rows};(audit/'047-replay-check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='rows'},indent=2))
