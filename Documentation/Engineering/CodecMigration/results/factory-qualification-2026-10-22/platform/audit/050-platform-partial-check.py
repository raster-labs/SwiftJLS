#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, xml.etree.ElementTree as ET, datetime, re, subprocess
P=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/platform_validation_002')
R=Path('/Users/pushparaj/projects/SwiftJLS'); A=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022')
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def read(p):return json.loads(p.read_text())
receipts=[P/'tests/source.json',P/'tests/results.json',P/'tests/toolchain.json',P/'qualification-source.json',P/'apple-value/build-results.json',P/'apple-value/binary-manifest.json',P/'apple-value/environment.json',P/'simulator-restore-after-runtime.json']+sorted((P/'apple-value').glob('*-26.0-*.json'))
pins={str(p.relative_to(P)):sha(p) for p in receipts}
pre=read(A/'050-platform-preflight.json')['hashes']; drivers={n:sha(P/n) for n in pre}
s=read(P/'tests/source.json');qual=read(P/'qualification-source.json');assert s==qual
for rel,h in s['files'].items():assert sha(R/rel)==h,rel
assert hashlib.sha256(json.dumps(s['files'],sort_keys=True).encode()).hexdigest()==s['source_manifest_sha256']
prior=read(A/'050-source-check.json')
assert {n:h for n,h in s['files'].items() if n in prior['production_source_inventory']}==prior['production_source_inventory']
assert {n:h for n,h in s['files'].items() if n in prior['test_swift_inventory']}==prior['test_swift_inventory']
assert s['production_file_count']==38 and s['test_swift_count']==31 and s['source_id']=='factory_002' and s['source_commit'] is None
assert hashlib.sha256(subprocess.check_output(['git','diff',s['base_head'],'--','Sources/SwiftJLS'],cwd=R)).hexdigest()==s['sources_patch_sha256']
testrows=[];ts=read(P/'tests/results.json');assert {x['label'] for x in ts}=={'debug','release','asan','tsan'} and len(ts)==4
for x in ts:
 name=x['label'];cmd=x['command'];assert x['exit_code']==0 and cmd[0:2]==['swift','test']
 assert cmd[cmd.index('--scratch-path')+1]==str(P/'test-build'/name)
 assert cmd[cmd.index('--xunit-output')+1]==str(P/'tests'/f'{name}.xml')
 if name=='asan':assert cmd[cmd.index('--sanitize')+1]=='address'
 elif name=='tsan':assert cmd[cmd.index('--sanitize')+1]=='thread'
 elif name=='release':assert cmd[cmd.index('-c')+1]=='release'
 else:assert '--sanitize' not in cmd and '-c' not in cmd
 xml=P/'tests'/f'{name}.xml';assert sha(xml)==x['xml_sha256']
 cases=ET.parse(xml).findall('.//testcase');assert len(cases)==149 and all(all(c.find(z) is None for z in ['failure','error','skipped']) for c in cases)
 assert len({(c.get('classname'),c.get('name')) for c in cases})==149
 log=P/'tests'/f'{name}.log';assert re.search(r'Test run with 149 tests in 27 suites passed',log.read_text())
 assert sha(Path(x['bundle_executable']))==x['bundle_executable_sha256']
 if name=='release':assert sha(Path(x['cli_binary']))==x['cli_binary_sha256']
 testrows.append({'mode':name,'tests':149,'console_suites':27,'xml_classname_groups':len({c.get('classname') for c in cases}),'xml_sha256':sha(xml),'log_sha256':sha(log),'bundle_sha256':x['bundle_executable_sha256']})
assert len({x['bundle_sha256'] for x in testrows})==4
env=read(P/'apple-value/environment.json');assert env['source_manifest_sha256']==s['source_manifest_sha256'] and env['sources_patch_sha256']==s['sources_patch_sha256']
b=read(P/'apple-value/build-results.json');assert len(b)==17 and all(x['exit_code']==0 for x in b)
final_artifacts={}
for x in b:
 assert sha(P/x['log'])==x['log_sha256']
 for rel,v in x.get('artifacts',{}).items():final_artifacts[rel]=v['sha256']
