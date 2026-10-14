#!/usr/bin/env python3
"""Archive small current-source validation records; exclude workspace and timing data."""
from pathlib import Path
import datetime, hashlib, json, shutil, subprocess
root=Path.cwd()
scratch=root/'work/m4-closeout-2026-10-14'
base=root/'Documentation/Engineering/CodecMigration/results'
out=base/'milestone4-closeout-2026-10-14'
manifest_path=base/'milestone4-closeout-2026-10-14.json'
checkpoint='059d97a786dd16bd554c92c126da6da99c9ec308'
def git(*args): return subprocess.check_output(['git',*args],text=True).strip()
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
assert git('rev-parse','HEAD')==checkpoint
assert not git('diff','--name-only',checkpoint,'--','Sources','Tests')
files={}
def copy(src,relative):
 dst=out/relative
 dst.parent.mkdir(parents=True,exist_ok=True)
 shutil.copyfile(src,dst)
 files[str(relative)]={'bytes':dst.stat().st_size,'sha256':sha(dst),'source':str(src.relative_to(root))}
for name in ['tests/results.json','qualify.log','value-qualification-commands.json','cli-payload-value.json','cli-payload-value.log','cli-process-value.log','cli-process-value/report.json','cli-process-value/manual-plain.txt','cli-process-value/manual-rendered.txt','cli-process-value/manual.1','resource26-value/commands.json']:
 copy(scratch/name,name)
for p in sorted((scratch/'tests').glob('*')):
 if p.suffix in {'.log','.xml'}: copy(p,p.relative_to(scratch))
for name in ['apple-build-value.log','apple-runtime-value.log','apple-resource-value.log','native-AppleRuntimeConsumer-value.log','native-ResourceStress-value.log','benchmark-value.log','tests-driver.log']:
 copy(scratch/name,name)
for p in sorted((scratch/'apple-value').rglob('*')):
 if p.is_file() and (p.suffix=='.log' or (p.suffix=='.json' and '.abi.' not in p.name)):
  copy(p,p.relative_to(scratch))
native=read(scratch/'native-results/results.json')
assert native['source']==checkpoint and native['success'] and native['exact_26_0_native_arm64']
for p in sorted((scratch/'native-results').rglob('*')):
 if p.is_file():
  assert p.stat().st_size<200000,'Unexpected large native file'
  copy(p,p.relative_to(scratch))
for name in ['run-tests.py','qualify.py','apple-build-value.py','apple-runtime-value.py','apple-resource-value.py','prepare-native.py','archive-validation.py']:
 copy(scratch/name,'reproduction/'+name)
copy(scratch/'native-payload/run-native.py','reproduction/run-native.py')
# Native payload includes repeated fixture trees and archived historical documentation.
# Retain the original manifest hash and the executable/framework hashes only.
payload_manifest=read(scratch/'native-payload/manifest.json')
selected={k:v for k,v in payload_manifest['files'].items() if not k.startswith('repo/') and '/Resources/' not in k and '/_CodeSignature/' not in k}
provenance={
 'source_commit':checkpoint,
 'sources_tree':git('rev-parse',checkpoint+':Sources'),
 'tests_tree':git('rev-parse',checkpoint+':Tests'),
 'native_payload_manifest_sha256':sha(scratch/'native-payload/manifest.json'),
 'native_payload_manifest_filter':'Executable and framework metadata hashes; repository archive and repeated test fixture resources excluded. Git Tests tree identifies fixture contents.',
 'native_payload_files':selected,
 'source_test_and_contract_files':{},
}
paths=git('ls-tree','-r','--name-only',checkpoint,'--','Sources','Tests','Package.swift','VERSION','Documentation/SUITE_POLICY.md','Documentation/COMMON_API.md','Documentation/MEMORY_CONTRACT.md','Documentation/CLI_CONTRACT.md','Documentation/PLATFORMS.md','Documentation/PERFORMANCE.md','Documentation/TESTING.md').splitlines()
for name in paths:
 if name.startswith('Tests/') and not name.endswith('.swift'): continue
 provenance['source_test_and_contract_files'][name]={'git_blob':git('rev-parse',checkpoint+':'+name),'sha256':sha(root/name)}
