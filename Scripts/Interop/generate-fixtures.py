from pathlib import Path
import subprocess,struct,hashlib,json
import argparse,tempfile
parser=argparse.ArgumentParser()
parser.add_argument('--oracle',required=True,type=Path)
parser.add_argument('--output',required=True,type=Path)
args=parser.parse_args()
root=Path(tempfile.mkdtemp(prefix='swiftjls-fixtures-'));out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);records=[]
for bits in range(2,17):
 for width,height,pattern in [(1,1,'max'),(1,19,'noise'),(23,1,'ramp'),(17,13,'noise'),(33,9,'zero'),(33,9,'max')]:
  mask=(1<<bits)-1;seed=0x4a4c5301;samples=[]
  for y in range(height):
   for x in range(width):
    seed=(1664525*seed+1013904223)&0xffffffff
    samples.append(mask if pattern=='max' else 0 if pattern=='zero' else (x+y*width)&mask if pattern=='ramp' else (seed>>8)&mask)
  name=f'p{bits}-{width}x{height}-{pattern}';raw=bytes(samples) if bits<=8 else struct.pack('<'+'H'*len(samples),*samples)
  source=root/f'{name}.raw';source.write_bytes(raw)
  target=out/f'{name}.jls';subprocess.run([str(args.oracle.resolve()),'encode',str(width),str(height),str(bits),'0',str(source),str(target)],check=True)
  reference=struct.pack('<'+'H'*len(samples),*samples);(out/f'{name}.u16le').write_bytes(reference)
  records.append({'name':name,'width':width,'height':height,'meaningfulBits':bits,'storageBits':16,'signed':False,'byteOrder':'littleEndian','pattern':pattern,'seed':'0x4a4c5301','encoded_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),'samples_sha256':hashlib.sha256(reference).hexdigest()})
(out/'manifest.json').write_text(json.dumps({'generator':'generate-oracle-fixtures.py; 32-bit LCG 1664525*x+1013904223, shift 8, precision mask','oracle':'CharLS 2.4.2','oracle_commit':'36dd3307e070d8fbc765c3ba890b7e681046fa39','oracle_licence':'BSD-3-Clause; built outside SwiftJLS; not a runtime dependency','fixture_licence':'Apache-2.0; original synthetic samples generated for this migration','cases':records},indent=2)+'\n')
print('Generated',len(records),'independent encoded fixtures.')
