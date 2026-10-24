#!/usr/bin/env python3
from pathlib import Path
import collections,contextlib,datetime,gzip,hashlib,importlib.util,io,json,sys,time
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent; F=R/'workspace89-corrected-002'; P=F/'profiles'
BASE=Path('/Users/pushparaj/projects/SwiftJLS/Documentation/Engineering/CodecMigration/results/factory-qualification-2026-10-22/workspace')
OLD=BASE/'workspace89-linux-005-replay-043/profiles'
rd=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
m=load('classifier',R/'external-classifier/measure-operation.py');orig=load('oldclassifier',R/'external-classifier/measure-operation-original.py');runner=load('runner',R/'external-classifier/run-workspace-profiles.py')
plan=rd(R/'plan.json');receipt=rd(R/'corrected-receipt.json');started=time.monotonic()
assert receipt['exit_code']==0 and rd(R/'copy-receipt.json')['exit_code']==0
assert sha(R/'workspace89/WorkspaceProbe')==receipt['workspace_binary_sha256']
assert sha(R/'external-classifier/measure-operation.py')==receipt['corrected_classifier_sha256']
assert rd(R/'corrected-inputs-before.json')['files']==rd(R/'corrected-inputs-after.json')['files']
assert sha(Path(plan['source_receipt']))==receipt['source_receipt_sha256']
control_output=io.StringIO()
with contextlib.redirect_stdout(control_output):m.self_test();runner.self_test()
cases=rd(P/'matrix.json')['cases'];assert len(cases)==89
assert cases==rd(BASE/'workspace89-linux-005/profiles/matrix.json')['cases']==rd(OLD/'matrix.json')['cases']
assert sorted(n for n,a in cases)==sorted(p.name for p in P.iterdir() if p.is_dir())
revision='candidate_004:receipt:'+plan['source_receipt_sha256'];assert rd(P/'matrix.json')['revision']==revision
counts=collections.Counter();requested=collections.Counter();oldcounts=collections.Counter();oldrequested=collections.Counter();ops=collections.Counter();reclass=collections.Counter();rows=[];commands_count=0;peak=None;changed=[];raw_bytes=0
for name,args in cases:
 d=P/name;report=rd(d/'operation.json');summary=rd(d/'summary.json');commands=rd(d/'commands.json');raw=d/'allocations.gz';rh=sha(raw)
 assert summary['profile_sha256']==report['profile_sha256']==rh;assert summary['binary_sha256']==receipt['workspace_binary_sha256'];assert summary['commands']==commands
 assert len(commands)==3 and all(x['exit_code']==0 for x in commands);commands_count+=len(commands)
 assert commands[1]['command'][3]=='/original/WorkspaceProbe' and commands[1]['command'][4:]==args
 lines=gzip.open(raw,'rt').readlines();fresh=m.replay(lines);assert fresh=={k:v for k,v in report.items() if k not in ['revision','profile_sha256']},name
 old_classified=orig.replay(lines)
 runner.verify_operation_report(name,args[0],report,revision,raw)
 assert report['pure_algorithm_workspace_complete'] is False and report['stack_peak_bytes'] is None and report['allocator_overhead_bytes'] is None
 assert report['codec_heap_attribution_complete'] is True
 for k in ['phase_total_requested_heap_peak_bytes','baseline_total_requested_heap_bytes','phase_total_peak_above_baseline_bytes','process_requested_heap_peak_bytes']:
  assert old_classified[k]==report[k]
 for k in ['phase_allocation_calls','phase_allocated_bytes','baseline_live_bytes','end_live_bytes']:
  assert sum(g[k] for g in old_classified['groups'].values())==sum(g[k] for g in report['groups'].values())
 transfer=[]
 for index,s in report['allocation_stacks'].items():
  before=old_classified['allocation_stacks'][index]
  if before['category']!=s['category']:
   assert before['category']=='storage_control_objects' and s['category']=='owned_pixel_buffer'
   assert s['allocation_calls']==1 and len(s['requested_size_counts'])==1
   transfer.append({'stack_index':index,'bytes':s['allocated_bytes'],'frames':s['frames'][:7]});reclass['phase_calls']+=s['allocation_calls'];reclass['phase_bytes']+=s['allocated_bytes']
 consumer=[json.loads(x) for x in (d/'consumer.stdout').read_text().splitlines() if x.startswith('{')]
 assert len(consumer)==1 and consumer[0]['samples_verified'] is True and consumer[0]['operation']==args[0]
 historical=rd(OLD/name/'operation.json');old_consumer=[json.loads(x) for x in (BASE/'workspace89-linux-005/profiles'/name/'consumer.stdout').read_text().splitlines() if x.startswith('{')]
 assert consumer==old_consumer,('fixture/sample profile mismatch',name)
 ops[args[0]]+=1
 groups={}
 for g in report['groups'].keys()|historical['groups'].keys():
  new=report['groups'].get(g,{});old=historical['groups'].get(g,{})
  counts[g]+=new.get('phase_allocation_calls',0);requested[g]+=new.get('phase_allocated_bytes',0)
  oldcounts[g]+=old.get('phase_allocation_calls',0);oldrequested[g]+=old.get('phase_allocated_bytes',0)
  delta={k:new.get(k,0)-old.get(k,0) for k in set(new)|set(old)}
  if any(delta.values()):groups[g]=delta
 if groups:changed.append(name)
 row={'case':name,'args':args,'profile_sha256':rh,'profile_bytes':raw.stat().st_size,'operation_sha256':sha(d/'operation.json'),'trace_summary_sha256':sha(d/'summary.json'),'commands_sha256':sha(d/'commands.json'),'consumer_stdout_sha256':sha(d/'consumer.stdout'),'phase_peak_bytes':report['phase_total_requested_heap_peak_bytes'],'baseline_requested_heap_bytes':report['baseline_total_requested_heap_bytes'],'peak_delta_bytes':report['phase_total_peak_above_baseline_bytes'],'algorithm_peak_delta_bytes':report['groups'].get('algorithm_state',{}).get('peak_above_baseline_bytes',0),'phase_calls':sum(g['phase_allocation_calls'] for g in report['groups'].values()),'owned_pixel_phase_calls':report['groups'].get('owned_pixel_buffer',{}).get('phase_allocation_calls',0),'comparison_to_factory002':{'baseline_report_sha256':sha(OLD/name/'operation.json'),'group_deltas':groups,'phase_peak_delta':report['phase_total_requested_heap_peak_bytes']-historical['phase_total_requested_heap_peak_bytes'],'total_phase_calls_delta':sum(g['phase_allocation_calls'] for g in report['groups'].values())-sum(g['phase_allocation_calls'] for g in historical['groups'].values())},'same_raw_classifier_transfers':transfer}
 rows.append(row);raw_bytes+=row['profile_bytes']
 if peak is None or row['phase_peak_bytes']>peak['phase_peak_bytes']:peak={k:row[k] for k in ['case','phase_peak_bytes','baseline_requested_heap_bytes','peak_delta_bytes']}
