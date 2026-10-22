from pathlib import Path
import hashlib,json,datetime
s=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch');root=Path('/Users/pushparaj/projects/SwiftJLS');snap=s/'snapshots/frozen-candidate-validation-002/SwiftJLS';audit=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022')
h=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(base,scope):
 q=base/scope
 return {str(p.relative_to(base)):h(p) for p in ([q] if q.is_file() else q.rglob('*')) if p.is_file() and not set(p.relative_to(base).parts)&{'.build','.git','.swiftpm','__pycache__','.DS_Store'}}
r={'generated_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scopes':{},'inventory':{}}
for scope in ['Sources','Tests','Package.swift','VERSION','Scripts/Interop','Scripts/test-payload-cli.py','Examples/IndependentConsumer','Examples/CrossCodecConsumer','Examples/ResourceStress','Examples/AppleRuntimeConsumer']:
 a,b=inventory(root,scope),inventory(snap,scope);assert a==b,scope;r['scopes'][scope]=len(a);r['inventory'].update(b)
p=s/'diagnostics/frozen-candidate-extended-validation-002.json';d=json.loads(p.read_text());r['receipt_sha256']=h(p);ep=Path(d['events_jsonl']);ev=[json.loads(l) for l in ep.read_text().splitlines()];assert h(ep)==d['events_jsonl_sha256'];assert len(ev)==11;assert [e['step'] for e in ev]==[x['step'] for x in d['steps']];assert all(e['returncode']==0 for e in ev);r['events_sha256']=h(ep)
for rel,v in d['tracked_file_hashes'].items():assert h(root/rel)==h(snap/rel)==v
r['tracked_file_hashes']=d['tracked_file_hashes'];r['reports']={}
for k,v in d['reports'].items():
 p=Path(v['path']);assert h(p)==v['sha256'];j=json.loads(p.read_text());rows=j['cases'] if isinstance(j,dict) else j
 if k=='payload_cli':
  assert len(rows)==73;assert all(x['exit']==x['expected'] for x in rows if 'expected' in x);assert {x['condition']:x['exit'] for x in rows if 'condition' in x}=={'deadline blocked pipe':5,'cancel blocked pipe':130,'closed binary output':6}
 else:assert all(x['passed'] for x in rows)
 r['reports'][k]={'sha256':h(p),'count':len(rows)}
 if k in ['interop_scalar','interop_component']:assert all(x['maximum_error']<=x['near'] for x in rows)
 if k=='interop_mapping':assert all(h(snap/'interop-encoded'/(x['name']+'.jls'))==x['encoded_sha256'] for x in rows)
f=snap/'Tests/SwiftJLSTests/Fixtures';mf=lambda name:json.loads((f/(name+'.json')).read_text())['cases']
expected={'interop_scalar':[x['name'] for x in mf('manifest') if not x.get('preset')],'interop_component':[x['name']+('' if n==0 else '-r3') for m in ['components','components-hp','components-legacy-hp'] for x in mf(m) for n in ([0,3] if x['interleave']==0 else [0])],'interop_mapping':[x['name'] for m in ['mapping','extended','legacy-profiles','legacy-combined'] for x in mf(m)]}
r['outputs']={}
for key,names in expected.items():
 j=json.loads(Path(d['reports'][key]['path']).read_text());rows=j['cases'] if isinstance(j,dict) else j;assert names==[x['name'] for x in rows];assert len(names)==len(set(names))
 for name in names:
  p=snap/'interop-encoded'/(name+'.jls');assert p.is_file();r['outputs'][name]={'sha256':h(p),'size':p.stat().st_size,'mtime':p.stat().st_mtime}
assert all(datetime.datetime.fromisoformat(ev[7]['started_utc']).timestamp()<=v['mtime']<=datetime.datetime.fromisoformat(ev[7]['finished_utc']).timestamp() for v in r['outputs'].values())
combined=''.join((snap/'Scripts/Interop'/p).read_text()+'\n' for p in ['Consumer.swift','ComponentConsumer.swift','LegacyMigrationConsumer.swift','MappingConsumer.swift']);assert (snap/'InteropConsumerPkg/Sources/Consumer/main.swift').read_text()==combined;assert str(snap) in (snap/'InteropConsumerPkg/Package.swift').read_text()
r['binary_hashes']={}
old_events=[json.loads(l) for l in (s/'diagnostics/frozen-candidate-extended-validation-001-events.jsonl').read_text().splitlines()]
for prefix,step in [('charls_driver_36dd3307','build_charls_driver_36dd3307'),('mapping_driver_04e44bb7','build_mapping_driver_04e44bb7')]:
 p=Path(d['reused_oracle_binaries'][prefix+'_path']);assert h(p)==d['reused_oracle_binaries'][prefix+'_sha256'];b=next(e for e in old_events if e['step']==step);assert str(p)==b['command'][-1] and b['returncode']==0;assert datetime.datetime.fromisoformat(b['started_utc']).timestamp()<=p.stat().st_mtime<=datetime.datetime.fromisoformat(b['finished_utc']).timestamp();r['binary_hashes'][str(p)]={'sha256':h(p),'mtime':p.stat().st_mtime}
for rel,step in [('.build/out/Products/Release/swiftjls-cli','build_swiftjls_cli_release'),('InteropConsumerPkg/.build/out/Products/Release/Consumer','interop_consumer_encode'),('Examples/IndependentConsumer/.build/out/Products/Release/Consumer','example_independent_consumer'),('Examples/CrossCodecConsumer/.build/out/Products/Release/CrossCodecConsumer','example_cross_codec_consumer'),('Examples/ResourceStress/.build/out/Products/Release/ResourceStress','example_resource_stress'),('Examples/AppleRuntimeConsumer/.build/out/Products/Release/AppleRuntimeConsumer','example_apple_runtime_consumer_macos')]:
 p=snap/rel;assert p.is_file();b=next(e for e in ev if e['step']==step);assert datetime.datetime.fromisoformat(b['started_utc']).timestamp()<=p.stat().st_mtime<=datetime.datetime.fromisoformat(b['finished_utc']).timestamp(),rel;r['binary_hashes'][str(p)]={'sha256':h(p),'mtime':p.stat().st_mtime}
oldmac=s/'diagnostics/frozen-candidate-extended-validation-001-macos-only.json';assert h(oldmac)=='5bdce9f399b0ac2db4044d271104d166af46788a6d50109be20813c8892a96d7';olde=s/'diagnostics/frozen-candidate-extended-validation-001-events.jsonl';assert hashlib.sha256(b''.join(olde.read_bytes().splitlines(keepends=True)[:16])).hexdigest()=='17245ba41c6a88b9c5ab7ffd076968f84a1cf2e92e4673946bff87aad803d05d'
r['original_receipts']={name:h(s/'diagnostics'/name) for name in ['frozen-candidate-extended-validation-001.json','frozen-candidate-extended-validation-001-events.jsonl','frozen-candidate-extended-validation-001-macos-only.json']}
# Reconfirm reviewed source parity after all read-only reconciliation.
for scope in r['scopes']:assert inventory(root,scope)==inventory(snap,scope)=={k:v for k,v in r['inventory'].items() if k==scope or k.startswith(scope+'/')}
(audit/'036-extended-validation.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k not in ['inventory','outputs']},indent=2));print('Fresh streams checked:',len(r['outputs']))
