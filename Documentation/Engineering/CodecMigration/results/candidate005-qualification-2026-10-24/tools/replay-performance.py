#!/usr/bin/env python3
"""Portable candidate005 raw replay; --bootstrap additionally repeats frozen 50k analyses."""
from pathlib import Path
import argparse, gzip, hashlib, importlib.util, json, subprocess, sys, tempfile
sys.dont_write_bytecode=True
def require(c,m):
    if not c:raise RuntimeError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--archive',type=Path,required=True);p.add_argument('--bootstrap',action='store_true');a=p.parse_args()
    root=a.archive.resolve();manifest=json.loads((root.parent/(root.name+'.json')).read_text())
    entries={x['logical_path']:x for x in manifest['files']}
    def data(logical):
        e=entries[logical];path=(root.parent/e['path']).resolve();require(path.is_relative_to(root),'Archive path escape')
        stored=path.read_bytes();require(sha(stored)==e['sha256'],'Stored hash mismatch '+logical)
        raw=gzip.decompress(stored) if e.get('compression')=='gzip' else stored
        require(sha(raw)==e['uncompressed_sha256'],'Decompressed hash mismatch '+logical);return raw
    def identity(logical):
        e=entries[logical];return e.get('local_original_sha256',e['uncompressed_sha256'])
    def read(logical):return json.loads(data(logical))
    audit_path=root/'tools/final-candidate005-audit.py'
    require(sha(audit_path.read_bytes())==entries['tools/final-candidate005-audit.py']['sha256'],'Audit helper changed')
    spec=importlib.util.spec_from_file_location('frozen_audit',audit_path);audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)
    mixed_path=root/'tools/final-candidate005-audit-mixed-packages.py'
    mixed=None
    if 'package_bindings' in manifest:
        require(sha(audit_path.read_bytes())==manifest['base_audit_sha256'],'Manifest base audit identity')
        require(sha(mixed_path.read_bytes())==manifest['independent_audit_helper_sha256'],'Manifest mixed audit identity')
        spec=importlib.util.spec_from_file_location('mixed_audit',mixed_path);mixed=importlib.util.module_from_spec(spec);spec.loader.exec_module(mixed)
    results={}
    with tempfile.TemporaryDirectory(prefix='swiftjls005-public-replay-') as temporary:
        temp=Path(temporary)
        for kind,name in manifest['final_runs'].items():
            base=manifest.get('final_run_paths',{}).get(kind,'performance/runs/'+name)+'/';out=temp/name;out.mkdir()
            config=manifest.get('package_bindings',{}).get(kind)
            package_temp=None
            if config:
                require(mixed is not None and config['freeze_sha256']==mixed.accepted_freeze(kind),'Accepted original/amended package scope '+kind)
                package_base=config['archive_prefix']+'/'
                require(sha(data(package_base+'campaign-freeze.json'))==config['freeze_sha256'],'Per-kind frozen package identity '+kind)
                freeze=read(package_base+'campaign-freeze.json')
                for rel,digest in freeze['files'].items():
                    data(package_base+rel)
                    require(identity(package_base+rel)==digest,'Package input receipt binding '+kind+'/'+rel)
                require(sha(data(base+'campaign-freeze.json'))==config['freeze_sha256'],'Measured run package identity '+kind)
                names={'frozen_schedule.json':'schedules/'+('short1032-3arms' if kind=='short' else 'larger15-guard' if kind=='larger' else 'rss528-4arms')+'-005.json',
                       'campaign_identity.py':'campaign_identity.py','identity.json':'identity.json'}
                if kind=='rss':names.update({x:x for x in ['rss528_runner.py','rss528_analyse.py','diag72_runner.py']})
                else:
                    names.update({'frozen_runner.py':'short1032_runner.py' if kind=='short' else 'larger15_runner.py','frozen_shared_helper.py':'diag72_runner.py'})
                    names.update({'frozen_analyse.py':'short1032_analyse.py'} if kind=='short' else {'frozen_larger_guard_plan.json':'larger-guard-plan.json'})
                if kind!='short':names['persistent-service-identities.json']='persistent-service-identities.json'
                for copied,original in names.items():
                    data(base+copied);data(package_base+original)
                    require(identity(base+copied)==identity(package_base+original),'Measured helper/analyser/identity binding '+kind+'/'+copied)
                package_temp=temp/(kind+'-package');package_temp.mkdir()
                if kind!='short':
                    identities=data(package_base+'persistent-service-identities.json')
                    require(data(base+'persistent-service-identities.json')==identities,'Measured selected identities differ from package')
                    (package_temp/'persistent-service-identities.json').write_bytes(identities)

            needed=['raw.jsonl','events.jsonl','conditions.jsonl','environment.json','complete.json','summary.json','frozen_schedule.json']
            if kind=='short':needed+=['bootstrap-metadata.json','frozen_analyse.py']
            if kind=='rss':needed+=['rss528_analyse.py']
            for n in needed:(out/n).write_bytes(data(base+n))
            complete=read(base+'complete.json');require(complete['completed'] is True,'Incomplete final run')
            for n,key in [('raw.jsonl','raw_jsonl_sha256'),('events.jsonl','events_jsonl_sha256'),('conditions.jsonl','conditions_jsonl_sha256'),('summary.json','summary_json_sha256')]:
                expected=complete['hashes'][n] if kind=='rss' else complete[key]
                require(identity(base+n)==expected,'Original receipt binding '+n)
            raw=[json.loads(x) for x in (out/'raw.jsonl').read_text().splitlines()]
            events=[json.loads(x) for x in (out/'events.jsonl').read_text().splitlines()]
            schedule=read(base+'frozen_schedule.json');summary=read(base+'summary.json')
            counts=audit.counts_and_events(kind,out,schedule,raw,events)
            checks=(audit.short_metrics if kind=='short' else audit.larger_metrics if kind=='larger' else audit.rss_metrics)(raw,summary)
            conditions=audit.conditions_review(out)
            service_review=None
            if config and kind!='short':
                require(mixed is not None,'Selected-service replay helper absent')
                service_review=mixed.selected_identities_review(out,package_temp)
            if a.bootstrap and kind in {'short','rss'}:
                replay=temp/(kind+'-bootstrap');replay.mkdir()
                if kind=='short':
                    (replay/'raw.jsonl').symlink_to(out/'raw.jsonl')
                    command=[sys.executable,str(out/'frozen_analyse.py'),'--output',str(replay),'--schedule',str(out/'frozen_schedule.json')]
                else:command=[sys.executable,str(out/'rss528_analyse.py'),'--raw',str(out/'raw.jsonl'),'--output',str(replay/'summary.json')]
                subprocess.run(command,check=True)
                require(json.loads((replay/'summary.json').read_text())==summary,'Frozen bootstrap summary mismatch')
                if kind=='short':require(json.loads((replay/'bootstrap-metadata.json').read_text())==read(base+'bootstrap-metadata.json'),'Frozen bootstrap metadata mismatch')
            results[kind]={'processes':counts['records'],'raw_events_and_metrics_recomputed':True,'condition_records':conditions['condition_records'],'bootstrap_recomputed':a.bootstrap and kind in {'short','rss'},'results':checks,'package_binding':config,'selected_service_identity_conditions':service_review}
    print(json.dumps({'scope':'Only completed archived runs replayed; no new measurements or automatic acceptance. Redacted conditions retain original receipt binding.','publication_mode':manifest['publication_mode'],'missing_measurements':manifest['missing_measurements'],'milestone4_complete':manifest['milestone4_complete'],'runs':results},indent=2))
if __name__=='__main__':main()