assert commands_count==267 and ops==dict(encode=20,owned=23,into=23,inspect=23)
assert counts['owned_pixel_buffer']==23 and counts['unattributed_codec']==0
assert sha(R/'workspace89/WorkspaceProbe')==receipt['workspace_binary_sha256']
assert sha(R/'external-classifier/measure-operation.py')==receipt['corrected_classifier_sha256']
for key in ['files']:
 assert rd(R/'corrected-inputs-before.json')[key]==rd(R/'corrected-inputs-after.json')[key]
result={'status':'accepted_scoped_evidence','utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reconcile_seconds':time.monotonic()-started,'source_receipt_sha256':receipt['source_receipt_sha256'],'input_manifest_sha256':sha(R/'corrected-inputs-before.json'),'workspace_binary_sha256':receipt['workspace_binary_sha256'],'classifier_sha256':receipt['corrected_classifier_sha256'],'original_classifier_sha256':sha(R/'external-classifier/measure-operation-original.py'),'classifier_patch_sha256':sha(R/'external-classifier/classifier.patch'),'collection_receipt_sha256':sha(R/'corrected-receipt.json'),'reconcile_script_sha256':sha(Path(__file__)),'profiles':89,'commands':commands_count,'ops':dict(ops),'raw_profiles_bytes':raw_bytes,'same_raw_independent_replays':178,'all_samples_verified':True,'fixture_profile_reports_equal_to_factory002':True,'all_codec_attributed':True,'owned_pixel_calls':23,'other66_pixel_calls':0,'phase_calls_total':sum(counts.values()),'phase_calls_by_category':dict(counts),'phase_requested_bytes_by_category':dict(requested),'baseline_factory002_phase_calls_total':sum(oldcounts.values()),'baseline_factory002_phase_calls_by_category':dict(oldcounts),'baseline_factory002_phase_requested_bytes_by_category':dict(oldrequested),'phase_call_deltas_by_category':dict(counts-oldcounts) if False else {g:counts[g]-oldcounts[g] for g in counts.keys()|oldcounts.keys()},'phase_requested_byte_deltas_by_category':{g:requested[g]-oldrequested[g] for g in requested.keys()|oldrequested.keys()},'largest_phase_heap_peak':peak,'same_raw_classifier_transfers':dict(reclass),'changed_profiles_vs_factory002':changed,'controls_output':control_output.getvalue(),'copy_probe':rd(R/'copy-reconciliation.json'),'universal_total_unknown':True,'limitations':['Requested heap bytes omit allocator usable-size overhead, stack, VM mappings and RSS.','One marked operation per process across the fixed 89 profiles; no universal all-input or concurrent total.','Category peaks occur at different instants and must not be summed.','Runtime/unattributed remains explicit; production peakWorkspaceBytes remains nil.','CopyProbe intercepts ordinary memcpy/memmove reads; it cannot observe inlined copies.','Apple RSS, physical-device and deferred milestone5 gates are not changed.'],'rows':rows}
(R/'reconciliation-summary.json').write_text(json.dumps(result,indent=2,sort_keys=True)+'\n')
print(json.dumps({k:v for k,v in result.items() if k not in ['rows','changed_profiles_vs_factory002']},indent=2))
