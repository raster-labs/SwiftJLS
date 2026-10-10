#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Conformance-only use of the separately downloaded ITU T.87 reference decoder.
The HP reference executables and their licence remain outside this repository.
"""
import argparse,base64,hashlib,io,json,pathlib,struct,subprocess,tempfile,urllib.request,zipfile
p=argparse.ArgumentParser();p.add_argument('--candidates',type=pathlib.Path,required=True);p.add_argument('--report',type=pathlib.Path,required=True);a=p.parse_args()
url='https://www.itu.int/rec/dologin_pub.asp?id=T-REC-T.87-199806-I%21%21ZPF-E&lang=e&type=items';digest='c54f20d167485399d2094d3375151d2ec31535d4c32d92fb929b15fc364ea41a'
archive=urllib.request.urlopen(url,timeout=120).read();assert hashlib.sha256(archive).hexdigest()==digest
outer=zipfile.ZipFile(io.BytesIO(archive));software=zipfile.ZipFile(io.BytesIO(outer.read('software/T87/Software.zip')));reference=zipfile.ZipFile(io.BytesIO(software.read('software/T87/jlsrefV100.zip')))
def pgm(data):
 tokens=[];index=0
 while len(tokens)<4:
  while data[index] in b' \t\r\n':index+=1
  if data[index]==35:
   index=data.index(b'\n',index)+1;continue
  end=index
  while data[end] not in b' \t\r\n':end+=1
  tokens.append(data[index:end]);index=end
 assert tokens[0]==b'P5'
 index+=2 if data[index:index+2]==b'\r\n' else 1
 width,height,maximum=map(int,tokens[1:]);raw=data[index:]
 samples=list(raw) if maximum<256 else list(struct.unpack('>'+'H'*(len(raw)//2),raw))
 assert len(samples)==width*height
 return width,height,maximum,samples
results=[]
with tempfile.TemporaryDirectory(prefix='t87-conformance-') as temporary:
 directory=pathlib.Path(temporary)
 # Extract only named oracle resources, with original notices retained.
 for name in ['nloco16d.exe','nlocod.exe','nloco16e.exe','nlocoe.exe','README.TXT']:(directory/name).write_bytes(reference.read(name))
 (directory/'LEGAL.txt').write_bytes(software.read('software/T87/LEGAL.txt'))
 for case in json.loads(a.candidates.read_text())['cases']:
  maximum = case['preset']['maximumSampleValue']
  if maximum < 3:
   results.append(dict(name=case['name'],passed=False,unsupported=True,reason='Published reference requires MAXVAL >= 3.'))
   continue
  decoder = 'nlocod.exe' if maximum < 256 else 'nloco16d.exe'
  encoder = 'nlocoe.exe' if maximum < 256 else 'nloco16e.exe'
  (directory/'input.jls').write_bytes(base64.b64decode(case['encoded']))
  output=directory/'output.pgm';output.unlink(missing_ok=True)
  result=subprocess.run([str(directory/decoder),'input.jls','output.pgm'],cwd=directory,capture_output=True,timeout=10)
  entry=dict(name=case['name'],exit_code=result.returncode)
  try:
   assert result.returncode==0,result.stderr.decode(errors='replace')
   width,height,maximum,samples=pgm(output.read_bytes())
   original=base64.b64decode(case['samples']);expected=struct.unpack('<'+'H'*(len(original)//2),original)
   error=max(abs(x-y) for x,y in zip(samples,expected));entry.update(maximum_error=error,maximum=maximum)
   assert (width,height)==(case['width'],case['height']) and len(samples)==len(expected) and error<=case['near']
   entry['passed']=True
   # Produce independently encoded fixtures using the same explicit parameters.
   preset=case['preset'];source=bytes(expected) if maximum<256 else struct.pack('>'+'H'*len(expected),*expected)
   (directory/'source.pgm').write_bytes(f'P5\n{width} {height}\n{maximum}\n'.encode()+source)
   command=[str(directory/encoder),'-c0',f"-e{case['near']}",f"-r{preset['reset']}",f"-Ta{preset['threshold1']}",f"-Tb{preset['threshold2']}",f"-Tc{preset['threshold3']}",'source.pgm','-oreference.jls']
   generated=subprocess.run(command,cwd=directory,capture_output=True,timeout=10)
   assert generated.returncode==0,generated.stderr.decode(errors='replace')
   entry['reference_encoded']=base64.b64encode((directory/'reference.jls').read_bytes()).decode()
   decoded=subprocess.run([str(directory/decoder),'reference.jls','reference.pgm'],cwd=directory,capture_output=True,timeout=10)
   assert decoded.returncode==0
   _,_,_,reconstruction=pgm((directory/'reference.pgm').read_bytes())
   entry['reference_decoded_u16le']=base64.b64encode(struct.pack('<'+'H'*len(reconstruction),*reconstruction)).decode()
  except Exception as error:
   entry.update(passed=False,error=str(error),stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace'))
  results.append(entry)
report=dict(oracle='ITU T.87 HP conformance reference V1.00',archive_sha256=digest,source=url,cases=results)
a.report.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
assert all(r['passed'] or r.get('unsupported',False) for r in results)
