#!/usr/bin/env python3
"""Bind the verified frozen candidate and predecessor to final committed source."""
import importlib.util, json, os, subprocess
from pathlib import Path
spec=importlib.util.spec_from_file_location('qualification_source',Path(__file__).with_name('qualification-source.py'))
q=importlib.util.module_from_spec(spec);spec.loader.exec_module(q);os.chdir(q.ROOT)
identity=q.source()
if identity['source_commit'] is None:raise RuntimeError('Commit production source before freezing benchmark identity')
build=json.loads((q.OUT/'consumer-builds.json').read_text())
if build['source']['files']!=identity['files']:raise RuntimeError('Benchmark source changed after build')
commands=json.loads((q.OUT/'value-qualification-commands.json').read_text())
records=[r for r in commands if r['label']=='benchmark-reuse-value']
reuse=json.loads((q.OUT/'benchmark-reuse.json').read_text())
expected=['python3',str(q.OUT/'reuse-benchmark.py'),'--build-identity',reuse['build_identity_path'],'--output',str(q.OUT/'benchmark-reuse.json')]
if len(records)!=1 or records[0]['command']!=expected or records[0]['exit_code']:
    raise RuntimeError('Matching successful explicit benchmark reuse command required')
if reuse['verified'] is not True or reuse['rebuilt'] is not False or reuse['source_commit']!=identity['source_commit'] or reuse['source']['files']!=identity['files']:
    raise RuntimeError('Benchmark reuse source bridge is incomplete or stale')
if q.sha(Path(reuse['build_identity_path']))!=reuse['build_identity_sha256'] or q.sha(q.ROOT/'VERSION')!=reuse['version_sha256']:
    raise RuntimeError('Candidate build record or VERSION changed after reuse validation')
if build['benchmark_provenance']['record_sha256']!=q.sha(q.OUT/'benchmark-reuse.json'):
    raise RuntimeError('Consumer qualification refers to a different reuse record')
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
binaries={'predecessor':str(q.ROOT/'work/m4-benchmark/predecessor/.build/release/Benchmark'),
          'successor':reuse['binary']['path']}
hashes={name:q.sha(Path(path)) for name,path in binaries.items()}
if hashes['predecessor']!=old['binary_sha256']['predecessor']:
    raise RuntimeError('Reused predecessor does not match recorded historical binary')
if hashes['successor']!=build['binaries']['Benchmark']['sha256'] or hashes['successor']!=reuse['binary']['sha256']:
    raise RuntimeError('Successor differs from the verified frozen candidate')
consumer=q.sha(q.ROOT/'Scripts/Benchmark/Consumer.swift')
candidate=Path(reuse['build_identity_path']).parent
if q.sha(q.ROOT/'work/m4-benchmark/predecessor/Sources/Benchmark/main.swift')!=consumer or q.sha(candidate/'consumer/Sources/Benchmark/main.swift')!=consumer:
    raise RuntimeError('Benchmark harness differs from original common Consumer.swift')
if consumer!=old['consumer_sha256'] or consumer!=build['consumer_sha256']:
    raise RuntimeError('Benchmark consumer identity changed')
record=dict(source_commit=identity['source_commit'],predecessor_commit=predecessor_commit,
    developer_dir=build['developer_dir'],swift=build['swift'],
    source_files={k:v for k,v in identity['files'].items() if k in ['Package.swift','VERSION'] or k.startswith('Sources/')},
    consumer_sha256=consumer,binaries=binaries,binary_sha256=hashes,builds_verified=True,
    successor_build=reuse['original_build_command'],successor_build_mode='reused_frozen_candidate',
    successor_reuse_command=records[0],successor_reuse_log='benchmark-reuse-value.log',
    successor_reuse_record='benchmark-reuse.json',successor_reuse_record_sha256=q.sha(q.OUT/'benchmark-reuse.json'),
    original_candidate_base=reuse['original_base_source'],original_candidate_patches=reuse['original_patches'],
    original_candidate_build_identity_sha256=reuse['build_identity_sha256'],
    source_fingerprint_record='consumer-builds.json',
    predecessor_provenance=dict(status='Reused historical build, not rebuilt in this qualification',
        record=str(historical.relative_to(q.ROOT)),record_sha256=q.sha(historical),
        verified_current_source_and_consumer=True,verified_current_binary_hash=True))
q.write(q.OUT/'benchmark-build.json',record)
print(json.dumps({k:record[k] for k in ['source_commit','binary_sha256','builds_verified']},indent=2))
