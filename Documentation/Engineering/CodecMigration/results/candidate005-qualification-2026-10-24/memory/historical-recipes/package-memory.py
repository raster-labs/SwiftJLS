#!/usr/bin/env python3
"""Prepare one immutable memory evidence component, only after timing release.

No benchmark/build/replay is launched. Source and raw-profile hashing is substantial;
do not run this script in a timing window. Existing outputs are never overwritten.
"""
from pathlib import Path
import argparse, datetime, gzip, hashlib, importlib.util, json, re, shutil, subprocess, sys
sys.dont_write_bytecode=True
A24=Path(__file__).resolve().parent.parent
RUN=A24/'linux-workspace-candidate005'
REPO=Path('/Users/pushparaj/projects/SwiftJLS')
OLD=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/candidate004-linux-validation-002')
HISTORY=REPO/'Documentation/Engineering/CodecMigration/results/candidate004-qualification-2026-10-23.json'
HISTORY_SHA='7117530e4b3a99685f1755f35a6a6c493c906eb2f08d481044c13533654e966d'
PROFILE_FILES={'version.stderr','summary.json','allocation-stacks.txt','consumer.stderr','analysis.stderr',
 'analysis.stdout','analysis-demangled.txt','consumer.stdout','version.stdout','commands.json','operation.json','sizes.tsv','allocations.gz'}
FIXTURES={'p12-17x13-noise.jls','n3-p12-17x13-noise.jls','c3-i2-p12-n0-17x13-noise.jls',
 'hp1-c3-i2-p8-n0-17x13-noise.jls','map-p8-c3-i2-w2-n0.jls','subsampled-zero-n0.jls',
 'map-p16-c3-i0-w1-n0.jls','extended-p12-65537x2.jls'}
