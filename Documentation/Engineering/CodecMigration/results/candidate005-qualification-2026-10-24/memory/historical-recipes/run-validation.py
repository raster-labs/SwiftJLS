#!/usr/bin/env python3
"""Prepared candidate005 Linux evidence; never invoked without a released window."""
from pathlib import Path
import argparse, collections, contextlib, datetime, gzip, hashlib, importlib.util
import io, json, shutil, subprocess, sys, time, traceback
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
LIVE = Path('/Users/pushparaj/projects/SwiftJLS')
OLD = Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261023/candidate004-linux-validation-002')
IMAGE = 'sha256:31d14d727f4451f25e29bac9c42563a098c39ac66415e8bad970f48038e38aca'
TARBALL = Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/oracles/libunwind-1.8.3/libunwind-1.8.3.tar.gz')
TAR_HASH = 'be30d910e67f58d82e753231f1357f326a1a088acf126b21ff77e60aab19b90b'
CLASSIFIER = 'a1d97dca4c65b025992a5fed0a259ad2e76a412c6e202b293ccf70c80b5799d6'
IGNORED = {'.build', '.git', '__pycache__', '.DS_Store'}
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def now(): return datetime.datetime.now(datetime.timezone.utc).isoformat()
def require(c, m):
    if not c: raise RuntimeError(m)
def write(name, value):
    p = ROOT / name
    with p.open('x') as f: json.dump(value, f, indent=2, sort_keys=True); f.write('\n')
def files(root):
    result = {}
    for name in ['Sources', 'Tests', 'Scripts', 'Examples', 'Package.swift', 'VERSION']:
        p = root / name
        for q in ([p] if p.is_file() else sorted(p.rglob('*'))):
            if q.is_file() and not any(x in IGNORED for x in q.relative_to(root).parts):
                result[str(q.relative_to(root))] = sha(q)
    return result
def bind(args):
    require(not (ROOT / 'bound-plan.json').exists(), 'Already bound; preserve this attempt.')
    receipt = Path(args.receipt).resolve()
    require(sha(receipt) == args.receipt_sha256, 'Receipt digest mismatch')
    r = read(receipt); pins_path = receipt.parent / 'all-source-pins.json'; pins = read(pins_path)
    require(sha(pins_path) == r['all_source_pins_sha256'], 'Receipt does not bind source pins')
    actual = files(LIVE)
    require(actual == pins, 'Live source/fixture/probe/tool inventory differs from receipt pins')
    for key, prefix in [('swiftjls_file_sha256', 'Sources/SwiftJLS/'), ('test_file_sha256', 'Tests/')]:
        require({k:v for k,v in pins.items() if k.startswith(prefix) and k.endswith('.swift')} == r[key], key + ' mismatch')
    require(pins['Scripts/StorageEvidence/measure-operation.py'] == CLASSIFIER, 'Unexpected classifier; review rather than widen it')
    require(sha(TARBALL) == TAR_HASH, 'Pinned libunwind tarball changed')
    require(subprocess.check_output(['git','rev-parse','HEAD'],cwd=LIVE,text=True).strip() == r['base_head'], 'Base HEAD changed')
    snapshot = ROOT / 'SwiftJLS'; snapshot.mkdir(exist_ok=False)
    for rel, digest in pins.items():
        p = Path(rel)
        require(not p.is_absolute() and '..' not in p.parts, 'Nonrelative source pin')
        out = snapshot / p; out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(LIVE / p, out); require(sha(out) == digest, 'Snapshot copy changed: ' + rel)
    revision = str(r['candidate']) + ':receipt:' + args.receipt_sha256
    commands = {}
    originals = {}
    for mode, out_name in [('workspace','workspace89'), ('copy','copy-probe20')]:
        source = OLD / (mode + '-command.json'); originals[source.name] = sha(source)
        cmd = read(source)
        for i, value in enumerate(cmd):
            if value.startswith('type=bind,') and ',target=/SwiftJLS,' in value:
                cmd[i] = 'type=bind,source=' + str(snapshot) + ',target=/SwiftJLS,readonly'
            elif value.startswith('type=bind,source=' + str(OLD) + '/'):
                cmd[i] = value.replace(str(OLD), str(ROOT))
            elif value.startswith('WORKSPACE_REVISION_ID='):
                cmd[i] = 'WORKSPACE_REVISION_ID=' + revision
        require(IMAGE in cmd, 'Prior Docker image changed')
        commands[mode] = cmd
    write('bound-plan.json', dict(status='bound; not executed', utc=now(), source_receipt=str(receipt),
        source_receipt_sha256=args.receipt_sha256, all_source_pins=str(pins_path),
        all_source_pins_sha256=sha(pins_path), source_files=pins, base_head=r['base_head'],
        snapshot=str(snapshot), revision=revision, docker_image=IMAGE, commands=commands,
        inherited_command_sha256=originals, driver_sha256=sha(__file__),
        baseline_matrix_sha256=sha(OLD/'workspace89-corrected-002/profiles/matrix.json'),
        scope='Requested heap and scoped copy controls; no RSS or universal allocator/stack inference'))
    print('Bound only: ' + str(ROOT/'bound-plan.json'))
