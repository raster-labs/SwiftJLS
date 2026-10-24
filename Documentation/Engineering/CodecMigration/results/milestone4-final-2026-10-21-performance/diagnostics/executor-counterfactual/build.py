#!/usr/bin/env python3
"""One release build and six correctness preflights, without timing qualification."""
import datetime, hashlib, json, os, pathlib, subprocess, tarfile, time

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CODEC = HERE/'codec'
ENV = dict(os.environ, DEVELOPER_DIR='/Library/Developer/CommandLineTools')
source = json.loads((HERE/'source-identity.json').read_text())

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def guard():
    for name, expected in source['source_files'].items():
        assert sha(CODEC/name) == expected, name
    assert sha(HERE/'consumer/Sources/Benchmark/main.swift') == source['consumer_sha256']
    assert sha(HERE/'consumer/Package.swift') == source['consumer_package_sha256']

assert not (HERE/'benchmark-build.log').exists(), 'Refusing to repeat the build.'
guard()
assert not (CODEC/'Tests/SwiftJLSTests/Fixtures').exists()
process = subprocess.Popen(['git','archive',source['base_source'],'Tests/SwiftJLSTests/Fixtures'],cwd=ROOT,stdout=subprocess.PIPE)
with tarfile.open(fileobj=process.stdout,mode='r|') as archive:
    for member in archive:
        path=pathlib.PurePosixPath(member.name)
        assert not path.is_absolute() and '..' not in path.parts
        assert member.isfile() or member.isdir()
        archive.extract(member,CODEC)
assert process.wait()==0
(HERE/'fixture-materialisation.json').write_text(json.dumps(dict(base_source=source['base_source'],fixtures_tree=source['fixtures_tree'],method='Exact git archive; no fixture edits'),indent=2)+'\n')
args=['swift','build','-c','release','--jobs','4','--package-path',str(HERE/'consumer')]
start=time.monotonic()
with (HERE/'benchmark-build.log').open('x') as log:
    result=subprocess.run(args,cwd=ROOT,env=ENV,stdout=log,stderr=subprocess.STDOUT)
command=dict(command=args,cwd=str(ROOT),exit_code=result.returncode,seconds=time.monotonic()-start,
    utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),developer_dir=ENV['DEVELOPER_DIR'])
(HERE/'benchmark-build.json').write_text(json.dumps(command,indent=2)+'\n')
print(json.dumps(command),flush=True)
assert result.returncode==0
guard()
binary=HERE/'consumer/.build/release/Benchmark'
binary_hash=sha(binary)
preflight=HERE/'preflight-correctness-only'
preflight.mkdir()
env=dict(ENV,SWIFTJLS_BENCHMARK_END_TO_END='1')
for key in ['SWIFTJLS_BENCHMARK_EXPORT','SWIFTJLS_BENCHMARK_DECODE']:
    env.pop(key,None)
records=[]
for bits in [12,16]:
    for pattern in ['flat','ramp','noise']:
        case=f'37x23-{pattern}-p{bits}'
        args=[str(binary),'37','23',str(bits),pattern,'0','1','correctness-only-'+case]
        result=subprocess.run(args,cwd=ROOT,env=env,capture_output=True,text=True,timeout=60)
        record=dict(case=case,command=args,exit_code=result.returncode,stdout=result.stdout,stderr=result.stderr,
            purpose='Correctness preflight only. Original Consumer verifies every decoded sample before its emitted single observation; durations are not performance evidence.')
        (preflight/(case+'.json')).write_text(json.dumps(record,indent=2)+'\n')
        assert result.returncode==0,record
        row=json.loads(result.stdout)
        assert row['warmups']==0 and row['iterations']==1 and row['bits']==bits
        records.append(dict(case=case,exit_code=0,full_sample_verification='passed',encoded_bytes=row['encoded_bytes']))
guard()
assert sha(binary)==binary_hash
summary=dict(purpose='Correctness only; no qualified timing',cases=records,all_six_passed=True)
(preflight/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
record=dict(source=source,command=command,binary=str(binary),binary_sha256=binary_hash,
    source_unchanged=True,consumer_unchanged=True,preflight=summary,timings_run=False,promoted=False,
    diagnostic_only='Removing required executor policy is forbidden in production; ABI/optimisation/layout may also differ.')
(HERE/'build-identity.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k not in ['source','command']},indent=2),flush=True)
