from pathlib import Path
import sys,hashlib,json,gzip,importlib.util,datetime,collections
sys.dont_write_bytecode=True
repo=Path('/Users/pushparaj/projects/SwiftJLS');s=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch');snap=s/'snapshots/frozen-candidate-validation-002/SwiftJLS';controls=s/'diagnostics/workspace-002-stack-control';audit=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022');tool=repo/'Scripts/StorageEvidence/measure-operation.py'
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();initial=h(tool)
spec=importlib.util.spec_from_file_location('operation038',tool);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);m.self_test()
r={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'classifier_sha256':initial,'old_classifier_sha256':h(snap/'Scripts/StorageEvidence/measure-operation.py'),'workspace_probe_sha256':h(controls/'WorkspaceProbe'),'profiles':{},'negative_controls':'repository self_test plus each of the six observed factory frames independently mutated/removed'}
for p in sorted(controls.glob('*/allocations.gz')):
 lines=gzip.open(p,'rt').readlines();fresh=m.replay(lines);old=json.loads((p.parent/'operation.json').read_text());retained=json.loads((p.parent/'operation-replayed.json').read_text());assert h(p)==old['profile_sha256']==retained['profile_sha256']
 assert all(fresh[k]==v for k,v in retained.items() if k not in ['revision','profile_sha256']),p
 assert fresh['codec_heap_attribution_complete'];assert not fresh['pure_algorithm_workspace_complete'];assert fresh['stack_peak_bytes'] is None and fresh['allocator_overhead_bytes'] is None
 assert fresh['groups']['owned_pixel_buffer']['phase_allocation_calls']==1
 for key in ['phase_total_requested_heap_peak_bytes','baseline_total_requested_heap_bytes','phase_total_peak_above_baseline_bytes','process_requested_heap_peak_bytes']:assert fresh[key]==old[key]
 for key in ['phase_allocation_calls','phase_allocated_bytes','baseline_live_bytes','end_live_bytes']:assert sum(x[key] for x in fresh['groups'].values())==sum(x[key] for x in old['groups'].values())
 assert sum(fresh['simultaneous_categories_at_phase_peak_bytes'].values())==fresh['phase_total_requested_heap_peak_bytes']
 changes=[]
 for idx,st in old['allocation_stacks'].items():
  new=fresh['allocation_stacks'][idx]
  if st['category']!=new['category']:
   assert st['category']=='unattributed_codec' and new['category']=='owned_pixel_buffer';assert st['allocation_calls']==1
   assert st['frames'][:6]==new['frames'][:6]
   for i in range(6):
    frames=st['frames'].copy();frames[i]='SwiftJLS.Other.allocate';assert m.classify(frames,610)=='unattributed_codec',(p,i)
    frames=st['frames'].copy();del frames[i];assert m.classify(frames,610)=='unattributed_codec',(p,i)
   changes.append({'trace':idx,'size_counts':st['requested_size_counts'],'frames':st['frames'][:8]})
 r['profiles'][p.parent.name]={'profile_sha256':h(p),'original_report_sha256':h(p.parent/'operation.json'),'replayed_report_sha256':h(p.parent/'operation-replayed.json'),'raw_command':next(l.strip() for l in lines if l.startswith('X ')),'phase_calls':sum(x['phase_allocation_calls'] for x in fresh['groups'].values()),'phase_peak':fresh['phase_total_requested_heap_peak_bytes'],'pixel':fresh['groups']['owned_pixel_buffer'],'changed_stacks':changes,'unknown':fresh['groups'].get('unattributed_codec',{})}
# Copy observation: verify actual retained JSON/binary and frozen/current source pin parity.
p=s/'diagnostics/frozen-candidate-linux-copy-probe-002.json';d=json.loads(p.read_text());assert d['returncode']==0;raw=Path(d['raw_stdout_path']);assert h(raw)==d['raw_stdout_sha256'];assert json.loads(raw.read_text())==d['probe_output'];assert h(Path(d['binary_path']))==d['binary_sha256'];assert d['probe_output']['self_test'] is True
for rel,sha in d['source_file_sha256'].items():assert h(snap/rel)==h(repo/rel)==sha
rows=d['probe_output']['cases'];assert len(rows)==20;groups=collections.defaultdict(list)
for x in rows:
 assert x['maximum_sample_error']<=x['near'];assert x['observed_source_copy_bytes']==(x['source_capacity'] if x['injected'] else 0);groups[x['fixture'],x['interleave']].append(x)
assert len(groups)==10 and all(sorted(x['injected'] for x in v)==[False,True] for v in groups.values())
assert '--heap-only' not in ' '.join(d['command']);assert 'target=/SwiftJLS,readonly' in ' '.join(d['command']);assert d['binary_sha256'] in d['stderr'];assert 'Swift version 6.4' in d['stderr'];assert 'aarch64' in d['stderr']
r['copy']={'receipt_sha256':h(p),'binary_sha256':d['binary_sha256'],'raw_sha256':h(raw),'rows':len(rows),'normal_zero':10,'positive_exact_capacity':10,'max_error_all_zero':all(x['maximum_sample_error']==0 for x in rows),'scope':d['probe_output']['scope'],'source_pins':d['source_file_sha256']}
# Full production pin equality; tests/fixtures verified in036, count/hash map repeated here.
for scope in ['Sources/SwiftJLS','Package.swift','VERSION','Tests/SwiftJLSTests/Fixtures']:
 a=repo/scope;b=snap/scope;files=[a] if a.is_file() else [x for x in a.rglob('*') if x.is_file() and '__pycache__' not in x.parts]
 other=[b] if b.is_file() else [x for x in b.rglob('*') if x.is_file() and '__pycache__' not in x.parts]
 assert {str(x.relative_to(repo)):h(x) for x in files}=={str(x.relative_to(snap)):h(x) for x in other}
assert h(tool)==initial
(audit/'038-factory-workspace-controls.json').write_text(json.dumps(r,indent=2)+'\n')
print('CLASSIFIER',initial,'BINARY',r['workspace_probe_sha256']);print('COPY',r['copy']['receipt_sha256'])
for name,v in r['profiles'].items():print(name,'calls',v['phase_calls'],'peak',v['phase_peak'],'pixel',v['pixel']['phase_allocated_bytes'],'changes',len(v['changed_stacks']),'unknown',v['unknown'])
print('ALL CONTROL AND REPLAY CHECKS PASS')
