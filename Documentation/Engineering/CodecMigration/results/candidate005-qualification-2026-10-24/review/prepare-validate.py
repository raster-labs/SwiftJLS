import datetime,hashlib,json,os,pathlib,re,shutil,subprocess,sys,time,xml.etree.ElementTree as ET
ROOT=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024')
REPO=pathlib.Path('/Users/pushparaj/projects/SwiftJLS')
OLD=pathlib.Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/snapshots/candidate_004')
OUT=ROOT/sys.argv[1];OUT.mkdir()
ENV=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools')
sha=lambda p:hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
pins={str(p.relative_to(REPO)):sha(p) for top in ['Sources','Tests','Scripts','Examples'] for p in sorted((REPO/top).rglob('*')) if p.is_file() and not any(x in p.parts for x in ['.build','.swiftpm'])}
pins.update({x:sha(REPO/x) for x in ['Package.swift','VERSION']})
(OUT/'all-source-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
def verify():
 for n,h in pins.items():
  if sha(REPO/n)!=h:raise RuntimeError('Source changed during validation: '+n)
def run(label,cmd,cwd=REPO):
 verify();t=time.time();ev={'label':label,'command':cmd,'cwd':str(cwd),'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'developer_dir':ENV['DEVELOPER_DIR']}
 with (OUT/(label+'.stdout')).open('w') as o,(OUT/(label+'.stderr')).open('w') as e:p=subprocess.run(cmd,cwd=cwd,env=ENV,stdout=o,stderr=e)
 ev.update(exit_code=p.returncode,elapsed_seconds=time.time()-t,stdout_sha256=sha(OUT/(label+'.stdout')),stderr_sha256=sha(OUT/(label+'.stderr')))
 with (OUT/'events.jsonl').open('a') as f:f.write(json.dumps(ev)+'\n')
 print(label,p.returncode,round(ev['elapsed_seconds'],2),flush=True);verify()
 if p.returncode:raise RuntimeError(label+' failed; see preserved logs')
 return ev
try:
 expected=sum(len(re.findall(r'@Test\b',(REPO/n).read_text())) for n in pins if n.startswith('Tests/SwiftJLSTests/') and n.endswith('.swift'))
 suites=sum(len(re.findall(r'@Suite\b',(REPO/n).read_text())) for n in pins if n.startswith('Tests/SwiftJLSTests/') and n.endswith('.swift'))
 validations=[]
 for label in ['release','debug','asan','tsan']:
  cmd=['swift','test','--build-system','swiftbuild','--jobs','4','--scratch-path',str(OUT/(label+'-build')),'--disable-xctest','--xunit-output',str(OUT/(label+'.xml')),'-Xswiftc','-load-plugin-library','-Xswiftc','/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib']
  cmd+=['-c','release' if label=='release' else 'debug']
  if label in ['asan','tsan']:cmd+=['--sanitize','address' if label=='asan' else 'thread']
  ev=run(label,cmd);x=ET.parse(OUT/(label+'.xml')).getroot();ev.update(tests=len(list(x.iter('testcase'))),failures=len(list(x.iter('failure'))),errors=len(list(x.iter('error'))),skipped=len(list(x.iter('skipped'))),xml_sha256=sha(OUT/(label+'.xml')))
  assert ev['tests']==expected and not(ev['failures'] or ev['errors'] or ev['skipped']),ev
  validations.append(ev);(OUT/'validation.json').write_text(json.dumps(validations,indent=2)+'\n')
 arm=OUT/'arm_candidate';arm.mkdir();shutil.copy2(OLD/'arm_candidate/Package.swift',arm/'Package.swift');shutil.copytree(REPO/'Sources/SwiftJLS',arm/'Sources/SwiftJLS');shutil.copytree(OLD/'arm_candidate/Sources/MemDiagRelief',arm/'Sources/MemDiagRelief');(arm/'Sources/Benchmark').mkdir();shutil.copy2(REPO/'Scripts/Benchmark/Consumer.swift',arm/'Sources/Benchmark/main.swift')
 assert sha(arm/'Package.swift')=='b8c00c41dda983f6cee24c45f3e352ebde71c0f25b42abd379a431f1a556394b'
 assert sha(arm/'Sources/Benchmark/main.swift')=='27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'
 run('benchmark-build',['swift','build','-c','release','--jobs','4'],arm)
 bp=pathlib.Path(subprocess.check_output(['swift','build','-c','release','--show-bin-path'],cwd=arm,env=ENV,text=True).strip());bins=OUT/'binaries';bins.mkdir();binary_records={}
 for n in ['Benchmark','MemDiagRelief']:
  p=bins/n;shutil.copy2(bp/n,p);binary_records[n]={'path':str(p),'sha256':sha(p)}
 receipt={'base_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),'candidate':'candidate_005','swiftjls_file_sha256':{n:h for n,h in pins.items() if n.startswith('Sources/SwiftJLS/')},'test_file_sha256':{n:h for n,h in pins.items() if n.startswith('Tests/SwiftJLSTests/') and n.endswith('.swift')},'all_source_pins_sha256':sha(OUT/'all-source-pins.json'),'consumer_sha256':sha(REPO/'Scripts/Benchmark/Consumer.swift'),'declaration_counts_from_source':{'test_declarations':expected,'suite_declarations':suites},'validation':validations,'binaries':binary_records}
 verify();(OUT/'prepare-and-validate-receipt.json').write_text(json.dumps(receipt,indent=2)+'\n');print('COMPLETE',expected,suites,flush=True)
except BaseException as e:
 (OUT/'failure.json').write_text(json.dumps({'error':str(e),'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()},indent=2)+'\n');raise
