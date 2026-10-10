#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import argparse,hashlib,json,pathlib,struct,subprocess,tempfile
p=argparse.ArgumentParser();p.add_argument('--oracle',type=pathlib.Path,required=True);p.add_argument('--fixtures',type=pathlib.Path,required=True);p.add_argument('--encoded',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args();results=[]
with tempfile.TemporaryDirectory() as tmp:
 tmp=pathlib.Path(tmp)
 for manifest in ['mapping','extended','legacy-profiles']:
  for case in json.loads((a.fixtures/(manifest+'.json')).read_text())['cases']:
   name=case['name'];reference=(a.fixtures/(name+'.u16le')).read_bytes()
   assert hashlib.sha256(reference).hexdigest()==case['u16le_sha256']
   source=a.encoded/(name+'.jls');dest=tmp/'pixels'
   subprocess.run([str(a.oracle.resolve()),'decode',str(source),str(dest)],check=True,stdout=subprocess.DEVNULL)
   decoded=dest.read_bytes();values=list(decoded) if case['meaningfulBits']<=8 else list(struct.unpack('<'+'H'*(len(decoded)//2),decoded))
   c=case['components'];plane=case['width']*case['height']
   if manifest!='legacy-profiles' and case['interleave']:
    values=[values[i*c+channel] for channel in range(c) for i in range(plane)]
   actual=struct.pack('<'+'H'*len(values),*values)
   assert actual==reference,name
   if manifest=='mapping':assert (tmp/'pixels.table7').read_bytes()==(a.fixtures/(name+'.table')).read_bytes(),name
   results.append(dict(name=name,passed=True,samples=len(values),encoded_sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
a.report.write_text(json.dumps(dict(oracle_revision='04e44bb760632104ab1209593eea3f8c20ac11e5',cases=results,passed=len(results)),indent=2)+'\n')
print(len(results),'independently verified mapping, extended and legacy migration outputs')
