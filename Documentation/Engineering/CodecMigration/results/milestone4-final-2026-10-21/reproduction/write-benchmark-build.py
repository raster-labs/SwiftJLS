#!/usr/bin/env python3
"""Bind the new successful build and reused predecessor to committed source."""
import importlib.util, json, os, subprocess
from pathlib import Path
spec=importlib.util.spec_from_file_location('qualification_source',Path(__file__).with_name('qualification-source.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q);os.chdir(q.ROOT)
identity=q.source()
if identity['source_commit'] is None:raise RuntimeError('Commit production source before freezing benchmark identity')
build=json.loads((q.OUT/'consumer-builds.json').read_text())
if build['source']['files']!=identity['files']:raise RuntimeError('Benchmark source changed after build')
commands=json.loads((q.OUT/'value-qualification-commands.json').read_text())
records=[r for r in commands if r['label']=='benchmark-value']
expected=['swift','build','-c','release','--jobs','4','--package-path','work/m4-benchmark/successor']
if len(records)!=1 or records[0]['command']!=expected or records[0]['exit_code']:
    raise RuntimeError('Matching successful benchmark build command required')
if build['developer_dir']!='/Library/Developer/CommandLineTools':raise RuntimeError('Wrong compiler selection')
historical=q.ROOT/'Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-14/powered/scalar/environment.json'
old=json.loads(historical.read_text())
if build['swift'].split('Apple Swift version',1)[-1].strip()!=old['swift']['output'].split('Apple Swift version',1)[-1].strip():
    raise RuntimeError('Current compiler identity differs from the reused predecessor build evidence')
predecessor_commit='15aa75164145414f3d5ffb801401c52d40cc5bcc'
predecessor_repo=q.ROOT.parent/'JLSwift'
if subprocess.check_output(['git','rev-parse','HEAD'],cwd=predecessor_repo,text=True).strip()!=predecessor_commit:
    raise RuntimeError('Wrong predecessor commit')
if subprocess.check_output(['git','status','--porcelain','--untracked-files=no'],cwd=predecessor_repo,text=True):
    raise RuntimeError('Predecessor tracked checkout is dirty')
binaries={name:str(q.ROOT/'work/m4-benchmark'/name/'.build/release/Benchmark') for name in ['predecessor','successor']}
hashes={name:q.sha(Path(path)) for name,path in binaries.items()}
if hashes['predecessor']!=old['binary_sha256']['predecessor']:
    raise RuntimeError('Reused predecessor does not match recorded historical binary')
if hashes['successor']!=build['binaries']['Benchmark']['sha256']:
    raise RuntimeError('Successor differs from the successful build')
consumer=q.sha(q.ROOT/'Scripts/Benchmark/Consumer.swift')
if any(q.sha(q.ROOT/'work/m4-benchmark'/name/'Sources/Benchmark/main.swift')!=consumer for name in binaries):
    raise RuntimeError('Benchmark harness differs from original common Consumer.swift')
if consumer!=old['consumer_sha256'] or consumer!=build['consumer_sha256']:
    raise RuntimeError('Benchmark consumer identity changed')
record=dict(source_commit=identity['source_commit'],predecessor_commit=predecessor_commit,
    developer_dir=build['developer_dir'],swift=build['swift'],
    source_files={k:v for k,v in identity['files'].items() if k=='Package.swift' or k.startswith('Sources/')},
    consumer_sha256=consumer,binaries=binaries,binary_sha256=hashes,builds_verified=True,
    successor_build=records[0],successor_build_log='benchmark-value.log',
    source_fingerprint_record='consumer-builds.json',
    predecessor_provenance=dict(status='Reused historical build, not rebuilt in this qualification',
        record=str(historical.relative_to(q.ROOT)),record_sha256=q.sha(historical),
        verified_current_source_and_consumer=True,verified_current_binary_hash=True))
q.write(q.OUT/'benchmark-build.json',record)
print(json.dumps({k:record[k] for k in ['source_commit','binary_sha256','builds_verified']},indent=2))