def guard(p):
    require(sha(__file__) == p['driver_sha256'], 'Driver changed after binding')
    require(sha(p['source_receipt']) == p['source_receipt_sha256'], 'Receipt changed')
    require(sha(p['all_source_pins']) == p['all_source_pins_sha256'], 'Pins changed')
    require(files(LIVE) == files(Path(p['snapshot'])) == p['source_files'], 'Frozen/live inputs changed')
    require(sha(TARBALL) == TAR_HASH, 'libunwind tarball changed')
    require(sha(OLD/'workspace89-corrected-002/profiles/matrix.json') == p['baseline_matrix_sha256'], 'Baseline matrix changed')
    return dict(utc=now(), files=len(p['source_files']), source_receipt_sha256=p['source_receipt_sha256'], passed=True)
def run(args):
    p = read(ROOT/'bound-plan.json'); pre = guard(p)
    write('execution-start.json', dict(utc=now(), authorisation_note=args.authorisation_note,
        plan_sha256=sha(ROOT/'bound-plan.json'), guard=pre))
    docker = ['/Users/pushparaj/.local/bin/docker', '--context', 'colima']
    # No process arguments or unrelated service credentials are collected.
    for name, argv in [('image', docker+['image','inspect',IMAGE]),
                       ('containers-before', docker+['ps','--format','{{.ID}}\t{{.Image}}\t{{.Names}}\t{{.State}}'])]:
        c=subprocess.run(argv,capture_output=True,text=True)
        write(name+'.json',dict(command=argv,exit_code=c.returncode,stdout=c.stdout,stderr=c.stderr))
        require(c.returncode == 0, name+' failed')
    for mode, dirname, product in [('workspace','workspace89','WorkspaceProbe'), ('copy','copy-probe20','CopyProbe')]:
        (ROOT/dirname).mkdir(exist_ok=False); started=now(); clock=time.monotonic()
        with (ROOT/(mode+'-stdout.log')).open('xb') as out, (ROOT/(mode+'-stderr.log')).open('xb') as err:
            c=subprocess.run(p['commands'][mode],stdout=out,stderr=err)
        binary=ROOT/dirname/product
        write(mode+'-receipt.json', dict(command=p['commands'][mode],exit_code=c.returncode,
            started_utc=started,finished_utc=now(),seconds=time.monotonic()-clock,
            source_receipt_sha256=p['source_receipt_sha256'],
            binary=str(binary),binary_sha256=sha(binary) if binary.exists() else None,
            stdout_sha256=sha(ROOT/(mode+'-stdout.log')),stderr_sha256=sha(ROOT/(mode+'-stderr.log'))))
        require(c.returncode == 0, mode+' failed; preserve logs, do not overwrite')
    write('execution-complete.json',dict(utc=now(),status='collection completed; reconciliation pending',guard=guard(p)))
