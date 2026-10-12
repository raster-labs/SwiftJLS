#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Independent opaque/scalar mapping vectors, including standard continuations."""
import argparse, hashlib, json, pathlib, struct, subprocess, tempfile
p=argparse.ArgumentParser(); p.add_argument('--oracle',type=pathlib.Path,required=True); p.add_argument('--output',type=pathlib.Path,required=True); a=p.parse_args()
oracle=str(a.oracle.resolve()); out=a.output; out.mkdir(parents=True,exist_ok=True); cases=[]
with tempfile.TemporaryDirectory() as tmp:
    tmp=pathlib.Path(tmp)
    for bits in [2,8,12,16]:
        maximum=(1<<bits)-1
        for components,ilv in [(1,0),(3,0),(3,1),(3,2)]:
            for wt,near in [(1,0),(2,0),(2,1),(3,0)]:
                if bits == 16 and wt == 3: continue # CharLS splits these entries across segment boundaries.
                width,height=7,5; plane=width*height
                samples=[(i*1733+c*19+(i%3)*maximum)&maximum for c in range(components) for i in range(plane)]
                values=[((i*271)^0xa5) & (255 if wt==1 else 65535) for i in range(maximum+1)]
                table=b''.join(v.to_bytes(wt,'big') for v in values)
                native=samples if ilv==0 else [samples[c*plane+i] for i in range(plane) for c in range(components)]
                raw=bytes(native) if bits<=8 else struct.pack('<'+'H'*len(native),*native)
                (tmp/'input').write_bytes(raw); (tmp/'table').write_bytes(table)
                subprocess.run([oracle,'encode',str(width),str(height),str(bits),str(components),str(ilv),str(wt),str(near),str(tmp/'input'),str(tmp/'table'),str(tmp/'out')],check=True)
                subprocess.run([oracle,'decode',str(tmp/'out'),str(tmp/'decoded')],check=True,stdout=subprocess.DEVNULL)
                assert (tmp/'decoded.table7').read_bytes()==table
                decoded=(tmp/'decoded').read_bytes(); actual=list(decoded) if bits<=8 else list(struct.unpack('<'+'H'*(len(decoded)//2),decoded))
                if ilv: actual=[actual[i*components+c] for c in range(components) for i in range(plane)]
                assert max(abs(x-y) for x,y in zip(samples,actual))<=near
                name=f'map-p{bits}-c{components}-i{ilv}-w{wt}-n{near}'
                record=dict(name=name,width=width,height=height,meaningfulBits=bits,near=near,components=components,interleave=ilv,rgb=False,entryWidth=wt)
                for ext,data in [('jls',(tmp/'out').read_bytes()),('u16le',struct.pack('<'+'H'*len(actual),*actual)),('table',table),('mapped.u16le',struct.pack('<'+'H'*len(actual),*[values[v] for v in actual]))]:
                    (out/(name+'.'+ext)).write_bytes(data);record[ext+'_sha256']=hashlib.sha256(data).hexdigest()
                cases.append(record)
(out/'mapping.json').write_text(json.dumps(dict(licence='Apache-2.0 original synthetic samples',oracle='CharLS development mapping API',oracle_revision='04e44bb760632104ab1209593eea3f8c20ac11e5', limitations=['16-bit three-byte tables excluded: this CharLS revision emits 65530-byte chunks, splitting Wt=3 entries contrary to T.87 C.2.4.1.2/3.'],cases=cases),indent=2)+'\n')
print(len(cases),'independent mapping fixtures')
