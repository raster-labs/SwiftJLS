from pathlib import Path
import subprocess,json,hashlib,gzip,re
root=Path.cwd();base=root/'Documentation/Engineering/CodecMigration/results';out=base/'milestone4-powered-2026-10-13';out.mkdir(exist_ok=True)
source='36fb97e0a654c0d18802b666df2b07d24cb0637a';artifacts={};uids={}
for n,p in enumerate(sorted((root/'work/m4-apple-final').glob('*-26.0-*.json'))):uids[json.loads(p.read_text())['device']['udid']]=f'<simulator-{n+1}>'
def digest(b):return hashlib.sha256(b).hexdigest()
def save(name,data,compress=False):
 if isinstance(data,Path):data=data.read_bytes()
 if not isinstance(data,(str,bytes)):data=json.dumps(data,indent=2)+'\n'
 if isinstance(data,bytes):data=data.decode()
 data=data.replace(str(root),'<repo>').replace(str(root.parent),'<workspace>').replace(str(Path.home()),'<user>')
 for uid,label in uids.items():data=data.replace(uid,label)
 raw=data.encode();name+= '.gz' if compress else '';p=out/name;p.parent.mkdir(parents=True,exist_ok=True)
 p.write_bytes(gzip.compress(raw,mtime=0) if compress else raw)
 artifacts[name]=dict(sha256=digest(p.read_bytes()),bytes=p.stat().st_size)
def tree(prefix,folder,patterns):
 for pattern in patterns:
  for p in sorted(folder.glob(pattern)):
   if p.is_file():save(prefix+'/'+str(p.relative_to(folder)),p, p.suffix in ['.log','.jsonl','.xml'] or p.stat().st_size>100000)
for label,folder in [('final-rgb','m4-powered-final-2026-10-13'),('final-scalar','m4-powered-final-scalar-2026-10-13'),('final-near','m4-powered-final-near-2026-10-13'),('initial','m4-powered-2026-10-13'),('initial-selected','m4-powered-selected-2026-10-13'),('validation-experiment','m4-validation-optimisation'),('packed-experiment','m4-packed-optimisation')]:
 tree(label,root/'work'/folder,['*.json','*.jsonl','*.log','*.py','scalar/*','colour/*'])
tree('tests',root/'work/m4-packed-tests',['*.json','*.xml','*.log','cli/report.json'])
tree('apple',root/'work/m4-apple-final',['*.json','*.log','*/*.log'])
tree('resources',root/'work/m4-resource26-final',['*.json'])
for p in sorted((root/'work/m4-current-ci-artifacts').rglob('*')):
 if p.is_file():
  name='hosted/'+str(p.relative_to(root/'work/m4-current-ci-artifacts'))
  if p.suffix=='.gz':
   q=out/name;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(p.read_bytes());artifacts[name]=dict(sha256=digest(q.read_bytes()),bytes=q.stat().st_size)
  else:save(name,p,p.stat().st_size>100000)
tree('header-diagnostic',root/'work/m4-header-sizes',['*.json'])
tree('cpu-diagnostic',root/'work/m4-final-cpu-profile',['*.json','*.txt','*.stdout','*.stderr'])
for name in ['check-m4-header-sizes.py','profile-m4-final.py','report-m4-performance.py','run-m4-powered.py','run-m4-powered-selected.py','run-m4-powered-final.py','run-m4-powered-final-scalar.py','run-m4-powered-final-near.py','compare-m4-validation-opt.py','compare-m4-packed-opt.py','summarise-m4-powered.py','summarise-m4-final.py','run-m4-packed-tests.py','m4-apple-final-build.py','run-m4-final-simulators.py','run-m4-final-resource26.py','m4-final-runtime26.log','m4-final-resource26.log','m4-final-colour-cases.json','m4-final-near-cases.json','m4-ci-36fb97e.json','m4-pr-status-36fb97e.json','m4-validation-only-ComponentSamples.swift','m4-hosted-merge-trees.jsonl','m4-macos26-ci.log','m4-doc-checks-f09b333.json','m4-doc-pr-f09b333.json','m4-final-fuzz.log']:
 save('reproduction/'+name,root/'work'/name,name.endswith('.log'))
for name in ['Consumer.swift','compare.py','test-runner.py']:
 p=root/'Scripts/Benchmark'/name
 if p.exists():save('reproduction/final-'+name,p)
 for rev in ['1b4964d']:
  r=subprocess.run(['git','show',rev+':Scripts/Benchmark/'+name],capture_output=True)
  if r.returncode==0:save('reproduction/'+rev+'-'+name,r.stdout)
save('reproduction/package-m4-powered.py',Path(__file__))
for label in ['predecessor','baseline','successor']:
 save('reproduction/'+label+'-Package.swift',root/'work/m4-benchmark'/label/'Package.swift')
