from pathlib import Path
import subprocess,os,json,time,hashlib
here=Path(__file__).resolve().parent;root=here.parents[3]
env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools')
guard=['git','diff','--exit-code','bee49a2ad47eae4ea149bdced2043b7a45df3dae','--','Sources','Package.swift','Scripts/Benchmark']
subprocess.run(guard,cwd=root,check=True)
cmd=['swift','build','-c','release','--jobs','4','--package-path',str(here)]
start=time.monotonic()
with (here/'build.log').open('w') as log:r=subprocess.run(cmd,env=env,cwd=root,stdout=log,stderr=subprocess.STDOUT)
result=dict(command=cmd,developer_dir=env['DEVELOPER_DIR'],exit_code=r.returncode,seconds=time.monotonic()-start,swift=subprocess.check_output(['swift','--version'],env=env,text=True))
if r.returncode==0:
 result['binaries']={target:dict(path=str(here/'.build/release'/target),sha256=hashlib.sha256((here/'.build/release'/target).read_bytes()).hexdigest()) for target in ['ReportBenchmark','ZeroBenchmark','UUIDBenchmark']}
subprocess.run(guard,cwd=root,check=True)
(here/'build.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result));raise SystemExit(r.returncode)
