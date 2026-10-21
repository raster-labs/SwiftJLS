#!/usr/bin/env python3
"""Execute only the three predeclared comparisons, once and in fixed order."""
from pathlib import Path
import hashlib,json,subprocess,sys,time
HERE=Path(__file__).resolve().parent
plan=json.loads((HERE/'plan.json').read_text())
for name,digest in plan['script_sha256'].items(): assert hashlib.sha256((HERE/name).read_bytes()).hexdigest()==digest
assert not (HERE/'results').exists(),'Fresh fixed comparison output required'
commands=[]
for item in plan['comparison_order']:
 args=[sys.executable,str(HERE/item['runner']),'--mode',item['mode'],'--reference',item['reference'],'--output',str(HERE/'results'/item['name'])]
 start=time.monotonic()
 with (HERE/(item['name']+'.log')).open('x') as log:
  result=subprocess.run(args,cwd=HERE,stdout=log,stderr=subprocess.STDOUT)
 commands.append(dict(comparison=item['name'],command=args,exit_code=result.returncode,seconds=time.monotonic()-start,log=item['name']+'.log'))
 (HERE/'commands.json').write_text(json.dumps(commands,indent=2)+'\n');print(json.dumps(commands[-1]),flush=True)
 assert result.returncode==0,'Comparison failed; preserve evidence; no retry'
print('All three fixed comparisons finished; no automatic promotion or threshold waiver',flush=True)
