"""Existing two-window host preflight. Observation/admission only, never starts benchmarks."""
import argparse,datetime,json,os,pathlib
import campaign_identity as identity
from diag72_runner import measure_10s_instantaneous_window,self_test_host_guards,conditions
p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=pathlib.Path);a=p.parse_args();identity.require(not a.output.exists(),'Fresh preflight filename required')
env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools');proof=identity.verify(env);result={'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'source_guards':proof,'host_guard_self_test':self_test_host_guards(),'host_scope':'Shared services running; no idleness claim. CPU windows are survivor-process CPU deltas and miss processes that exit between observations. Root reviews conditions before authorising collection.','windows':[],'campaign_freeze_sha256':identity.sha(identity.HERE/'campaign-freeze.json')}
try:
 for i in range(2):result['windows'].append(measure_10s_instantaneous_window(i,env,10.0))
 result.update(status='automated_preflight_passed',root_acceptance='pending_independent_review',end_source_guards=identity.verify(env))
except BaseException as e:
 result.update(status='preflight_failed',error=repr(e),conditions=conditions(env));raise
finally:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(a.output,identity.sha(a.output))
