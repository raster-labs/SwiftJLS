from pathlib import Path
import json,subprocess,struct,hashlib
import argparse,tempfile
parser=argparse.ArgumentParser()
parser.add_argument('--oracle',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
root=Path(tempfile.mkdtemp(prefix='swiftjls-near-'));d=args.output.resolve();manifest=json.loads((d/'manifest.json').read_text());records=[r for r in manifest['cases'] if not r.get('near',0)]
for bits in range(2,17):
 for near in sorted(set([1,min(3,((1<<bits)-1)//2), min(255,((1<<bits)-1)//2)])):
  for w,h,pattern in [(1,19,'noise'),(17,13,'noise'),(33,9,'max'),(33,9,'zero')]:
   source=d/f'p{bits}-{w}x{h}-{pattern}.u16le';raw=source.read_bytes();native=raw[::2] if bits<=8 else raw
   input=root/'near.raw';input.write_bytes(native);name=f'n{near}-p{bits}-{w}x{h}-{pattern}';jls=d/(name+'.jls')
   subprocess.run([str(args.oracle.resolve()),'encode',str(w),str(h),str(bits),str(near),str(input),str(jls)],check=True)
   decoded=root/'near-decoded.raw';subprocess.run([str(args.oracle.resolve()),'decode',str(jls),str(decoded)],stdout=subprocess.DEVNULL,check=True)
   expected=decoded.read_bytes();expected=b''.join(bytes([v,0]) for v in expected) if bits<=8 else expected
   (d/(name+'.u16le')).write_bytes(raw);(d/(name+'.decoded.u16le')).write_bytes(expected)
   records.append(dict(name=name,width=w,height=h,meaningfulBits=bits,near=near,encoded_sha256=hashlib.sha256(jls.read_bytes()).hexdigest(),samples_sha256=hashlib.sha256(raw).hexdigest(),decoded_sha256=hashlib.sha256(expected).hexdigest()))
manifest['cases']=records;(d/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print('Total',len(records))
