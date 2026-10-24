#!/usr/bin/env python3
"""Run only after root explicitly releases final disposition/restoration for full staging."""
from pathlib import Path
import argparse,datetime,hashlib,json,subprocess,time
ROOT=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--root-release',action='store_true',required=True);parser.parse_args()
name='publication-stage-004'
if any((ROOT/x).exists() for x in [name,name+'.stdout',name+'.stderr',name+'-command.json']):raise RuntimeError('Fresh stage/output names required')
review=json.loads((ROOT/'publication-mixed-static-review-002.json').read_text())
for filename,digest in review['reviewed_stable_file_sha256'].items():
 if hashlib.sha256((ROOT/'memory-publication'/filename).read_bytes()).hexdigest()!=digest:raise RuntimeError('Reviewed tooling changed: '+filename)
command=['python3',str(ROOT/'memory-publication/package-candidate005.py'),'stage','--stage-parent',str(ROOT/name),'--released-window-note','All timing completed; root released final mixed-package audit, authored disposition and final018 simulator restoration for full external staging. Shared services stayed running. No new measurements or publication.']
t0=time.monotonic();started=datetime.datetime.now(datetime.timezone.utc).isoformat()
with (ROOT/(name+'.stdout')).open('xb') as out,(ROOT/(name+'.stderr')).open('xb') as err:
 result=subprocess.run(command,stdout=out,stderr=err)
receipt={'argv':command,'started_utc':started,'exit_code':result.returncode,'seconds':time.monotonic()-t0}
for suffix in ['stdout','stderr']:receipt[suffix+'_sha256']=hashlib.sha256((ROOT/(name+'.'+suffix)).read_bytes()).hexdigest()
(ROOT/(name+'-command.json')).write_text(json.dumps(receipt,indent=2)+'\n')
print(json.dumps(receipt));print((ROOT/(name+'.stdout')).read_text());print((ROOT/(name+'.stderr')).read_text());raise SystemExit(result.returncode)
