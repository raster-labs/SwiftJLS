from pathlib import Path
import json,hashlib,subprocess,time,datetime,importlib.util,gzip,sys
sys.dont_write_bytecode=True
R=Path(__file__).resolve().parent
rd=lambda p:json.loads(p.read_text());sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();now=lambda:datetime.datetime.now(datetime.timezone.utc).isoformat()
def load(name,p):
 s=importlib.util.spec_from_file_location(name,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
v=load('guards',R/'execute-validation.py');c=load('classifier',R/'external-classifier/measure-operation.py');runner=load('matrix',R/'external-classifier/run-workspace-profiles.py')
p=rd(R/'plan.json');old=R/'workspace89';fresh=R/'workspace89-corrected-001';fresh.mkdir(exist_ok=False)
before=v.verify();v.write('corrected-inputs-before.json',before)
assert sha(old/'WorkspaceProbe')==rd(R/'workspace-receipt.json')['binary_sha256']
assert sha(R/'external-classifier/measure-operation.py')==rd(R/'external-classifier/self-test.json')['corrected_classifier_sha256']
# Replay all available raw data before collecting a new matrix; preserve old reports.
partial=[]
for f in sorted((old/'profiles').glob('*/operation.json')):
 orig=rd(f);raw=f.parent/'allocations.gz';result=c.replay(gzip.open(raw,'rt'))
 result.update(revision=orig['revision'],profile_sha256=sha(raw));runner.verify_operation_report(f.parent.name,f.parent.name.rsplit('-',1)[1],result,orig['revision'],raw)
 target=fresh/'partial-original-replay'/f.parent.name;target.mkdir(parents=True);(target/'operation.json').write_text(json.dumps(result,indent=2)+'\n')
 partial.append({'case':f.parent.name,'original_report_sha256':sha(f),'raw_profile_sha256':sha(raw),'replayed_report_sha256':sha(target/'operation.json'),'groups_before':orig['groups'],'groups_after':result['groups']})
v.write('partial-original-replay.json',partial)
# CopyProbe is complete and independently reconciled here.
copy=rd(R/'copy-stdout.log');assert copy['self_test'] and len(copy['cases'])==20
pairs={}
for row in copy['cases']:
 assert row['maximum_sample_error']<=row['near'];assert row['observed_source_copy_bytes']==(row['source_capacity'] if row['injected'] else 0)
 key=(row['fixture'],row['interleave']);pairs.setdefault(key,{})[row['injected']]=row
assert len(pairs)==10 and all(set(x)=={False,True} for x in pairs.values())
v.write('copy-reconciliation.json',{'self_test':True,'rows':20,'paired_case_modes':10,'normal_zero_source_copy_rows':10,'injected_exact_source_capacity_rows':10,'all_samples_within_near':True,'raw_stdout_sha256':sha(R/'copy-stdout.log'),'receipt_sha256':sha(R/'copy-receipt.json'),'binary_sha256':sha(R/'copy-probe20/CopyProbe'),'limitation':copy['scope']})
inner='''set -euo pipefail
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends heaptrack python3
swift --version
uname -m
dpkg-query -W heaptrack python3 libunwind8
sha256sum /original/WorkspaceProbe /original/libunwind-183-prefix/lib/libunwind.so.8.2.0 /original/libunwind-183-prefix/lib/libunwind-aarch64.so.8.2.0 /validation/measure-operation.py /validation/run-workspace-profiles.py
LD_LIBRARY_PATH=/original/libunwind-183-prefix/lib ldd /usr/lib/heaptrack/libheaptrack_preload.so | tee /evidence/libunwind-183-ldd.txt
python3 /validation/measure-operation.py --self-test
python3 /validation/run-workspace-profiles.py --self-test
LD_LIBRARY_PATH=/original/libunwind-183-prefix/lib timeout 2400s python3 /validation/run-workspace-profiles.py --binary /original/WorkspaceProbe --output /evidence/profiles --revision "$WORKSPACE_REVISION_ID"
'''
cmd=['/Users/pushparaj/.local/bin/docker','--context','colima','run','--rm','--cpus=4','--mount',f'type=bind,source={p["frozen_snapshot"]},target=/SwiftJLS,readonly','--mount',f'type=bind,source={old},target=/original,readonly','--mount',f'type=bind,source={R/"external-classifier"},target=/validation,readonly','--mount',f'type=bind,source={fresh},target=/evidence','--workdir','/SwiftJLS','--env','WORKSPACE_REVISION_ID=candidate_004:receipt:'+p['source_receipt_sha256'],p['docker_image'],'/bin/bash','-c',inner]
receipt={'command':cmd,'started_utc':now(),'workspace_binary_sha256':sha(old/'WorkspaceProbe'),'corrected_classifier_sha256':sha(R/'external-classifier/measure-operation.py'),'external_runner_sha256':sha(R/'external-classifier/run-workspace-profiles.py'),'source_receipt_sha256':p['source_receipt_sha256'],'input_manifest_sha256':sha(R/'corrected-inputs-before.json'),'prior_partial_attempt_preserved':str(old),'expected_profiles':89,'build_reused':True}
v.write('corrected-running.json',receipt);t=time.monotonic();print('corrected89 starting '+now(),flush=True)
with (fresh/'stdout.log').open('wb') as stdout,(fresh/'stderr.log').open('wb') as stderr:
 s=subprocess.run(cmd,stdout=stdout,stderr=stderr)
receipt.update(exit_code=s.returncode,finished_utc=now(),elapsed_seconds=time.monotonic()-t,stdout_sha256=sha(fresh/'stdout.log'),stderr_sha256=sha(fresh/'stderr.log'))
v.write('corrected-receipt.json',receipt)
after=v.verify();v.write('corrected-inputs-after.json',after);assert before['files']==after['files'];assert sha(old/'WorkspaceProbe')==receipt['workspace_binary_sha256'];assert sha(R/'external-classifier/measure-operation.py')==receipt['corrected_classifier_sha256']
v.write('corrected-collection-complete.json',{'exit_code':s.returncode,'utc':now(),'inputs_and_binary_preserved':True,'interpretation':'Collection completion only; full independent replay/reconciliation follows.'});print('corrected89 exited '+str(s.returncode)+' '+now(),flush=True);raise SystemExit(s.returncode)
