#!/usr/bin/env python3
"""Reconcile retained candidate005 platform results; never builds or runs tests."""
import datetime, importlib.util, json, os, pathlib, subprocess, xml.etree.ElementTree as ET
spec=importlib.util.spec_from_file_location('qualification_source',pathlib.Path(__file__).with_name('qualification-source.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q)
p=q.OUT; identity=q.source(); pins=q.PINS
load=lambda rel:json.loads((p/rel).read_text())
assert identity==load('qualification-source.json')
commands=load('platform-commands.json');assert len(commands)==7 and all(x['exit_code']==0 for x in commands)
for x in commands: assert q.sha(p/(x['label']+'.log'))==x['log_sha256']
build=load('apple-value/build-results.json');assert build and all(x['exit_code']==0 for x in build)
for x in build: assert q.sha(p/x['log'])==x['log_sha256']
environment=load('apple-value/environment.json');assert environment['source_manifest_sha256']==identity['source_manifest_sha256']
assert len(environment['sdks'])==5 and environment['sdks']['watchos']['triple']=='arm64_32-apple-watchos26.0'
binary=load('apple-value/binary-manifest.json')
runtime=[]
for f in sorted((p/'apple-value').glob('*.json')):
 r=json.loads(f.read_text())
 if not isinstance(r,dict) or 'runtime' not in r:continue
 assert r['runtime']['version']=='26.0' and r['source_manifest_sha256']==identity['source_manifest_sha256']
 assert all(c['exit_code']==0 for c in r['commands'])
 spawn=[c for c in r['commands'] if len(c['command'])>2 and c['command'][2]=='spawn'];assert len(spawn)==1
 assert 'Combined legacy mapping/HP runtime passed.' in spawn[0]['stdout']
 assert r['consumer_binary_sha256']==binary[r['sdk']]['consumer_binary_sha256']
 assert r['library_dylib_sha256']==binary[r['sdk']]['library_dylib_sha256']
 runtime.append(dict(receipt=f.name,device=r['device']['name'],udid=r['device']['udid'],runtime=r['runtime']['version'],runtime_build=r['runtime']['buildversion']))
assert len(runtime)==5
resource=load('resource26-value/summary.json');assert resource['source_manifest_sha256']==identity['source_manifest_sha256'] and len(resource['workloads'])==4
assert all(x['exit_code']==0 for x in load('resource26-value/commands.json'))
for w in resource['workloads']:
 assert w['runtime']=='26.0' and w['frames']==32 and len(w['rows'])==4
 assert all(r['ownedPixelAllocations']==r['frames'] and r['suppliedPixelAllocations']==0 and r['reportedCopyBytes']==0 for r in w['rows'])
manifest=load('native-payload/manifest.json');native=load('native-results/results.json')
assert native['success'] and native['exact_26_0_native_arm64'] and native['source_id']=='candidate_005'
assert native['source_manifest_sha256']==identity['source_manifest_sha256']==manifest['source_manifest_sha256']
assert native['guest_verified_bundle_executable_sha256']==manifest['bundle_executable_sha256']
assert native['guest_verified_cli_binary_sha256']==manifest['cli_binary_sha256']
assert native['guest_verified_consumer_binary_sha256']==manifest['consumer_binary_sha256']
assert len(native['commands'])==11 and all(x['exit_code']==0 for x in native['commands'])
assert 'Combined legacy mapping/HP runtime passed.' in (p/'native-results/consumer.stdout').read_text()
tests={}
for mode in ['release','debug','asan','tsan']:
 rel='native-results/unit.xml' if mode=='release' else f'native-results/unit-{mode}.xml'
 cases=list(ET.parse(p/rel).getroot().iter('testcase'))
 groups={x.attrib.get('classname') for x in cases}
 assert len(cases)==157 and len(groups)==29
 assert not any(x.find(y) is not None for x in cases for y in ['failure','error','skipped'])
 rec=native['tests'] if mode=='release' else native['extra_tests'][mode]
 assert rec['declarations']==157 and rec['classname_suites']==29 and rec['failures']==0 and rec['skipped']==0 and rec['xml_sha256']==q.sha(p/rel)
 tests[mode]=dict(declarations=157,xunit_classnames=29,failures=0,errors=0,skipped=0,xml_sha256=q.sha(p/rel))
assert native['source_named_suite_declarations']==28
assert native['resource_stress_summary']==dict(row_count=4,total_frames=32,owned_equal_frames=True,zero_supplied=True,zero_copy_bytes=True)
assert native['cli_summary']['payload_cases']==73 and native['cli_summary']['process_checks']==103 and native['cli_summary']['process_status']=='passed'
env=dict(os.environ,DEVELOPER_DIR='/Applications/Xcode.app/Contents/Developer')
post=json.loads(subprocess.check_output(['/usr/bin/xcrun','simctl','list','devices','available','--json'],env=env,text=True))['devices']
initial=load('execution-release-001.json')['simulator_inventory']['devices']
flatten=lambda d:{v['udid']:v['state'] for rows in d.values() for v in rows}
a,b=flatten(initial),flatten(post);assert all(b.get(k)==v for k,v in a.items())
assert b['9021546C-CD90-4663-A01B-B4E92851C3DF']=='Shutdown'
q.write(p/'simulator-restore.json',dict(initial_states=a,final_states=b,restored=True,benchmark_paused_iPhone_remains_shutdown=True))
driver=load('native-driver-commands.json');assert driver[-1]['label']=='post-run stopped VM inventory'
lines=[line.split() for line in driver[-1]['stdout'].splitlines() if 'm4-macos26' in line.split()]
assert len(lines)==1 and lines[0][-1]=='stopped'
q.write(p/'apple-results-summary.json',dict(source_manifest_sha256=identity['source_manifest_sha256'],sdk_builds=environment['sdks'],simulator_consumers=runtime,resource_platforms=4,resource_frames_each=32,simulator_states_restored=True))
artifacts=['pins.json','qualification-source.json','platform-commands.json','apple-results-summary.json','apple-value/build-results.json','apple-value/environment.json','apple-value/binary-manifest.json','resource26-value/commands.json','resource26-value/summary.json','consumer-builds.json','native-payload/manifest.json','native-payload/run-native.py','native-results/results.json','native-driver-commands.json','simulator-restore.json','execution-release-001.json','driver-correction-001.json','driver-correction-002.json','apple-attempt-1/platform-commands.json','apple-attempt-1/apple-build-value.log']
result=dict(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='passed_after_retained_driver_admission_correction',source_id='candidate_005',source_commit=None,base_head=pins['base_head'],source_receipt_sha256=pins['source_receipt_sha256'],source_manifest_sha256=identity['source_manifest_sha256'],library_files=39,test_swift_files_including_fixture_generators=32,source_named_suite_declarations=28,apple=dict(sdk_builds=environment['sdks'],simulator_consumers=5,exact_runtime='26.0',resource_platforms=4,resource_frames_each=32,simulator_states_restored=True),native=dict(scope=native['scope'],os=native['os'],architecture=native['architecture'],tests=tests,runtime_consumer='passed',resource_rows=4,resource_frames=32,payload_cli_checks=73,process_cli_checks=103,cli_binary_sha256=manifest['cli_binary_sha256'],vm_initial_final_state='stopped'),host_reuse=dict(tests=pins['host_receipt'],tests_sha256=pins['host_receipt_sha256'],host_cli_receipts=pins['host_cli_receipts'],no_host_test_or_cli_rerun=True),retained_driver_failures=[dict(receipt='apple-attempt-1/platform-commands.json',reason='Stale hardcoded38-source count rejected the39-file frozen inventory before any build/runtime command; corrected to pinned inventory length.')],preexecution_corrections=[dict(receipt='driver-correction-002.json',reason='Renamed per-file SHA loop variable to preserve157 expected test count; no native attempt failed.')],artifact_sha256={f:q.sha(p/f) for f in artifacts},driver_final_sha256={f.name:q.sha(f) for f in p.glob('*.py')},limits=['SDK27.x targeting26.0 and actual26.0 simulator/guest execution are distinct evidence.','Native guest execution is hardware-virtualised, not physical-device qualification.','Physical devices, performance acceptance, universal total workspace and milestone5 are not established by these checks.','Shared services were not stopped; the benchmark-paused iPhone remains shut down for root to restore after all timings.'])
q.unchanged(identity);q.write(p/'platform-results.json',result)
print(json.dumps({k:result[k] for k in ['status','source_id','source_manifest_sha256','library_files','source_named_suite_declarations']},indent=2))
