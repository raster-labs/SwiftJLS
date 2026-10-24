#!/usr/bin/env python3
"""Portable current-profile replay; reads archived files and writes no result claims."""
from pathlib import Path
import argparse, contextlib, gzip, hashlib, importlib.util, io, json, sys
sys.dont_write_bytecode=True
def require(c,m):
    if not c: raise RuntimeError(m)
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def load(n,p):
    s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def main():
    a=argparse.ArgumentParser();a.add_argument('--archive',type=Path,default=Path(__file__).resolve().parent);p=a.parse_args().archive.resolve()
    manifest=read(p/'manifest.json')
    for f in manifest['files']:
        path=(p/f['path']).resolve();require(path.is_relative_to(p) and sha(path)==f['sha256'],'Archive digest mismatch: '+f['path'])
        raw=path.read_bytes();payload=gzip.decompress(raw) if f.get('compression')=='gzip' else raw
        require(hashlib.sha256(payload).hexdigest()==f['uncompressed_sha256'] and len(payload)==f['uncompressed_bytes'],'Payload mismatch')
    m=load('memory_measure',p/'source/Scripts/StorageEvidence/measure-operation.py')
    runner=load('memory_runner',p/'source/Scripts/StorageEvidence/run-workspace-profiles.py')
    with contextlib.redirect_stdout(io.StringIO()):m.self_test();runner.self_test()
    matrix=read(p/'workspace/profiles/matrix.json');summary=read(p/'receipts/reconciliation-summary.json')
    require(len(matrix['cases'])==89 and len(summary['rows'])==89,'Profile count')
    expected={x['case']:x for x in summary['rows']};counts={};owned=0
    baselines=read(p/'comparison/candidate004-groups.json')
    for name,args in matrix['cases']:
        d=p/'workspace/profiles'/name;report=read(d/'operation.json');raw=d/'allocations.gz'
        with gzip.open(raw,'rt') as f:actual=m.replay(f.readlines())
        require(actual=={k:v for k,v in report.items() if k not in ['revision','profile_sha256']},name+': raw replay')
        runner.verify_operation_report(name,args[0],report,matrix['revision'],raw)
        commands=read(d/'commands.json');trace=read(d/'summary.json')
        require(len(commands)==3 and all(c['exit_code']==0 for c in commands),name+': commands')
        require(trace['binary_sha256']==summary['workspace_binary_sha256'] and trace['commands']==commands,name+': binary/command identity')
        require(sha(raw)==expected[name]['raw_sha256'] and sha(d/'operation.json')==expected[name]['report_sha256'],name+': report binding')
        require(report['pure_algorithm_workspace_complete'] is False and report['stack_peak_bytes'] is None and report['allocator_overhead_bytes'] is None,'Unknowns relabelled')
        consumer=[json.loads(x) for x in (d/'consumer.stdout').read_text().splitlines() if x.startswith('{')]
        require(len(consumer)==1 and consumer[0]['samples_verified'] is True and consumer[0]['operation']==args[0],name+': samples')
        baseline=baselines[name]
        require(baseline['original_report_sha256']==expected[name]['candidate004_report_sha256'],name+': baseline identity')
        for group in set(report['groups'])|set(baseline['groups']):
            new=report['groups'].get(group,{});old=baseline['groups'].get(group,{})
            delta={k:new.get(k,0)-old.get(k,0) for k in set(new)|set(old)}
            require(delta==expected[name]['candidate004_group_deltas'][group],name+': baseline delta')
        counts[args[0]]=counts.get(args[0],0)+1;owned+=report['groups'].get('owned_pixel_buffer',{}).get('phase_allocation_calls',0)
    require(counts==dict(encode=20,owned=23,into=23,inspect=23) and owned==23,'Pixel/operation totals')
    copy=read(p/'receipts/copy-stdout.log');pairs={}
    require(copy['self_test'] is True and len(copy['cases'])==20,'Copy self-test/count')
    for row in copy['cases']:
        key=(row['fixture'],row['near'],row['interleave']);modes=pairs.setdefault(key,set());require(row['injected'] not in modes,'Duplicate copy row');modes.add(row['injected'])
        require(row['maximum_sample_error']<=row['near'] and row['observed_source_copy_bytes']==(row['source_capacity'] if row['injected'] else 0),'Copy verification')
    require(len(pairs)==10 and all(x=={False,True} for x in pairs.values()),'Copy pairing')
    print(json.dumps(dict(status='replayed',profiles=89,copy_rows=20,owned_pixel_allocations=23,peakWorkspaceBytes=None,universal_stack_allocator_peak_known=False)))
if __name__=='__main__':main()
