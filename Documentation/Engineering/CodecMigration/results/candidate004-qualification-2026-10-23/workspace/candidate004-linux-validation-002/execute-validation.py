#!/usr/bin/env python3
"""External, source-frozen validation only; never writes the repository."""
from pathlib import Path
import datetime,hashlib,json,subprocess,time,traceback
ROOT=Path(__file__).resolve().parent
PLAN=json.loads((ROOT/'plan.json').read_text())
SNAP=Path(PLAN['frozen_snapshot']); LIVE=Path('/Users/pushparaj/projects/SwiftJLS')
RECEIPT=Path(PLAN['source_receipt'])
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def now():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def write(name,v):
 p=ROOT/name;p.write_text(json.dumps(v,indent=2,sort_keys=True)+'\n')
 return sha(p)
def files(root):
 result={}
 for name in ['Package.swift','VERSION','Sources','Tests','Examples/WorkspaceProbe','Examples/CopyProbe','Scripts/StorageEvidence']:
  p=root/name
  for q in ([p] if p.is_file() else sorted(p.rglob('*'))):
   if q.is_file() and not any(x in {'.build','.git','__pycache__','.DS_Store'} for x in q.parts):result[str(q.relative_to(root))]=sha(q)
 return result
def verify():
 assert sha(RECEIPT)==PLAN['source_receipt_sha256'],'prepare receipt changed'
 r=json.loads(RECEIPT.read_text())
 for key,glob in [('swiftjls_file_sha256','Sources/SwiftJLS/**/*.swift'),('test_file_sha256','Tests/**/*.swift')]:
  expected=r[key]
  for rel,digest in expected.items():
   assert sha(SNAP/rel)==digest,('snapshot',rel)
   assert sha(LIVE/rel)==digest,('live source bridge',rel)
  assert set(str(q.relative_to(SNAP)) for q in SNAP.glob(glob))==set(expected),('file set',key)
 assert sha(SNAP/'Package.swift')==PLAN['codec_package_sha256']==sha(LIVE/'Package.swift')
 assert sha(Path(r['arm_candidate_dir'])/'Package.swift')==r['package_swift_sha256']
 snap=files(SNAP);live=files(LIVE)
 assert snap==live,('probe/fixture/tool bridge mismatch',[k for k in snap.keys()|live.keys() if snap.get(k)!=live.get(k)])
 tar=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/oracles/libunwind-1.8.3/libunwind-1.8.3.tar.gz')
 assert sha(tar)=='be30d910e67f58d82e753231f1357f326a1a088acf126b21ff77e60aab19b90b'
 return dict(utc=now(),files=snap,file_count=len(snap),source_receipt_sha256=sha(RECEIPT),libunwind_tarball_sha256=sha(tar),live_bridge_equal=True)

def main():
 assert not (ROOT/'execution-start.json').exists(),'Never overwrite an attempted campaign'
 write('execution-start.json',{'utc':now(),'plan_sha256':sha(ROOT/'plan.json'),'driver_sha256':sha(Path(__file__)),'authorisation':'Parent explicitly authorised frozen004 Linux89+20 before any final timings on 2026-10-23.'})
 pre=verify(); write('inputs-before.json',pre)
 docker=['/Users/pushparaj/.local/bin/docker','--context','colima']
 for name,args in [('image',docker+['image','inspect',PLAN['docker_image']]),('containers-before',docker+['ps','--format','{{json .}}'])]:
  c=subprocess.run(args,capture_output=True,text=True);write(name+'.json',{'command':args,'exit_code':c.returncode,'stdout':c.stdout,'stderr':c.stderr});assert c.returncode==0
 statuses=[]
 for mode,dirname in [('workspace','workspace89'),('copy','copy-probe20')]:
  out=ROOT/dirname;out.mkdir(exist_ok=False)
  cmd=PLAN['commands'][mode];t=time.monotonic()
  receipt={'command':cmd,'source_receipt_sha256':sha(RECEIPT),'input_manifest_sha256':sha(ROOT/'inputs-before.json'),'started_utc':now(),'docker_image':PLAN['docker_image'],'scope':'Linux requested-heap/copy evidence only; no Apple RSS or universal-total inference'}
  write(mode+'-running.json',receipt);print(mode+' starting '+now(),flush=True)
  with (ROOT/(mode+'-stdout.log')).open('wb') as stdout,(ROOT/(mode+'-stderr.log')).open('wb') as stderr:
   c=subprocess.run(cmd,stdout=stdout,stderr=stderr)
  receipt.update(exit_code=c.returncode,finished_utc=now(),elapsed_seconds=time.monotonic()-t,stdout_sha256=sha(ROOT/(mode+'-stdout.log')),stderr_sha256=sha(ROOT/(mode+'-stderr.log')))
  binary=out/('WorkspaceProbe' if mode=='workspace' else 'CopyProbe')
  if binary.exists():receipt.update(binary=str(binary),binary_sha256=sha(binary))
  write(mode+'-receipt.json',receipt);statuses.append(receipt)
  print(mode+' exited '+str(c.returncode)+' '+now(),flush=True)
 post=verify();write('inputs-after.json',post)
 assert pre['files']==post['files'],'frozen inputs changed'
 write('execution-complete.json',{'utc':now(),'commands_completed':len(statuses),'all_command_exits_zero':all(s['exit_code']==0 for s in statuses),'input_identity_preserved':True,'receipts':[m+'-receipt.json' for m in ['workspace','copy']],'interpretation':'Collection command completion only; independent reconciliation follows.'})
 return 0 if all(s['exit_code']==0 for s in statuses) else 1
if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as e:
  write('execution-failure.json',{'utc':now(),'error':repr(e),'traceback':traceback.format_exc()});raise
