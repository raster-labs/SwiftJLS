#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,xml.etree.ElementTree as ET,datetime,re
P=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/platform_validation_002')
A=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022');R=Path('/Users/pushparaj/projects/SwiftJLS')
def read(p):return json.loads(p.read_text())
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
partial=read(A/'050-platform-partial.json')
for rel,h in partial['receipt_sha256'].items():assert sha(P/rel)==h,rel
src=read(P/'qualification-source.json')
for rel,h in src['files'].items():assert sha(R/rel)==h,rel
manifest=read(P/'native-payload/manifest.json'); old=read(P/'native-payload-manifest-attempt-1.json');payload=P/'native-payload'
assert manifest['source_manifest_sha256']==old['source_manifest_sha256']==partial['source_manifest_sha256']
assert set(manifest['files'])-set(old['files'])=={'repo/ManPages/swiftjls-cli.1'}
assert not set(old['files'])-set(manifest['files'])
assert all(manifest['files'][n]==h for n,h in old['files'].items())
for rel,h in manifest['files'].items():assert sha(payload/rel)==h,rel
for rel,h in src['files'].items():assert manifest['files']['repo/'+rel]==h,rel
assert sha(R/'ManPages/swiftjls-cli.1')==manifest['files']['repo/ManPages/swiftjls-cli.1']
assert sha(P/'run-native-template.py')==sha(payload/'run-native.py')
assert manifest['expected_test_declarations']==149
pins={}
def pin(p):pins[str(p.relative_to(P))]=sha(p)
for f in ['native-payload/manifest.json','native-payload-manifest-attempt-1.json','consumer-builds.json','value-qualification-commands.json','resource26-value/summary.json','resource26-value/commands.json','simulator-restore.json','native-driver.py','prepare-native.py','run-native-template.py','native-driver-commands-attempt-1.json','native-driver-commands.json','native-vm-process-attempt-1.json','native-vm-process.json']:pin(P/f)
commands=read(P/'value-qualification-commands.json');assert len(commands)==9 and all(v['exit_code']==0 for v in commands)
for v in commands:
 assert sha(P/v['log'])==v['log_sha256'];pin(P/v['log'])
cons=read(P/'consumer-builds.json');assert cons['source']==src
for n in ['AppleRuntimeConsumer','ResourceStress']:
 v=cons['binaries'][n];assert sha(Path(v['path']))==v['sha256']==manifest['consumer_binary_sha256'][n]==sha(payload/n)
assert 'Apple runtime passed:' in (P/'host-AppleRuntimeConsumer-value.log').read_text()
def check_rows(rows):
 assert len(rows)==4 and sum(x['frames'] for x in rows)==32
 assert all(x['ownedPixelAllocations']==x['frames'] and x['suppliedPixelAllocations']==0 and x['reportedCopyBytes']==0 for x in rows)
check_rows(read(P/'host-ResourceStress-value.log'))
resource=read(P/'resource26-value/summary.json');assert resource['source_manifest_sha256']==src['source_manifest_sha256'] and len(resource['workloads'])==4
resource_cmds=read(P/'resource26-value/commands.json');assert len(resource_cmds)==20 and all(v['exit_code']==0 for v in resource_cmds)
apple=partial['sdk_binary_manifest']
for sdk,v in resource['binaries'].items():assert sha(P/v['path'])==v['sha256'] and v['library_dylib_sha256']==apple[sdk]['library_dylib_sha256']
for w in resource['workloads']:
 assert w['runtime']=='26.0' and w['frames']==32;check_rows(w['rows'])
 sp=[v for v in resource_cmds if v['label']==w['label']];assert len(sp)==1
 assert sp[0]['command'][0:4]==['xcrun','simctl','spawn',w['device_udid']]
 assert sp[0]['command'][4]==str(P/resource['binaries'][w['sdk']]['path'])
 assert json.loads(sp[0]['stdout'])==w['rows']
state=read(P/'simulator-restore.json')['devices'];state={d['udid']:d['state'] for ds in state.values() for d in ds}
for w in partial['runtime_consumers']:assert state[w['udid']]==w['initial_final_state']
cli_sha=manifest['cli_binary_sha256'];assert sha(payload/'swiftjls-cli')==cli_sha

def cli(sub):
 pay=P/sub/'cli-payload.json' if sub.startswith('native') else P/'cli-payload-value.json'
 pro=P/sub/'cli-process/report.json' if sub.startswith('native') else P/'cli-process-value/report.json'
 pl=read(pay);pr=read(pro);assert len(pl)==73 and all(x['exit']==(x['expected'] if 'expected' in x else {'deadline blocked pipe':5,'cancel blocked pipe':130,'closed binary output':6}[x['condition']]) for x in pl)
 assert pr['status']=='passed' and pr['checks']==len(pr['commands'])==103
 assert all(x['exit_code']==x['expected_exit_code'] for x in pr['commands'])
 assert pr['binary_sha256']==cli_sha
 for key,file in [('test_runner_sha256','Scripts/test-cli.py'),('installer_sha256','Scripts/install-cli.sh'),('manual_sha256','ManPages/swiftjls-cli.1')]:assert pr[key]==sha(R/file)==sha(payload/'repo'/file)
 pin(pay);pin(pro);return {'payload_cases':73,'process_checks':103,'binary_sha256':cli_sha,'payload_sha256':sha(pay),'process_report_sha256':sha(pro)}
