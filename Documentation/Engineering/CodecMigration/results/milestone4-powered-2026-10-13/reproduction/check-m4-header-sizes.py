from pathlib import Path
import subprocess,os,json,hashlib
out=Path('work/m4-header-sizes');out.mkdir()
records=[];commands=[]
def markers(data):
 i=0;found=[];entropy=bytearray()
 while i<len(data):
  if i+1<len(data) and data[i]==255 and data[i+1]>=128:
   code=data[i+1]
   if code in [216,217] or 208<=code<=215:n=2
   else:n=2+int.from_bytes(data[i+2:i+4],'big')
   assert n>=2 and i+n<=len(data)
   found.append(dict(marker=f'FF{code:02X}',bytes=n,payload_hex=data[i+4:i+n].hex() if n>2 else ''));i+=n
  else:entropy.append(data[i]);i+=1
 return found,hashlib.sha256(entropy).hexdigest(),len(entropy)
for bits in [12,16]:
 for near in [0,3]:
  for mode in [0,1,2]:
   pair={}
   for label in ['predecessor','successor']:
    path=out/f'{label}-p{bits}-n{near}-i{mode}.jls';args=[f'work/m4-benchmark/{label}/.build/release/Benchmark','512','512',str(bits),'flat','0','1',label,'3',str(near),str(mode)]
    env=os.environ.copy();env['SWIFTJLS_BENCHMARK_EXPORT']=str(path)
    p=subprocess.run(args,env=env,capture_output=True,text=True);commands.append(dict(command=args,environment=dict(SWIFTJLS_BENCHMARK_EXPORT=str(path)),exit_code=p.returncode,stderr=p.stderr));assert p.returncode==0
    data=path.read_bytes();m,h,n=markers(data);pair[label]=dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),markers=m,entropy_bytes=n,entropy_sha256=h)
   for label,other in [('predecessor','successor'),('successor','predecessor')]:
    args=[f'work/m4-benchmark/{label}/.build/release/Benchmark','512','512',str(bits),'flat','0','1',label,'3',str(near),str(mode)]
    env=os.environ.copy();env['SWIFTJLS_BENCHMARK_DECODE']=str(out/f'{other}-p{bits}-n{near}-i{mode}.jls')
    p=subprocess.run(args,env=env,capture_output=True,text=True);commands.append(dict(command=args,environment=dict(SWIFTJLS_BENCHMARK_DECODE=env['SWIFTJLS_BENCHMARK_DECODE']),exit_code=p.returncode,stderr=p.stderr));assert p.returncode==0
   records.append(dict(bits=bits,near=near,interleave=mode,producers=pair,delta_bytes=pair['successor']['bytes']-pair['predecessor']['bytes'],entropy_identical=pair['successor']['entropy_sha256']==pair['predecessor']['entropy_sha256']))
(out/'summary.json').write_text(json.dumps(dict(source='36fb97e0a654c0d18802b666df2b07d24cb0637a',predecessor='15aa75164145414f3d5ffb801401c52d40cc5bcc',scope='Diagnostic export/cross-decode of flat 512 RGB cases; no timings qualify performance.',cases=records,commands=commands),indent=2)+'\n')
print('12 marker comparisons and 24 cross-decodes pass',[(r['near'],r['delta_bytes'],r['entropy_identical']) for r in records])