(out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
files['provenance.json']={'bytes':(out/'provenance.json').stat().st_size,'sha256':sha(out/'provenance.json'),'source':'Generated from committed source/test trees and native payload manifest'}
tests=read(scratch/'tests/results.json')
assert all(t['declarations']==87 and t['failures']==0 and t['skipped']==0 and t['exit_code']==0 for t in tests)
payload=read(scratch/'cli-payload-value.json')
process=read(scratch/'cli-process-value/report.json')
special_expected={'deadline blocked pipe':5,'cancel blocked pipe':130,'closed binary output':6}
assert len(payload)==73 and all(x['exit']==(x['expected'] if 'expected' in x else special_expected[x['condition']]) for x in payload)
assert process['checks']==103 and process['status']=='passed'
simulators=sorted((scratch/'apple-value').glob('*-26.0-*.json'))
assert len(simulators)==5
for f in simulators:
 d=read(f)
 assert d['runtime']['version']=='26.0' and all(c['exit_code']==0 for c in d['commands'])
resources=read(scratch/'resource26-value/commands.json')
assert all(r['exit_code']==0 for r in resources)
workloads=[r for r in resources if r['label'].endswith('resource workload')]
assert len(workloads)==4
for r in workloads:
 data=json.loads(r['stdout'])
 assert sum(x['frames'] for x in data)==32
 assert all(x['reportedCopyBytes']==0 and x['suppliedPixelAllocations']==0 for x in data)
assert sum(x['frames'] for x in json.loads((scratch/'native-results/resources.stdout').read_text()))==32
manifest={
 'recorded_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'record_status':'validation archived; controlled performance and workspace evidence pending integration',
 'production_checkpoint':checkpoint,
 'sources_tree':provenance['sources_tree'],'tests_tree':provenance['tests_tree'],
 'predecessor':'15aa75164145414f3d5ffb801401c52d40cc5bcc',
 'archive_directory':str(out.relative_to(base)),
 'native_vm_image':'ghcr.io/cirruslabs/macos-tahoe-base@sha256:6b01ed7bb644831fc3b5fdb297c8541bf7f032633d4ac5ac9b04affa163b3772',
 'validation':{
  'local_tests':{t['label']:{k:t[k] for k in ['declarations','failures','skipped','exit_code','seconds']} for t in tests},
  'cli':{'payload_checks':73,'process_checks':103,'status':'passed'},
  'apple_builds':{'sdk':'Xcode 27 Apple SDKs','deployment_target':'26.0','evidence':'apple-value/build-results.json','scope':'Four simulator libraries and independent consumers; watchOS arm64_32 compile probe.'},
  'apple_simulator_runtime':{'version':'26.0','platforms':['iOS iPhone','iOS iPad','tvOS','visionOS','watchOS'],'evidence':'apple-value/*-26.0-*.json'},
  'apple_simulator_resources':{'evidence':'resource26-value/commands.json','scope':'Four non-Watch profiles with 32 frames per profile; zero reported copy bytes and no supplied-destination pixel allocations.'},
  'native_execution':{k:v for k,v in native.items() if k!='commands'},
 },
 'files':dict(sorted(files.items())),
 'pending_integration':['Controlled paired performance campaign and case analysis.','Workspace accounting report and compact evidence pointer from workspace audit.'],
 'limitations':['Physical Watch and representative physical iPhone/iPad testing remain pending by owner direction.','Milestone 5 remains deferred.','CI process verification and merge belong to the owner; this manifest does not assert GitHub check outcomes.','Native macOS 26.0 evidence uses hardware-virtualised arm64 execution, not physical Apple device testing.','This archive does not yet establish performance acceptance or full algorithm workspace completion.'],
}
manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
for rel,entry in files.items(): assert sha(out/rel)==entry['sha256']
print(json.dumps({'archive':str(out.relative_to(root)),'manifest':str(manifest_path.relative_to(root)),'files':len(files),'bytes':sum(x['bytes'] for x in files.values()),'native_success':native['success']}))