def require(c,m):
    if not c: raise RuntimeError(m)
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha(p):return sha_bytes(p.read_bytes())
def read(p):return json.loads(p.read_text())
def payload(path,data):return gzip.decompress(data) if path.suffix=='.gz' else data
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--released-window-note',required=True);a=parser.parse_args()
    output=a.output.resolve();require(output.is_relative_to(A24) and not output.exists(),'Use a fresh external A24 output directory')
    require(sha(HISTORY)==HISTORY_SHA,'Historical manifest changed; do not rewrite or relabel it')
    plan=read(RUN/'bound-plan.json');completion=read(RUN/'completion.json');summary=read(RUN/'reconciliation-summary.json')
    require(completion['status']=='completed and independently reconciled' and completion['profiles']==89 and completion['copy_rows']==20,'Incomplete evidence')
    require(sha(RUN/'reconciliation-summary.json')==completion['reconciliation_sha256'],'Reconciliation changed')
    spec=importlib.util.spec_from_file_location('source_guard',RUN/'run-validation.py');driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
    before=driver.guard(plan)
    receipt_path=Path(plan['source_receipt']);receipt=read(receipt_path)
    require(sha(receipt_path)==plan['source_receipt_sha256']==completion['source_receipt_sha256'],'Selected-source mismatch')
    validations=receipt['validation']; modes={x['label']:x for x in validations if x['label'] in {'release','debug','asan','tsan'}}
    require(set(modes)=={'release','debug','asan','tsan'},'Host modes missing')
    require(all(x['exit_code']==0 and x['tests']>0 and x['failures']==x['errors']==x['skipped']==0 for x in modes.values()),'Host validation failed')
    require(len({x['tests'] for x in modes.values()})==1,'Host counts differ')
    output.mkdir(parents=True,exist_ok=False);entries=[];source_snapshot=Path(plan['snapshot'])
    def add(source,relative,derivative=None,reason=None):
        relative=Path(relative);require(not relative.is_absolute() and '..' not in relative.parts,'Unsafe archive path')
        require(not any(x in {'.build','__pycache__','build','copy-probe-build','libunwind-183-prefix'} for x in relative.parts),'Build/cache path selected')
        original=source.read_bytes();data=original if derivative is None else derivative
        plain=payload(relative,data)
        if derivative is None and source.name in {'analysis.stdout','analysis-demangled.txt','allocation-stacks.txt','sizes.tsv'} and len(data)>32768:
            relative=Path(str(relative)+'.gz');data=gzip.compress(data,mtime=0)
        # Known codec-source/profiler files only. Fail closed on credential-shaped
        # content; do not auto-redact measurements to make a scan pass.
        for pattern in [rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b',rb'\bgithub_pat_[A-Za-z0-9_]{30,}\b',rb'Bearer [A-Za-z0-9._~+/-]{20,}']:
            require(re.search(pattern,plain) is None,'Sensitive-content candidate: '+str(relative))
        dest=output/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(data)
        entry=dict(path=str(relative),sha256=sha_bytes(data),bytes=len(data),uncompressed_sha256=sha_bytes(plain),uncompressed_bytes=len(plain))
        if relative.suffix=='.gz':entry['compression']='gzip'
        if derivative is not None:entry.update(redacted_public_derivative=True,local_original_sha256=sha_bytes(original),local_original_bytes=len(original),derivation=reason)
        entries.append(entry)
    # Exact original recipes retain local paths as historical provenance; only
    # replay-workspace.py below is advertised as a portable reproduction command.
    for name in ['bound-plan.json','workspace-receipt.json','copy-receipt.json','execution-start.json','execution-complete.json',
                 'completion.json','reconciliation-summary.json','workspace-stdout.log','workspace-stderr.log','copy-stdout.log','copy-stderr.log']:
        add(RUN/name,'receipts/'+name)
    add(RUN/'run-validation.py','historical-recipes/run-validation.py')
    add(receipt_path,'source-identity/prepare-and-validate-receipt.json')
    add(Path(plan['all_source_pins']),'source-identity/all-source-pins.json')
    # Derivatives omit unrelated container/service identifiers and image Env.
    # Originals remain local and their hashes/byte sizes stay in the manifest.
    containers=read(RUN/'containers-before.json');lines=[x for x in containers['stdout'].splitlines() if x]
    safe=dict(exit_code=containers['exit_code'],running_container_count=len(lines),scope='Shared services remained running; unrelated service identities omitted.')
    add(RUN/'containers-before.json','receipts/containers-before.public.json',(json.dumps(safe,indent=2)+'\n').encode(),'Only count/exit preserved; unrelated service identifiers omitted. No timing or allocation measurement fields existed here.')
    image=read(RUN/'image.json');inspected=json.loads(image['stdout']);require(len(inspected)==1,'Unexpected image inventory')
    safe=dict(exit_code=image['exit_code'],image={k:inspected[0].get(k) for k in ['Id','RepoDigests','Architecture','Os']})
    require(safe['image']['Id']==plan['docker_image'],'Image identity mismatch')
    add(RUN/'image.json','receipts/image.public.json',(json.dumps(safe,indent=2)+'\n').encode(),'Preserved image identity/platform; unused image configuration/environment omitted.')
    for rel,digest in plan['source_files'].items():
        selected=(rel.startswith('Sources/') or rel.startswith(('Examples/WorkspaceProbe/','Examples/CopyProbe/','Scripts/StorageEvidence/'))
          or rel in {'Package.swift','VERSION','Tests/SwiftJLSTests/WorkspaceAdmissionTests.swift','Tests/SwiftJLSTests/OwnedAdmissionTests.swift'}
          or rel in {'Tests/SwiftJLSTests/Fixtures/'+n for n in FIXTURES})
        if selected:
            require(sha(source_snapshot/rel)==digest,'Snapshot source changed: '+rel);add(source_snapshot/rel,'source/'+rel)
    for mode,record in modes.items():
        for suffix,key in [('stdout','stdout_sha256'),('stderr','stderr_sha256'),('xml','xml_sha256')]:
            path=receipt_path.parent/(mode+'.'+suffix);require(sha(path)==record[key],'Host log changed');add(path,'host/'+path.name)
    for name in ['candidate005-memory-inventory.md','candidate005-memory-inventory.json','candidate005-memory-completion-draft.md',
                 'workspace-admission-design.md','workspace-admission-implementation.json']:
        add(A24/name,'review/'+name)
    add(RUN/'RESULTS.md','RESULTS.md')
    for filename in ['libunwind-183-configure.log','libunwind-183-make.log','libunwind-183-install.log','libunwind-183-ldd.txt']:
        add(RUN/'workspace89'/filename,'workspace/toolchain/'+filename)
    profiles=RUN/'workspace89/profiles';matrix=read(profiles/'matrix.json');require(len(matrix['cases'])==89,'Matrix changed')
    add(profiles/'matrix.json','workspace/profiles/matrix.json');baselines={};original_baselines=[]
    row_map={x['case']:x for x in summary['rows']}
    for name,args in matrix['cases']:
        folder=profiles/name;require({x.name for x in folder.iterdir() if x.is_file()}==PROFILE_FILES,'Unexpected profile files: '+name)
        require(sha(folder/'allocations.gz')==row_map[name]['raw_sha256'] and sha(folder/'operation.json')==row_map[name]['report_sha256'],'Replayed profile changed')
        for child in sorted(PROFILE_FILES):add(folder/child,'workspace/profiles/'+name+'/'+child)
        old=OLD/'workspace89-corrected-002/profiles'/name/'operation.json';old_hash=sha(old)
        require(old_hash==row_map[name]['candidate004_report_sha256'],'Baseline changed')
        baselines[name]=dict(groups=read(old)['groups'],original_report_sha256=old_hash)
        original_baselines.append(dict(case=name,sha256=old_hash,bytes=old.stat().st_size))
    generated=output/'comparison/candidate004-groups.json';generated.parent.mkdir(parents=True)
    data=(json.dumps(baselines,indent=2,sort_keys=True)+'\n').encode();generated.write_bytes(data)
    entries.append(dict(path='comparison/candidate004-groups.json',sha256=sha_bytes(data),bytes=len(data),uncompressed_sha256=sha_bytes(data),uncompressed_bytes=len(data),derived_metric_subset=True,source_reports=original_baselines,derivation='All category metric fields retained for delta replay; historical allocation stacks remain in the immutable candidate004 archive.'))
    add(Path(__file__).with_name('replay-workspace.py'),'replay-workspace.py');add(Path(__file__),'historical-recipes/package-memory.py')
    after=driver.guard(plan);require(sha(HISTORY)==HISTORY_SHA,'Historical manifest changed during packaging')
    manifest=dict(schema_version=1,scope='candidate005 memory evidence component; no RSS acceptance or milestone4 completion',
        generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),released_window_note=a.released_window_note,
        source_receipt_sha256=plan['source_receipt_sha256'],source_base_head=plan['base_head'],selected_source_commit=None,
        current_checkout_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
        source_identity='Measured/validated file hashes; base/current HEAD alone is not claimed as the candidate source.',
        historical_anchor=dict(path=str(HISTORY.relative_to(REPO)),sha256=HISTORY_SHA,immutable=True),
        source_guard_before=before,source_guard_after=after,host_tests_per_mode=next(iter(modes.values()))['tests'],
        profiles=89,copy_rows=20,owned_pixel_allocations=23,other_owned_pixel_allocations=0,
        peakWorkspaceBytes=None,pure_algorithm_workspace_complete=False,rss_status='separate experiment/disposition required',
        reproduction_command='python3 replay-workspace.py --archive .',
        historical_recipes='Absolute local collection commands retained as provenance; not advertised as portable.',
        fixture_scope='Eight fixtures required by WorkspaceProbe89/CopyProbe20 are included. Full host-suite reproduction uses a repository checkout matching all-source-pins.json.',
        excluded=['compiled binaries','build/cache directories','private libunwind install tree','unrelated service identifiers','unused image configuration/environment'],
        originals='All original files remain local and unchanged; public derivatives record original hashes.',
        file_count=len(entries),stored_bytes=sum(x['bytes'] for x in entries),uncompressed_bytes=sum(x['uncompressed_bytes'] for x in entries),files=entries)
    (output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status='packaged; independent portable replay/privacy audit still required',output=str(output),files=len(entries),manifest_sha256=sha(output/'manifest.json'))))
if __name__=='__main__':main()
