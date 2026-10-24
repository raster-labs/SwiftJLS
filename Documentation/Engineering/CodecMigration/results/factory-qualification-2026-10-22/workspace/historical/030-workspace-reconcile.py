#!/usr/bin/env python3
"""Independent read-only reconciliation of the completed local workspace campaign."""
import collections,gzip,hashlib,importlib.util,json,pathlib,subprocess,sys,time
sys.dont_write_bytecode = True
P=pathlib.Path
scratch=P('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch')
repo=P('/Users/pushparaj/projects/SwiftJLS')
root=scratch/'campaigns/workspace89-linux-004'
audit=P('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def check(v,message):
 if not v: raise AssertionError(message)
complete=read(root/'complete.json');outer=read(root/'outer-command-receipt.json');rec=read(root/'profiles/reconciliation-summary.json');meta=outer['snapshot_identity']
check(complete['completed'] is True and outer['returncode']==0,'outer completion')
check(sha(root/'outer-command-receipt.json')==complete['outer_command_receipt_sha256'],'outer hash')
check(sha(root/'frozen_runner.py')==complete['runner_sha256']==outer['runner_sha256'],'runner hash')
manifest_path=P(meta['manifest_path']);manifest=read(manifest_path);snap=P(meta['snapshot_root'])
check(sha(manifest_path)==sha(root/'frozen_source_manifest.json')==complete['manifest_sha256']==meta['manifest_sha256'],'manifest hash')
revision='working-tree:'+sha(manifest_path)
check(revision==complete['workspace_revision_id']==meta['workspace_revision_id']==rec['workspace_revision_id'],'revision')
actual={str(p.relative_to(snap)):sha(p) for p in snap.rglob('*') if p.is_file()}
check(actual==manifest['files'] and len(actual)==2890,'exact snapshot set')
check(not any(p.is_symlink() for p in snap.rglob('*')),'snapshot symlink')
validation=P(meta['reconciliation']['verified_against_validation_snapshot'])
differences=[]
for rel,digest in actual.items():
 check(sha(repo/rel)==digest,'current source/fixture/tool drift '+rel)
 if sha(validation/rel)!=digest:differences.append(rel)
check(differences==['Scripts/StorageEvidence/measure-operation.py'],'validation exception '+str(differences))
classifier=snap/'Scripts/StorageEvidence/measure-operation.py'
check(sha(classifier)=='ffbc1b6a13327ce2403822d3ff4647743df474d32167a226cd1e3d6f7c9b25d5','classifier')
check(sha(validation/'Scripts/StorageEvidence/measure-operation.py')=='996280213e506bfe8acf54acb6cfc67ac276eaec90128edadf9ef1b15d76acd1','prior classifier')
scopes=['Package.swift','VERSION','Sources','Examples/WorkspaceProbe','Scripts/StorageEvidence','Tests/SwiftJLSTests/Fixtures']
base=meta['base_revision']
base_set=set(subprocess.check_output(['git','-C',str(repo),'ls-tree','-r','--name-only',base,'--',*scopes],text=True).splitlines())
check(set(actual)==base_set,'base scope file set')
changed=set(subprocess.check_output(['git','-C',str(repo),'diff','--name-only',base,'--',*scopes],text=True).splitlines())
check(changed=={'Sources/SwiftJLS/Image.swift','Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift','Sources/SwiftJLS/JPEGLS/ScalarCodec.swift','Scripts/StorageEvidence/measure-operation.py','Scripts/StorageEvidence/run-workspace-profiles.py'},'base changed set')
for n,key in [('candidate-sources.patch','candidate_sources_patch_sha256'),('candidate-scripts.patch','candidate_scripts_patch_sha256')]:check(sha(snap.parent/n)==manifest[key]==meta[key],n)
binary_sha=sha(root/'WorkspaceProbe');check(binary_sha==outer['built_binary_sha256']==rec['built_workspace_probe_binary_sha256'],'binary hash')
check(sha(root/'build/out/Products/Release-linux-aarch64/WorkspaceProbe')==binary_sha,'original build binary')
check(sha(root/'profiles/reconciliation-summary.json')==complete['reconciliation']['reconciliation_summary_sha256'],'aggregate hash')
lib=rec['libunwind_183_receipt']
check(sha(P(lib['tarball_path']))==lib['tarball_sha256']=='be30d910e67f58d82e753231f1357f326a1a088acf126b21ff77e60aab19b90b','lib source')
for filename,key in [('libunwind.so.8.2.0','libunwind_so_8_2_0_sha256'),('libunwind-aarch64.so.8.2.0','libunwind_aarch64_so_8_2_0_sha256')]:check(sha(root/'libunwind-183-prefix/lib'/filename)==lib[key],filename)
check(sha(root/'libunwind-183-ldd.txt')==lib['ldd_binding_sha256'],'ldd hash')
check('/evidence/libunwind-183-prefix/lib/libunwind.so.8' in (root/'libunwind-183-ldd.txt').read_text(),'private binding')
# Independent declared case list, not loaded from the runner.
cases=[]
for size in [17,512]:
 for c in [1,3]:
  for near in [0,3]:
   for op in ['encode','owned','into','inspect']:cases.append([f'{size}-{c}-{near}-{op}',[op,str(size),str(size),str(c),str(near)]])
for profile,c,near in [('line',3,0),('line',3,3),('planar',3,0),('planar',3,3),('p16',1,0),('p16',3,3),('preset',1,3),('preset',3,0),('restart',3,3),('hp1',3,0),('hp2',3,0),('hp3',3,0)]:
 for op in ['encode','owned','into','inspect']:cases.append([f'{profile}-{c}-{near}-{op}',[op,'257','129',str(c),str(near),profile]])
for fixture in ['subsampled-zero-n0','map-p16-c3-i0-w1-n0','extended-p12-65537x2']:
 for op in ['owned','into','inspect']:cases.append([f'{fixture}-{op}',[op,'--fixture',f'Tests/SwiftJLSTests/Fixtures/{fixture}.jls']])
matrix=read(root/'profiles/matrix.json');check(len(cases)==89 and matrix=={'revision':revision,'cases':cases},'matrix')
check(sha(root/'profiles/matrix.json')==rec['matrix_json_sha256']==complete['reconciliation']['matrix_json_sha256'],'matrix hash')
check({p.name for p in (root/'profiles').iterdir() if p.is_dir()}=={c[0] for c in cases},'case directory set')
# Load only the existing classifier/replay code; no main/self-test/profile execution.
spec=importlib.util.spec_from_file_location('audit_replay',classifier);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
rows=[];total_raw_allocations=0;operation_counts=collections.Counter();phase_calls=collections.Counter();owned_calls=0
for name,args in cases:
 p=root/'profiles'/name;raw=p/'allocations.gz';raw_sha=sha(raw);report=read(p/'operation.json');summary=read(p/'summary.json');commands=read(p/'commands.json')
 expected=[['heaptrack','--version'],['heaptrack','-o',f'/evidence/profiles/{name}/allocations','/evidence/build/out/Products/Release-linux-aarch64/WorkspaceProbe',*args],['heaptrack_print','-f',f'/evidence/profiles/{name}/allocations.gz','-n','1000','-s','1000','-H',f'/evidence/profiles/{name}/sizes.tsv','-F',f'/evidence/profiles/{name}/allocation-stacks.txt']]
 check(commands==[{'command':c,'exit_code':0} for c in expected],name+' exact commands')
 check(summary['commands']==commands and summary['binary_sha256']==binary_sha and summary['profile']=='allocations.gz' and summary['profile_sha256']==raw_sha,name+' summary')
 check(report['revision']==revision and report['profile_sha256']==raw_sha,name+' report identity')
 lines=gzip.open(raw,'rt').readlines();replayed=mod.replay(lines)
 check(replayed=={k:v for k,v in report.items() if k not in ['revision','profile_sha256']},name+' raw replay mismatch')
 groups=report['groups'];check(report['codec_heap_attribution_complete'] is True and report['pure_algorithm_workspace_complete'] is False,name+' completeness scope')
 check(report['stack_peak_bytes'] is None and report['allocator_overhead_bytes'] is None,name+' unknown limits')
 check(sum(g['baseline_live_bytes'] for g in groups.values())==report['baseline_total_requested_heap_bytes'],name+' baseline sum')
 check(sum(report['simultaneous_categories_at_phase_peak_bytes'].values())==report['phase_total_requested_heap_peak_bytes'],name+' simultaneous sum')
 check(report['phase_total_requested_heap_peak_bytes']-report['baseline_total_requested_heap_bytes']==report['phase_total_peak_above_baseline_bytes'],name+' peak delta')
 check(report['process_requested_heap_peak_bytes']>=report['phase_total_requested_heap_peak_bytes'],name+' process peak')
 calls=collections.Counter();allocated=collections.Counter()
 for v in report['allocation_stacks'].values():
  check(sum(v['requested_size_counts'].values())==v['allocation_calls'],name+' stack call count')
  check(sum(int(size)*n for size,n in v['requested_size_counts'].items())==v['allocated_bytes'],name+' stack requested bytes')
  calls[v['category']]+=v['allocation_calls'];allocated[v['category']]+=v['allocated_bytes']
 for category,g in groups.items():
  check(g['phase_allocation_calls']==calls[category] and g['phase_allocated_bytes']==allocated[category],name+' group counts')
  check(g['peak_live_bytes']>=max(g['baseline_live_bytes'],g['end_live_bytes']) and g['peak_above_baseline_bytes']==g['peak_live_bytes']-g['baseline_live_bytes'],name+' category peaks')
  check(all(v>=0 for v in g.values()),name+' nonnegative counts')
 unknown=groups.get('unattributed_codec',{});check(unknown.get('baseline_live_bytes',0)==0 and unknown.get('phase_allocation_calls',0)==0,name+' unclassified codec')
 owned=groups.get('owned_pixel_buffer',{});check(owned.get('phase_allocation_calls',0)==(1 if args[0]=='owned' else 0),name+' owned calls')
 check((owned.get('peak_above_baseline_bytes',0)>0)==(args[0]=='owned'),name+' owned peak')
 consumer=[json.loads(line) for line in (p/'consumer.stdout').read_text().splitlines() if line.startswith('{')]
 check(len(consumer)==1 and consumer[0]['samples_verified'] is True and consumer[0]['operation']==args[0],name+' consumer verification')
 if args[1]=='--fixture':check(consumer[0]['fixture']==P(args[2]).name,name+' fixture')
 else:
  for key,val in zip(['width','height','components','near'],args[1:5]):check(consumer[0][key]==int(val),name+' '+key)
  check(consumer[0]['profile']==(args[5] if len(args)==6 else 'base'),name+' profile')
 stored=next(x for x in rec['cases'] if x['case']==name)
 for filename,key in [('commands.json','commands_json_sha256'),('summary.json','trace_summary_json_sha256'),('operation.json','operation_json_sha256')]:check(sha(p/filename)==stored[key],name+' '+filename+' hash')
 check(stored['args']==args and stored['operation']==args[0] and stored['binary_sha256']==binary_sha and stored['profile_sha256']==raw_sha,name+' aggregate binding')
 for key in ['baseline_total_requested_heap_bytes','phase_total_requested_heap_peak_bytes','phase_total_peak_above_baseline_bytes']:check(stored[key]==report[key],name+' aggregate '+key)
 raw_allocs=sum(l.startswith('+ ') for l in lines);total_raw_allocations+=raw_allocs;operation_counts[args[0]]+=1;phase_calls.update(calls);owned_calls+=owned.get('phase_allocation_calls',0)
 rows.append({'case':name,'raw_allocations':raw_allocs,'phase_calls':sum(calls.values()),'phase_peak_bytes':report['phase_total_requested_heap_peak_bytes'],'peak_above_baseline_bytes':report['phase_total_peak_above_baseline_bytes'],'operation_sha256':sha(p/'operation.json'),'profile_sha256':raw_sha})
check(len(rec['cases'])==89 and len({x['case'] for x in rec['cases']})==89,'aggregate case uniqueness')
check(max(r['peak_above_baseline_bytes'] for r in rows)==rec['max_phase_total_peak_above_baseline_bytes'],'aggregate max')
copy=rec['linked_copy_probe_receipt'];check(sha(P(copy['receipt_path']))==copy['receipt_sha256'] and sha(P(copy['binary_path']))==copy['binary_sha256'],'linked CopyProbe')
check(sha(classifier)==sha(repo/'Scripts/StorageEvidence/measure-operation.py')=='ffbc1b6a13327ce2403822d3ff4647743df474d32167a226cd1e3d6f7c9b25d5','classifier unchanged')
check({str(p.relative_to(snap)):sha(p) for p in snap.rglob('*') if p.is_file()} == manifest['files'], 'post-audit snapshot set/hashes')
result={'status':'passed','cases_replayed':89,'source_files_verified':len(actual),'validation_snapshot_exceptions':differences,'workspace_revision_id':revision,'binary_sha256':binary_sha,'classifier_sha256':sha(classifier),'source_manifest_sha256':sha(manifest_path),'runner_sha256':sha(root/'frozen_runner.py'),'matrix_sha256':sha(root/'profiles/matrix.json'),'outer_receipt_sha256':sha(root/'outer-command-receipt.json'),'aggregate_sha256':sha(root/'profiles/reconciliation-summary.json'),'operation_counts':dict(operation_counts),'phase_allocation_calls_by_category':dict(phase_calls),'total_raw_process_allocations':total_raw_allocations,'owned_pixel_allocations_in_marked_phases':owned_calls,'maximum_peak_above_baseline':max(rows,key=lambda r:r['peak_above_baseline_bytes']),'maximum_phase_peak':max(rows,key=lambda r:r['phase_peak_bytes']),'unknown_universal_workspace_preserved':True,'cases':rows}
out=audit/'030-workspace-results.json';out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2));print('AUDIT_RECEIPT',out)
