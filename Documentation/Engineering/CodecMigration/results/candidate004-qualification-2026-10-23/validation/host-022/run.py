import json, pathlib, hashlib, os, subprocess, time, re, xml.etree.ElementTree as ET
root=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023')
out=root/'022-candidate004-host-validation'
repo=pathlib.Path('/Users/pushparaj/projects/SwiftJLS')
snap=pathlib.Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/snapshots/candidate_004')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
receipt_path=snap/'prepare-and-validate-receipt.json'
r=json.loads(receipt_path.read_text()); receipt_sha=sha(receipt_path)
pins=r['swiftjls_file_sha256']|r['test_file_sha256']
expected=r['declaration_counts_from_source']['test_declarations']
def verify():
 assert sha(receipt_path)==receipt_sha
 for name,h in pins.items():
  assert sha(repo/name)==h and sha(snap/'SwiftJLS'/name)==h,name
 for name,h in r['swiftjls_file_sha256'].items():assert sha(snap/'arm_candidate'/name)==h,name
verify()
old=json.loads((root/'007-host-validation/summary.json').read_text())
rows=[]
env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools')
for v in old['validation']:
 label=v['label'];cmd=[x.replace('candidate_003','candidate_004').replace('007-host-validation','022-candidate004-host-validation') for x in v['command']]
 verify();t=time.time()
 with (out/'events.jsonl').open('a') as f:f.write(json.dumps({'event':'start','label':label,'command':cmd,'cwd':str(repo),'developer_dir':env['DEVELOPER_DIR'],'epoch':t})+'\n')
 p=subprocess.run(cmd,cwd=repo,env=env,capture_output=True,text=True)
 log=out/(label+'.log');log.write_text(p.stdout+'\n'+p.stderr)
 row={'label':label,'command':cmd,'exit_code':p.returncode,'elapsed_seconds':time.time()-t,'log_sha256':sha(log),'reused_compilation':'--skip-build' in cmd}
 xml=out/(label+'.xml')
 if xml.exists():
  x=ET.parse(xml).getroot();ts=list(x.iter('testcase'))
  row.update(testcases=len(ts),failures=len(list(x.iter('failure'))),errors=len(list(x.iter('error'))),skipped=len(list(x.iter('skipped'))),xml_sha256=sha(xml),classes=sorted({t.attrib.get('classname','') for t in ts}))
 rows.append(row)
 with (out/'events.jsonl').open('a') as f:f.write(json.dumps({'event':'end',**row})+'\n')
 (out/'summary.json').write_text(json.dumps({'base_head':r['base_head'],'candidate':'candidate_004','prepare_receipt_sha256':receipt_sha,'source_pins':pins,'declarations':r['declaration_counts_from_source'],'validation':rows},indent=2)+'\n')
 print(label,row.get('testcases'),p.returncode,flush=True)
 assert p.returncode==0 and row.get('testcases')==expected and row.get('failures')==row.get('errors')==row.get('skipped')==0,row
 verify()
print('COMPLETE',expected,flush=True)