for rel,h in final_artifacts.items():assert sha(P/rel)==h,rel
libraries=[x for x in b if '-emit-library' in x['command']];assert len(libraries)==4
for x in libraries+[x for x in b if '-emit-module' in x['command'] and '-emit-library' not in x['command']]:
 assert {v for v in x['command'] if v.endswith('.swift')}=={str(R/n) for n in prior['production_source_inventory']}
 assert '-strict-concurrency=complete' in x['command'] and '26.0' in x['command'][x['command'].index('-target')+1]
manifest=read(P/'apple-value/binary-manifest.json');assert set(manifest)=={'iphonesimulator','appletvsimulator','xrsimulator','watchsimulator','watchos_arm64_32'}
for sdk,v in manifest.items():
 for pathkey,hashkey in [('library_dylib','library_dylib_sha256'),('swiftmodule','swiftmodule_sha256'),('consumer_binary','consumer_binary_sha256')]:
  if pathkey in v:assert sha(P/v[pathkey])==v[hashkey]
runtime_rows=[]
expected_lines=['Independent consumer passed: native lossless coding preserves padded 12-bit samples and destination identity.','Apple runtime passed: direct storage, RGB/HP, mapping, metadata, Watch limits and cancellation.','Combined legacy mapping/HP runtime passed.']
restored=read(P/'simulator-restore-after-runtime.json')['devices'];restored_by_id={d['udid']:d for ds in restored.values() for d in ds}
for f in sorted((P/'apple-value').glob('*-26.0-*.json')):
 x=read(f);rt=x['runtime'];dev=x['device'];sdk=x['sdk'];cmds=x['commands']
 assert rt['version']=='26.0' and rt['isAvailable'] and x['source_manifest_sha256']==s['source_manifest_sha256']
 assert all(v['exit_code']==0 for v in cmds)
 spawn=[v for v in cmds if v['command'][2]=='spawn'];assert len(spawn)==1;sp=spawn[0]
 assert sp['command'][3:]==[dev['udid'],str(P/manifest[sdk]['consumer_binary']),str(R/'Tests/SwiftJLSTests/Fixtures')]
 assert all(line in sp['stdout'] for line in expected_lines)
 assert x['consumer_binary_sha256']==manifest[sdk]['consumer_binary_sha256'] and x['library_dylib_sha256']==manifest[sdk]['library_dylib_sha256']
 assert restored_by_id[dev['udid']]['state']==dev['state']
 if dev['state']!='Booted':assert cmds[-1]['command'][2]=='shutdown'
 runtime_rows.append({'device':dev['name'],'udid':dev['udid'],'runtime':rt['name'],'version':rt['version'],'build':rt['buildversion'],'sdk':sdk,'commands':len(cmds),'exit_codes':[v['exit_code'] for v in cmds],'receipt_sha256':sha(f),'consumer_sha256':x['consumer_binary_sha256'],'library_sha256':x['library_dylib_sha256'],'initial_final_state':dev['state']})
assert len(runtime_rows)==5 and sum(x['sdk']=='iphonesimulator' for x in runtime_rows)==2
for rel,h in pins.items():assert sha(P/rel)==h,rel
assert drivers=={n:sha(P/n) for n in pre}
result={'status':'accepted_completed_host_sdk_runtime_subset','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_manifest_sha256':s['source_manifest_sha256'],'source_files_verified':len(s['files']),'source_equals_factory002_050':True,'receipts_unchanged_during_audit':True,'receipt_sha256':pins,'driver_sha256':drivers,'drivers_changed_since_preflight':{n:{'previous':pre[n]['sha256'],'current':drivers[n]} for n in pre if pre[n]['sha256']!=drivers[n]},'host_toolchain':read(P/'tests/toolchain.json'),'host_tests':testrows,'sdk_environment':env,'sdk_command_count':len(b),'sdk_binary_manifest':manifest,'runtime_consumers':runtime_rows,'pending_not_audited':['resource simulator results','native guest execution','host consumer and CLI outputs'],'scope':'Independent read/hash/XML/command audit only. No build/test/measurement/VM operation.'}
(A/'050-platform-partial.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k in ['status','checked_utc','source_manifest_sha256','source_files_verified','receipts_unchanged_during_audit','drivers_changed_since_preflight','host_tests','sdk_command_count','runtime_consumers','pending_not_audited']},indent=2))
