import pathlib,subprocess,json,time,hashlib
out=pathlib.Path('work/m4-final-cpu-profile');out.mkdir()
binary=pathlib.Path('work/m4-benchmark/successor/.build/release/Benchmark');cmd=[str(binary),'2048','2048','16','flat','5','500','successor','3','0','1']
with (out/'consumer.json').open('w') as stdout,(out/'consumer.stderr').open('w') as stderr:
 start=time.monotonic();p=subprocess.Popen(cmd,stdout=stdout,stderr=stderr)
 sample=['sample',str(p.pid),'10','1','-file',str(out/'sample.txt')]
 r=subprocess.run(sample,capture_output=True,text=True)
 (out/'sample.stdout').write_text(r.stdout);(out/'sample.stderr').write_text(r.stderr)
 code=p.wait();(out/'commands.json').write_text(json.dumps(dict(source='36fb97e0a654c0d18802b666df2b07d24cb0637a',binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),consumer=dict(command=cmd,exit_code=code),sample=dict(command=sample,exit_code=r.returncode),seconds=time.monotonic()-start,scope='Diagnostic CPU sampling of mixed repeated encode/decode; timings are not performance measurements.'),indent=2)+'\n')
 print('CPU profile exits',code,r.returncode)
