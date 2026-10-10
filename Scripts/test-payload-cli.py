#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Black-box payload, malformed-input, transaction and pipe checks."""
import argparse,json,pathlib,subprocess,tempfile,os,signal,time,struct
p=argparse.ArgumentParser();p.add_argument('--binary',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args();binary=str(a.binary.resolve());results=[]
def run(args,data=None,code=0):
 r=subprocess.run([binary,*map(str,args)],input=data,capture_output=True,timeout=10);results.append(dict(args=list(map(str,args)),exit=r.returncode,expected=code));assert r.returncode==code,(args,r.returncode,r.stderr.decode());return r
with tempfile.TemporaryDirectory(prefix='swiftjls payload λ ') as directory:
 d=pathlib.Path(directory);raw=struct.pack('<'+ 'H'*221,*[(i*1733)&65535 for i in range(221)]);header=b'NRRD0005\ntype: uint16\ndimension: 2\nsizes: 17 13\nencoding: raw\nendian: little\n\n';source=header+raw
 encoded=run(['encode','-i','-','-o','-','--json'],source);assert encoded.stdout[:2]==b'\xff\xd8';assert json.loads(encoded.stderr)['success']
 decoded=run(['decode','-i','-','-o','-'],encoded.stdout);assert decoded.stdout==source
 info=json.loads(run(['inspect','-i','-','--json'],encoded.stdout).stdout);assert info['width']==17 and info['meaningfulBits']==16
 run(['validate','-i','-'],encoded.stdout)
 for endian in ['big','little']:
  alternate=header.replace(b'little',endian.encode()).replace(b'\n',b'\r\n')+(raw if endian=='little' else b''.join(raw[i:i+2][::-1] for i in range(0,len(raw),2)))
  assert run(['encode','-i','-','-o','-'],alternate).stdout==encoded.stdout
 near=run(['encode','-i','-','-o','-','--mode','near-lossless','--max-error','3'],source).stdout
 actual=run(['decode','-i','-','-o','-'],near).stdout.split(b'\n\n',1)[1]
 assert max(abs(x-y) for x,y in zip(struct.unpack('<221H',raw),struct.unpack('<221H',actual)))<=3
 output=d/'result λ.jls';run(['encode','-i','-','-o',output],source);saved=output.read_bytes()
 run(['encode','-i','-','-o',output],source,6);assert output.read_bytes()==saved
 run(['encode','-i','-','-o',output,'--overwrite'],source);assert output.read_bytes()==saved
 for malformed,code in [(b'',3),(header+raw[:-1],3),(source+b'\x00',3),(header.replace(b'17 13',b'17 junk 13')+raw,3),(header.replace(b'raw',b'gzip')+raw,4),(header.replace(b'encoding: raw',b'data file: https://invalid.example/x\nencoding: raw')+raw,4),(header.replace(b'type: uint16',b'type: uint16\ntype: uint16')+raw,4),(b'NRRD0005\n'+b'#'*17000,5)]:
  target=d/'never.nrrd';run(['encode','-i','-','-o',target],malformed,code);assert not target.exists()
 run(['encode','-i','-','-o','-','--max-error','3'],source,2)
 run(['encode','-i','-','-o','-','--mode','near-lossless','--max-error','999'],source,2)
 run(['decode','-i','-','-o','-'],encoded.stdout[:-1],3)
 run(['encode','-i','-','-o','-','--max-memory','100'],source,5)
 assert not list(d.glob('.swiftjls-*.tmp'))
 # A blocked input pipe must obey deadline and SIGINT without consuming data.
 for cancel in [False,True]:
  process=subprocess.Popen([binary,'encode','-i','-','-o','-','--timeout','0.25' if not cancel else '10'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  if cancel: time.sleep(.1);process.send_signal(signal.SIGINT)
  code=process.wait(timeout=3);process.stdin.close();assert code==(130 if cancel else 5),code
  results.append(dict(condition='cancel blocked pipe' if cancel else 'deadline blocked pipe',exit=code))
 # Closed binary output must fail, with no success JSON.
 rd,wr=os.pipe();os.close(rd)
 try:
  process=subprocess.run([binary,'encode','-i','-','-o','-','--json'],input=source,stdout=wr,stderr=subprocess.PIPE,timeout=5)
 finally: os.close(wr)
 assert process.returncode==6 and b'"success"' not in process.stderr
 results.append(dict(condition='closed binary output',exit=process.returncode))
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(results,indent=2)+'\n');print(len(results),'payload checks passed')