checks=json.loads((root/'work/m4-ci-36fb97e.json').read_text());assert len(checks)==17 and all(c['state']=='SUCCESS' for c in checks)
tests=json.loads((root/'work/m4-packed-tests/results.json').read_text());assert all(t['exit_code']==0 for t in tests)
assert all(t['declarations']==82 and t['failures']==0 and t['skipped']==0 for t in tests if 'declarations'in t)
runtimes=[]
for p in sorted((root/'work/m4-apple-final').glob('*-26.0-*.json')):
 d=json.loads(p.read_text());assert all(c['exit_code']==0 for c in d['commands']);runtimes.append(dict(device=d['device']['name'],runtime=d['runtime']['version'],build=d['runtime']['buildversion'],evidence='apple/'+p.name))
assert len(runtimes)==5
resources=json.loads((root/'work/m4-resource26-final/commands.json').read_text());assert all(c['exit_code']==0 for c in resources)
workloads=[c for c in resources if c['label'].endswith('resource workload')];assert len(workloads)==4
for c in workloads:
 rows=json.loads(c['stdout']);assert sum(r['frames'] for r in rows)==32
 assert all(r['ownedPixelAllocations']==r['frames'] and r['suppliedPixelAllocations']==0 and r['reportedCopyBytes']==0 for r in rows)
analysis=json.loads((root/'work/m4-powered-final-2026-10-13/combined-analysis.json').read_text());assert analysis['scalar']['complete_cases']==24 and analysis['colour']['complete_cases']==39
for f in ['m4-powered-final-2026-10-13','m4-powered-final-scalar-2026-10-13','m4-powered-final-near-2026-10-13']:
 assert all(c['exit_code']==0 for c in json.loads((root/'work'/f/'commands.json').read_text()))
 for p in (root/'work'/f).glob('*/environment.json'):
  e=json.loads(p.read_text());assert e['successor_sha']['output'].strip()==source
for p,h in json.loads((root/'work/m4-packed-optimisation/environment.json').read_text())['candidate_source_sha256'].items():assert digest((root/p).read_bytes())==h
fuzz=[]
for p in sorted((root/'work/m4-final-fuzz-artifacts').glob('*/campaign-result.json')):
 d=json.loads(p.read_text());assert d['exit_code']==0 and d['failure'] is None
 final=json.loads((p.parent/'campaign.jsonl').read_text().splitlines()[-1])
 assert final['complete'] and final['seconds']>=3600 and final['seedCount']==981
 assert (p.parent/'campaign-stderr.log').stat().st_size==0
 save('fuzz/'+p.parent.name+'/'+p.name,p)
 fuzz.append(dict(entry=final['entry'],result=d,final=final,last_input_sha256=digest((p.parent/'last-input.jls').read_bytes())))
 for n in ['campaign-stderr.log','campaign.jsonl']:
  if (p.parent/n).exists():save('fuzz/'+p.parent.name+'/'+n,p.parent/n,True)
if (root/'work/m4-final-fuzz-completed.json').exists():
 run=json.loads((root/'work/m4-final-fuzz-completed.json').read_text());assert run['headSha']==source and run['conclusion']=='success' and len(fuzz)==3
 save('fuzz/run.json',root/'work/m4-final-fuzz-completed.json')
header=json.loads((root/'work/m4-header-sizes/summary.json').read_text());assert len(header['cases'])==12 and all(c['entropy_identical'] for c in header['cases'])
report=dict(date='2026-10-13',source_commit=source,production_source_tree=subprocess.check_output(['git','rev-parse',source+':Sources'],text=True).strip(),test_tree=subprocess.check_output(['git','rev-parse',source+':Tests'],text=True).strip(),predecessor_sha='15aa75164145414f3d5ffb801401c52d40cc5bcc',focused_baseline_sha='1b4964dc0205ac9a529e07df9742878f40853e29',suite_policy='0.10.0',version='1.1.0-dev.2',tests=tests,hosted_checks=checks,runtimes=runtimes,non_watch_concurrent_workloads=4,benchmark_cases=dict(scalar=24,colour=39),resource_profile='successor-workspace-1GiB-memory-2GiB-v1',mutation_results=fuzz,artifacts=artifacts,qualification=dict(milestone4='incomplete',milestone5='deferred',performance='Powered monitored workstation evidence collected; residual regressions are not waived; no isolated-laboratory claim.',complete_workspace_accounting=False,physical_devices='unavailable and unexecuted',physical_watch='excluded and unexecuted',native_macos_26='not established by macOS 27.0.1 host'),limitations=['Initial and intermediate experiments retain their own source/binary/consumer hashes; do not merge their timings with the final runs.','Incomplete original colour case and failed default-limit largest RGB case are retained but excluded from complete-case counts.','RGB coverage is the owner-selected representative subset, not all 144 cases.','Thirty-second condition samples cannot exclude all transient background load. Initial final-RGB load average was elevated after compilation; recorded CPU idle and subsequent load are disclosed.','Peak process RSS, codec reports and whole-process heap peaks do not establish complete per-operation algorithm workspace.','Archived local paths and simulator identifiers use labelled placeholders. Artifact hashes describe archived bytes, not original unredacted files.'])
(base/'milestone4-powered-2026-10-13.json').write_text(json.dumps(report,indent=2)+'\n')
print('Archived',len(artifacts),'artifacts;',sum(x['bytes'] for x in artifacts.values()),'bytes; fuzz results',len(fuzz))