def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def reconcile(args):
    p=read(ROOT/'bound-plan.json'); guard(p)
    m=load('measure',Path(p['snapshot'])/'Scripts/StorageEvidence/measure-operation.py')
    runner=load('runner',Path(p['snapshot'])/'Scripts/StorageEvidence/run-workspace-profiles.py')
    controls=io.StringIO()
    with contextlib.redirect_stdout(controls): m.self_test(); runner.self_test()
    w=read(ROOT/'workspace-receipt.json'); c=read(ROOT/'copy-receipt.json')
    require(w['exit_code'] == c['exit_code'] == 0, 'Collection command failed')
    for r in [w,c]: require(sha(r['binary']) == r['binary_sha256'], 'Probe binary changed')
    folder=ROOT/'workspace89/profiles'; matrix=read(folder/'matrix.json')
    require(matrix['revision'] == p['revision'], 'Wrong measured revision')
    cases=matrix['cases'];require(len(cases)==89 and cases==read(OLD/'workspace89-corrected-002/profiles/matrix.json')['cases'], 'Matrix changed')
    require({n for n,a in cases} == {d.name for d in folder.iterdir() if d.is_dir()}, 'Missing/extra profile')
    counts=collections.Counter(); rows=[]; totals=collections.Counter()
    for name, argv in cases:
        d=folder/name; report=read(d/'operation.json'); summary=read(d/'summary.json'); raw=d/'allocations.gz'; commands=read(d/'commands.json')
        require(summary['profile_sha256']==report['profile_sha256']==sha(raw), name+': raw digest')
        require(summary['binary_sha256']==w['binary_sha256'] and summary['commands']==commands, name+': provenance')
        require(len(commands)==3 and all(x['exit_code']==0 for x in commands), name+': command failure')
        require(commands[1]['command'][4:]==argv, name+': arguments')
        with gzip.open(raw,'rt') as f: replay=m.replay(f.readlines())
        require(replay=={k:v for k,v in report.items() if k not in ['revision','profile_sha256']}, name+': replay mismatch')
        runner.verify_operation_report(name,argv[0],report,p['revision'],raw)
        require(report['pure_algorithm_workspace_complete'] is False and report['stack_peak_bytes'] is None and report['allocator_overhead_bytes'] is None, 'Unknowns relabelled')
        consumer=[json.loads(line) for line in (d/'consumer.stdout').read_text().splitlines() if line.startswith('{')]
        require(len(consumer)==1 and consumer[0]['samples_verified'] is True and consumer[0]['operation']==argv[0], name+': verification')
        previous=read(OLD/'workspace89-corrected-002/profiles'/name/'operation.json')
        groups={g:{k:report['groups'].get(g,{}).get(k,0)-previous['groups'].get(g,{}).get(k,0)
            for k in set(report['groups'].get(g,{}))|set(previous['groups'].get(g,{}))}
            for g in set(report['groups'])|set(previous['groups'])}
        for g, value in report['groups'].items(): totals[g]+=value['phase_allocation_calls']
        counts[argv[0]]+=1
        rows.append(dict(case=name,args=argv,raw_sha256=sha(raw),report_sha256=sha(d/'operation.json'),
            phase_requested_heap_peak_bytes=report['phase_total_requested_heap_peak_bytes'],
            baseline_requested_heap_bytes=report['baseline_total_requested_heap_bytes'],
            peak_above_baseline_bytes=report['phase_total_peak_above_baseline_bytes'],
            algorithm_state=report['groups'].get('algorithm_state',{}),
            candidate004_report_sha256=sha(OLD/'workspace89-corrected-002/profiles'/name/'operation.json'),
            candidate004_group_deltas=groups))
    require(counts==dict(encode=20,owned=23,into=23,inspect=23) and totals['owned_pixel_buffer']==23 and totals['unattributed_codec']==0, 'Operation/copy counts')
    copy=read(ROOT/'copy-stdout.log');require(copy['self_test'] is True and len(copy['cases'])==20, 'Copy controls absent')
    pairs={}
    for row in copy['cases']:
        key=(row['fixture'],row['near'],row['interleave']); modes=pairs.setdefault(key,{})
        require(row['injected'] not in modes, 'Duplicate copy row');modes[row['injected']]=row
        require(row['maximum_sample_error']<=row['near'], 'Copy sample error')
        require(row['observed_source_copy_bytes']==(row['source_capacity'] if row['injected'] else 0), 'Copy count mismatch')
    require(len(pairs)==10 and all(set(m)=={False,True} for m in pairs.values()), 'Missing positive/normal pair')
    write('reconciliation-summary.json',dict(status='scoped requested-heap and copy evidence reconciled',
        utc=now(),source_receipt_sha256=p['source_receipt_sha256'],profiles=89,commands=267,operations=dict(counts),
        phase_allocation_calls_by_category=dict(totals),owned_pixel_calls=23,other_pixel_calls=0,
        copy_rows=20,normal_zero_copy_rows=10,injected_source_capacity_rows=10,
        classifier_sha256=CLASSIFIER,workspace_binary_sha256=w['binary_sha256'],copy_binary_sha256=c['binary_sha256'],
        controls_output=controls.getvalue(),postflight=guard(p),rows=rows,
        measured_scope='Ordinary release Linux ARM64 marked-operation requested heap; category peaks cannot be summed.',
        limitations=['No allocator usable-size, pure algorithm stack, universal input/concurrency or Apple RSS claim.',
          'Copy instrumentation cannot observe inlined copies. Source and allocation evidence remain necessary.',
          'peakWorkspaceBytes stays nil; physical testing and milestone5 remain pending.']))
    print('Reconciled 89 profiles and 20 copy rows; unknown totals remain unknown.')
if __name__=='__main__':
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest='mode',required=True)
    b=sub.add_parser('bind');b.add_argument('--receipt',required=True);b.add_argument('--receipt-sha256',required=True)
    r=sub.add_parser('run');r.add_argument('--authorisation-note',required=True)
    sub.add_parser('reconcile'); args=parser.parse_args()
    try: {'bind':bind,'run':run,'reconcile':reconcile}[args.mode](args)
    except Exception as e:
        failure=ROOT/('failure-'+args.mode+'-'+datetime.datetime.now().strftime('%Y%m%dT%H%M%S%f')+'.json')
        failure.write_text(json.dumps(dict(utc=now(),error=repr(e),traceback=traceback.format_exc()),indent=2)+'\n'); raise
