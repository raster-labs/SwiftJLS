import copy,hashlib,importlib.util,json,pathlib,subprocess,sys
from unittest.mock import patch
A=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024');P=A/'campaigns005-final-services'
sys.path.insert(0,str(P));import diag72_runner as h
results=[]
for name,e in h.PERSISTENT_SERVICE_BY_NAME.items():
 identity=dict(e['identity'],status='running');identity['name']='/'+name
 def row():return {'ID':e['identity']['id'][:12],'Names':name,'Image':e['identity']['image'],'Command':' '.join([e['identity']['path'],*e['identity']['args']]),'Status':'Up'}
 cases=[('exact',subprocess.CompletedProcess([],0,json.dumps(identity),''),True),('inspect_exit_failure',subprocess.CompletedProcess([],1,'','not retained'),False),('malformed_json',subprocess.CompletedProcess([],0,'{',''),False),('multiple_json_objects',subprocess.CompletedProcess([],0,json.dumps(identity)+'\n'+json.dumps(identity),''),False),('missing_identity',subprocess.CompletedProcess([],0,'{}',''),False),('timeout',subprocess.TimeoutExpired('selected-inspect',10),False)]
 for label,response,want in cases:
  r=row()
  with patch.object(h.subprocess,'run',side_effect=response if isinstance(response,Exception) else None,return_value=None if isinstance(response,Exception) else response) as mocked:
   receipt=h.inspect_persistent_services([r],{})
  assert mocked.call_count==1
  cmd=mocked.call_args.args[0];assert cmd[:4]==['docker','container','inspect','--format'] and cmd[-1]==r['ID']
  assert '.Env' not in cmd[4] and 'working_dir' not in cmd[4] and 'config_files' not in cmd[4]
  got=not h.evaluate_colima_containers([r]);assert got==want,(name,label,got)
  assert receipt['inspection_seconds']>=0 and receipt['started_utc']<=receipt['completed_utc']
  results.append({'name':name,'case':label,'admitted':got,'matched_expectation':True})
# Unknown services never receive inspect-based exception; the guard rejects them.
unknown={'ID':'a'*12,'Names':'dev_php83','Image':'dev-stack-php83','Command':'php-fpm','Status':'Up'}
with patch.object(h.subprocess,'run',side_effect=AssertionError('Unexpected live subprocess')):
 result=h.inspect_persistent_services([unknown],{})
assert not result['services'] and h.evaluate_colima_containers([unknown])
controls=h.self_test_host_guards()
report={'passed':True,'live_commands_run':False,'mocked_inspection_controls':results,'unknown_name_rejected_without_inspection':True,'host_guard_controls':controls,'package_freeze_sha256':hashlib.sha256((P/'campaign-freeze.json').read_bytes()).hexdigest(),'helper_sha256':hashlib.sha256((P/'diag72_runner.py').read_bytes()).hexdigest()}
(A/'016-shared-service-admission/synthetic-inspection-controls.json').write_text(json.dumps(report,indent=2)+'\n')
print('PASS 18 mocked selected-inspection controls + unknown service + all original and exact-identity host controls')
