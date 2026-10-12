#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Investigate large-noise byte differences outside all timed measurements."""
import argparse, array, hashlib, json, os, pathlib, subprocess, sys, tempfile
p=argparse.ArgumentParser()
for name in ['predecessor','successor','oracle','report']: p.add_argument('--'+name,type=pathlib.Path,required=True)
a=p.parse_args(); records=[]
def expected(width,height,bits):
    mask=(1<<64)-1; maximum=(1<<bits)-1
    for i in range(width*height):
        z=(i+0x9e3779b97f4a7c15)&mask
        z=((z^(z>>30))*0xbf58476d1ce4e5b9)&mask
        z=((z^(z>>27))*0x94d049bb133111eb)&mask
        yield (z^(z>>31))&maximum
with tempfile.TemporaryDirectory(prefix='swiftjls-benchmark-oracle-') as temp:
    temp=pathlib.Path(temp)
    for width,height in [(512,512),(2048,2048),(4096,3073)]:
      for bits in [12,16]:
        row=dict(width=width,height=height,bits=bits,pattern='noise',commands=[],outputs={})
        paths={label:temp/(label+'.jls') for label in ['predecessor','successor']}
        # Export each producer, then independently decode and verify every value.
        for label in paths:
            command=[str(getattr(a,label).resolve()),str(width),str(height),str(bits),'noise','0','1',label]
            environment=dict(os.environ,SWIFTJLS_BENCHMARK_EXPORT=str(paths[label]))
            r=subprocess.run(command,env=environment,capture_output=True,timeout=180)
            row['commands'].append(dict(command=command,export=str(paths[label]),exit_code=r.returncode))
            r.check_returncode()
            raw=temp/'decoded.raw'
            command=[str(a.oracle.resolve()),'decode',str(paths[label]),str(raw)]
            r=subprocess.run(command,capture_output=True,timeout=180)
            row['commands'].append(dict(command=command,exit_code=r.returncode));r.check_returncode()
            values=array.array('H');values.frombytes(raw.read_bytes())
            if sys.byteorder!='little':values.byteswap()
            assert len(values)==width*height
            difference=max(abs(x-y) for x,y in zip(values,expected(width,height,bits)))
            row['outputs'][label]=dict(bytes=paths[label].stat().st_size,sha256=hashlib.sha256(paths[label].read_bytes()).hexdigest(),independent_maximum_error=difference)
        for label,other in [('successor','predecessor'),('predecessor','successor')]:
            command=[str(getattr(a,label).resolve()),str(width),str(height),str(bits),'noise','0','1',label]
            r=subprocess.run(command,env=dict(os.environ,SWIFTJLS_BENCHMARK_DECODE=str(paths[other])),capture_output=True,timeout=180)
            row['commands'].append(dict(command=command,decode=str(paths[other]),exit_code=r.returncode))
            row[label+'_decodes_'+other]=r.returncode==0
            if r.returncode:row[label+'_failure']=r.stderr.decode(errors='replace')[:2000]
        row['byte_identical']=paths['predecessor'].read_bytes()==paths['successor'].read_bytes()
        row['passed']=all(v['independent_maximum_error']==0 for v in row['outputs'].values()) and row['successor_decodes_predecessor'] and row['predecessor_decodes_successor']
        records.append(row)
        a.report.write_text(json.dumps(dict(oracle_revision='04e44bb760632104ab1209593eea3f8c20ac11e5',scope='Separate correctness experiment; export and cross-decode are outside timed benchmark runs',cases=records),indent=2)+'\n')
        print(width,height,bits,'passed',row['passed'],'byte_identical',row['byte_identical'],flush=True)
if not all(r['passed'] for r in records):raise SystemExit('Benchmark interoperability failure')
