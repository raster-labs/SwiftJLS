#!/usr/bin/env python3
import argparse, importlib.util, json, os, subprocess, time
from pathlib import Path
spec=importlib.util.spec_from_file_location('qualification_source',Path(__file__).with_name('qualification-source.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q);os.chdir(q.ROOT)
parser=argparse.ArgumentParser(description='Qualify final source while explicitly reusing the measured frozen Benchmark')
parser.add_argument('--benchmark-build-identity',required=True,type=Path)
args=parser.parse_args()
r=q.OUT;records=[];identity=q.source();version_sha256=q.sha(q.ROOT/'VERSION')
if (r/'value-qualification-commands.json').exists():raise RuntimeError('Refusing to overwrite qualification results')
q.write(r/'qualification-source.json',identity)
def run(cmd,label,env=None):
    start=time.monotonic()
    with (r/(label+'.log')).open('w') as f:p=subprocess.run(cmd,stdout=f,stderr=subprocess.STDOUT,env=env)
    records.append(dict(command=cmd,label=label,exit_code=p.returncode,seconds=time.monotonic()-start))
    q.write(r/'value-qualification-commands.json',records);q.unchanged(identity)
    if q.sha(q.ROOT/'VERSION')!=version_sha256:raise RuntimeError('VERSION changed during qualification')
    if p.returncode:raise RuntimeError(label)
    print(label+' passed',flush=True)
env=os.environ.copy();env['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
run(['python3',str(r/'reuse-benchmark.py'),'--build-identity',str(args.benchmark_build_identity.resolve()),'--output',str(r/'benchmark-reuse.json')], 'benchmark-reuse-value',env)
reuse=json.loads((r/'benchmark-reuse.json').read_text())
if reuse['source']['files']!=identity['files']:raise RuntimeError('Benchmark source bridge differs from qualification source')
binaries={'Benchmark':reuse['binary']}
env['DEVELOPER_DIR']='/Applications/Xcode.app/Contents/Developer'
run(['python3',str(r/'apple-build-value.py')],'apple-build-value',env)
run(['python3',str(r/'apple-runtime-value.py'),'26.0'],'apple-runtime-value',env)
run(['python3',str(r/'apple-resource-value.py')],'apple-resource-value',env)
env['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
for name,package in [('AppleRuntimeConsumer','Examples/AppleRuntimeConsumer'),('ResourceStress','Examples/ResourceStress')]:
    cmd=['swift','build','--build-system','swiftbuild','-c','release','--jobs','4','--package-path',package,'--scratch-path',str(r/'build'/name)]
    run(cmd,'native-'+name+'-value',env)
    folder=Path(subprocess.check_output(cmd+['--show-bin-path'],env=env,text=True).strip())
    binary=folder/name
    if not binary.is_file():raise RuntimeError('Missing product '+str(binary))
    binaries[name]=dict(path=str(binary),sha256=q.sha(binary))
q.write(r/'consumer-builds.json',dict(source=identity,developer_dir=env['DEVELOPER_DIR'],
    swift=subprocess.check_output(['swift','--version'],env=env,text=True),binaries=binaries,
    consumer_sha256=q.sha(q.ROOT/'Scripts/Benchmark/Consumer.swift'),
    compiled_consumer_sha256=reuse['compiled_consumer_sha256'],
    benchmark_provenance=dict(mode='reused_frozen_candidate',record='benchmark-reuse.json',
        record_sha256=q.sha(r/'benchmark-reuse.json'),build_identity_sha256=reuse['build_identity_sha256'])))
run([binaries['AppleRuntimeConsumer']['path'],str(q.ROOT/'Tests/SwiftJLSTests/Fixtures')],'host-AppleRuntimeConsumer-value',env)
run([binaries['ResourceStress']['path']],'host-ResourceStress-value',env)
binary=str(r/'test-build/release/out/Products/Release/swiftjls-cli')
run(['python3','Scripts/test-payload-cli.py','--binary',binary,'--output',str(r/'cli-payload-value.json')],'cli-payload-value',env)
run(['python3','Scripts/test-cli.py','--binary',binary,'--output',str(r/'cli-process-value')],'cli-process-value',env)
