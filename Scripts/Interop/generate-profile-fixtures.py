#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import argparse, hashlib, json, pathlib, struct, subprocess, tempfile
p=argparse.ArgumentParser();p.add_argument('--oracle',type=pathlib.Path,required=True);p.add_argument('--legacy',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();out=a.output
cases=[]
for item in json.loads((a.legacy/'cases.json').read_text()):
 name=item['name']; bits=item['bits']; data=(a.legacy/(name+'.jls')).read_bytes();raw=(a.legacy/(name+'.raw')).read_bytes()
 values=list(raw) if bits<=8 else list(struct.unpack('<'+'H'*(len(raw)//2),raw))
 planar=[values[x*3+c] for c in range(3) for x in range(4)]
 raw=struct.pack('<12H',*planar)
 case=dict(name=name,width=4,height=1,meaningfulBits=bits,components=3,near=0,interleave=item['interleave'],transform=item['transform'],rgb=True)
 for ext,value in [('jls',data),('u16le',raw)]:
  (out/(name+'.'+ext)).write_bytes(value);case[ext+'_sha256']=hashlib.sha256(value).hexdigest()
 cases.append(case)
(out/'legacy-profiles.json').write_text(json.dumps(dict(licence='Apache-2.0 original synthetic samples',predecessor='15aa75164145414f3d5ffb801401c52d40cc5bcc',cases=cases),indent=2)+'\n')
cases=[]
with tempfile.TemporaryDirectory() as tmp:
 tmp=pathlib.Path(tmp)
 for bits in [8,12]:
  for width,height in [(65537,2),(2,65537)]:
   values=[(i*73+(i//width)*11)&((1<<bits)-1) for i in range(width*height)]
   raw=bytes(values) if bits==8 else struct.pack('<'+'H'*len(values),*values)
   (tmp/'in').write_bytes(raw);table=bytes(i%256 for i in range(1<<bits));(tmp/'table').write_bytes(table)
   subprocess.run([str(a.oracle.resolve()),'encode',str(width),str(height),str(bits),'1','0','1','0',str(tmp/'in'),str(tmp/'table'),str(tmp/'out')],check=True)
   name=f'extended-p{bits}-{width}x{height}'
   case=dict(name=name,width=width,height=height,meaningfulBits=bits,components=1,near=0,interleave=0,rgb=False)
   for ext,data in [('jls',(tmp/'out').read_bytes()),('u16le',struct.pack('<'+'H'*len(values),*values))]:
    (out/(name+'.'+ext)).write_bytes(data);case[ext+'_sha256']=hashlib.sha256(data).hexdigest()
   cases.append(case)
(out/'extended.json').write_text(json.dumps(dict(licence='Apache-2.0 original synthetic samples',oracle_revision='04e44bb760632104ab1209593eea3f8c20ac11e5',cases=cases),indent=2)+'\n')
# Synthetic zero-run scheduling follows pinned JLSwift SyntheticFixtureSupport.
# Expected pixels are independent known zeros; predecessor verifies these streams.
j=[0]*4+[1]*4+[2]*4+[3]*4+[4]*2+[5]*2+[6]*2+[7]*2+list(range(8,16))
for near in [0,3]:
 w,h=17,19; factors=[(2,4),(2,1),(1,2)]; widths=[17,17,9];heights=[19,5,10];indices=[0]*3;bits=[]
 for stripe in range(5):
  for c,(_,v) in enumerate(factors):
   for row in range(v):
    if stripe*v+row>=heights[c]:continue
    remaining=widths[c]
    while remaining>0:
     block=1<<j[indices[c]];bits.append(1)
     if remaining>=block:remaining-=block;indices[c]=min(indices[c]+1,31)
     else:remaining=0
 entropy=bytearray();at=0;capacity=8
 while at<len(bits):
  chunk=bits[at:at+capacity];value=sum(bit<<(capacity-1-k) for k,bit in enumerate(chunk));entropy.append(value);at+=capacity;capacity=7 if value==255 else 8
 # A final FF still needs its stuffed successor.
 if entropy[-1]==255:entropy.append(0)
 data=bytearray([255,216,255,247,0,17,8,0,h,0,w,3,1,0x24,0,2,0x21,0,3,0x12,0,255,218,0,12,3,1,0,2,0,3,0,near,1,0])+entropy+bytes([255,217])
 (out/f'subsampled-zero-n{near}.jls').write_bytes(data)
print('36 legacy HP, 4 independent extended, 2 synthetic subsampled fixtures')

extras=[]
for name in ['legacy-extended-65537x1','legacy-extended-1x65537','legacy-mapping-w1','legacy-mapping-w2']:
 data=(a.legacy/(name+'.jls')).read_bytes();(out/(name+'.jls')).write_bytes(data)
 extras.append(dict(name=name,sha256=hashlib.sha256(data).hexdigest()))
for near in [0,3]:
 name=f'subsampled-zero-n{near}';data=(out/(name+'.jls')).read_bytes()
 extras.append(dict(name=name,sha256=hashlib.sha256(data).hexdigest()))
(out/'legacy-extra.json').write_text(json.dumps(dict(licence='Apache-2.0 synthetic samples; subsampled generator adapted from pinned predecessor tests',predecessor='15aa75164145414f3d5ffb801401c52d40cc5bcc',cases=extras),indent=2)+'\n')

m=json.loads((a.legacy/'legacy-combined.json').read_text());m.update(predecessor='15aa75164145414f3d5ffb801401c52d40cc5bcc',licence='Apache-2.0 original synthetic samples')
for c in m['cases']:
 for ext in ['jls','u16le']:
  data=(a.legacy/(c['name']+'.'+ext)).read_bytes();(out/(c['name']+'.'+ext)).write_bytes(data);c[ext+'_sha256']=hashlib.sha256(data).hexdigest()
(out/'legacy-combined.json').write_text(json.dumps(m,indent=2)+'\n')