host_cli=cli('host')
prior_bundle={x['mode']:x['bundle_sha256'] for x in partial['host_tests']};assert manifest['bundle_executable_sha256']==prior_bundle
attempts=[]
for sub,expected_exit in [('native-results-attempt-1',2),('native-results',0)]:
 base=P/sub;d=read(base/'results.json');pin(base/'results.json')
 for f in base.rglob('*'):
  if f.is_file():pin(f)
 assert d['source_manifest_sha256']==src['source_manifest_sha256'] and d['source'] is None
 assert d['guest_verified_bundle_executable_sha256']==prior_bundle
 assert d['guest_verified_cli_binary_sha256']==cli_sha
 assert d['guest_verified_consumer_binary_sha256']==manifest['consumer_binary_sha256']
 assert d['architecture']=='arm64' and 'ProductVersion:\t\t26.0' in d['os'] and '25A354' in d['os'] and d['exact_26_0_native_arm64']
 assert (base/'os.stdout').read_text()==d['os'] and (base/'architecture.stdout').read_text().strip()=='arm64'
 cmds=d['commands'];assert len(cmds)==11 and [v['label'] for v in cmds]==['os','architecture','hardware','unit','unit-debug','unit-asan','unit-tsan','consumer','resources','cli-payload','cli-process']
 assert all(v['exit_code']==0 for v in cmds[:-1]) and cmds[-1]['exit_code']==expected_exit
 tests=[]
 for mode in ['release','debug','asan','tsan']:
  label='unit' if mode=='release' else 'unit-'+mode;xml=base/(label+'.xml');v=d['tests'] if mode=='release' else d['extra_tests'][mode]
  cases=ET.parse(xml).findall('.//testcase');assert len(cases)==149 and len({(c.get('classname'),c.get('name')) for c in cases})==149
  assert all(all(c.find(z) is None for z in ['failure','error','skipped']) for c in cases)
  assert sha(xml)==v['xml_sha256'] and v['declarations']==149 and v['failures']==v['skipped']==0
  assert re.search(r'Test run with 149 tests in 27 suites passed',((base/(label+'.stdout')).read_text()+(base/(label+'.stderr')).read_text()))
  tests.append({'mode':mode,'tests':149,'console_suites':27,'xml_sha256':sha(xml),'bundle_sha256':prior_bundle[mode]})
 assert 'Combined legacy mapping/HP runtime passed.' in (base/'consumer.stdout').read_text()
 check_rows(read(base/'resources.stdout'));pl=read(base/'cli-payload.json');assert len(pl)==73 and all(x['exit']==(x['expected'] if 'expected' in x else {'deadline blocked pipe':5,'cancel blocked pipe':130,'closed binary output':6}[x['condition']]) for x in pl)
 if expected_exit:
  assert 'Binary name must match this repository manual' in (base/'cli-process.stderr').read_text()
  assert 'repo/ManPages/swiftjls-cli.1' not in old['files']
  assert not d.get('success',False) and not (base/'cli-process/report.json').exists()
  cli_result={'payload_cases':73,'process_gate_exit':2,'failure':'missing guest ManPages/swiftjls-cli.1; binary name and SHA unchanged'}
 else:
  assert d['success'] is True;cli_result=cli(sub)
 attempts.append({'directory':sub,'result_sha256':sha(base/'results.json'),'tests':tests,'commands':len(cmds),'command_exit_codes':[x['exit_code'] for x in cmds],'cli':cli_result})
for suffix in ['-attempt-1','']:
 logs=read(P/f'native-driver-commands{suffix}.json');assert 'm4-macos26' in logs[0]['stdout'] and re.search(r'm4-macos26.*stopped',logs[0]['stdout'])
 assert re.search(r'm4-macos26.*stopped',logs[-1]['stdout']) and logs[-1]['exit_code']==0
 vm=read(P/f'native-vm-process{suffix}.json');assert '--dir=evidence:'+str(payload)+':ro' in vm['command']
 assert vm['source_manifest_sha256']==src['source_manifest_sha256']
 assert all(x.get('exit_code')==0 for x in logs if x['label']!='guest qualification')
for rel,h in pins.items():assert sha(P/rel)==h,rel
out={'status':'accepted_host_simulator_native_factory002_platform_evidence','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_manifest_sha256':src['source_manifest_sha256'],'source_files_verified':len(src['files']),'native_payload_files_verified':len(manifest['files']),'native_payload_manifest_delta':['added repo/ManPages/swiftjls-cli.1; all prior entries and digests identical'],'factory002_production_unchanged':True,'prior_partial_report_sha256':sha(A/'050-platform-partial.json'),'host_cli':host_cli,'simulator_resource_profiles':[{'device':w['device_name'],'runtime':w['runtime'],'runtime_build':w['runtime_build'],'frames':w['frames'],'binary_sha256':w['binary_sha256']} for w in resource['workloads']],'native_attempts':attempts,'native_guest':'macOS26.0 build25A354 arm64, hardware virtualised','native_retry_scope':'Full second guest run, not focused CLI-only retry; original first failure retained','vm_initial_final_state':'task m4-macos26 stopped in both attempts','all_input_hashes_stable':True,'receipt_sha256':pins,'scope':'Read-only independent source/binary/receipt reconciliation; no builds, tests, fresh measurements or VM operations. Performance/RSS/universal workspace/physical/M5 gates are unchanged.'}
(A/'050-platform-final.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ['receipt_sha256','native_attempts']},indent=2))
