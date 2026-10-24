#!/usr/bin/env python3
"""Stage then explicitly publish candidate005 evidence. NEVER run during timing."""
from pathlib import Path
import argparse,difflib,gzip,hashlib,importlib.util,json,os,re,shutil,subprocess,sys,datetime
import xml.etree.ElementTree as ET
sys.dont_write_bytecode=True
HERE=Path(__file__).resolve().parent;A24=HERE.parent;REPO=Path('/Users/pushparaj/projects/SwiftJLS')
PLAN=json.loads((HERE/'integrated-plan.json').read_text())
NAME=PLAN['archive_name'];RESULTS=REPO/'Documentation/Engineering/CodecMigration/results'
PRUNE={'.build','__pycache__','.git','binaries','build','native-payload','native-consumer-build','SwiftJLS','arm_candidate','arm_memdiag'}
PRIVATE={'vm-ssh.exp','known_hosts','ssh_config','config','id_ed25519','id_rsa','credentials.json'}
OPAQUE_OUTPUT={
 'review/controls005-rss528_runner.py.json':dict(sha256='e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',artifact_kind='Retained empty failed self-test stdout; historical JSON suffix is not a receipt',correction_record='review/controls005-preparation-correction.json',successful_control_record='review/controls005-rss528-runner-002.json'),
 'review/016-shared-service-admission/mixed-audit-self-test-original.jsonl':dict(sha256='8e7d52881cd8a6347aa564d006e7c2393b866c6007c998d51e5abcd3fd606fef',artifact_kind='Retained concatenated pretty-printed synthetic self-test stdout; historical JSONL suffix is not line-oriented JSON',correction_record='review/016-shared-service-admission/mixed-audit-correction.json',successful_control_record='review/016-shared-service-admission/mixed-audit-self-test.json')
}
EXT={'.json','.jsonl','.xml','.log','.stdout','.stderr','.txt','.md','.py','.swift','.sh','.h','.c','.1','.jls','.u16le','.patch'}
def require(c,m):
    if not c:raise RuntimeError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def file_sha(p):return sha(Path(p).read_bytes())
def read(p):return json.loads(Path(p).read_text())
def module(name,path):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
privacy=module('privacy',HERE/'publication-privacy.py')
def history_guard():
    args=['git','diff','--quiet',PLAN['base_head'],'--','Documentation/Engineering/CodecMigration/results',
      ':!Documentation/Engineering/CodecMigration/results/'+NAME,
      ':!Documentation/Engineering/CodecMigration/results/'+NAME+'.json']
    require(subprocess.run(args,cwd=REPO).returncode==0,'A historical archive changed')
    untracked=subprocess.check_output(['git','ls-files','--others','--exclude-standard','--','Documentation/Engineering/CodecMigration/results'],cwd=REPO,text=True).splitlines()
    prefix='Documentation/Engineering/CodecMigration/results/'+NAME
    require(all(x==prefix+'.json' or x.startswith(prefix+'/') for x in untracked),'Unexpected untracked historical archive content')
def source_guard():
    r=read(A24/PLAN['source_receipt']);require(file_sha(A24/PLAN['source_receipt'])==PLAN['source_receipt_sha256'],'Source receipt changed')
    pins=read(A24/PLAN['all_source_pins']);require(file_sha(A24/PLAN['all_source_pins'])==r['all_source_pins_sha256'],'Source pins changed')
    for path,digest in pins.items():require(file_sha(REPO/path)==digest,'Current source input changed: '+path)
    require(len(r['swiftjls_file_sha256'])==PLAN['expected_source_files'] and len(r['test_file_sha256'])==PLAN['expected_test_files'],'Source/test inventory count')
    require(r['declaration_counts_from_source']=={'test_declarations':157,'suite_declarations':28},'Named declaration counts')
    for b in r['binaries'].values():require(file_sha(b['path'])==b['sha256'],'Frozen candidate binary changed')
    for mode in PLAN['expected_host']['modes']:
        xml=A24/'candidate005-001'/(mode+'.xml');tests=ET.parse(xml).findall('.//testcase')
        require(len(tests)==157 and len({t.get('classname') for t in tests})==29,'Host XML counts/classes changed')
    return r,pins
def admission(partial=False):
    history_guard();receipt,pins=source_guard();missing={}
    if partial:
        short=read(A24/'short-independent-001/audit.json');reuse=read(A24/'short-independent-001/reuse-receipt.json')
        require(short['completed'] is True and reuse['completed'] is True and reuse['report_sha256']==file_sha(A24/'short-independent-001/audit.json'),'Short-only audit incomplete/unbound')
        require(short['count_and_fidelity']['records']==18576 and short['replay']['exact_replay_equal'] is True,'Short-only evidence missing')
        performance={k:short[k] for k in ['audit_script_sha256','package_freeze_sha256']};performance['runs']={'short':short}
        for kind in ['larger','rss']:
            run=A24/PLAN['performance']['final'][kind]
            require(not (run/'complete.json').exists(),'Partial fallback is only for unexecuted larger/RSS; review completed results in full mode')
            for name in ['raw.jsonl','events.jsonl']:
                require(not (run/name).exists() or (run/name).stat().st_size==0,'Partial fallback cannot silently omit measured '+kind)
            missing[kind]={'status':'not_executed','planned_run':run.name,'recorded_processes':0,'expected_processes':PLAN['performance']['expected_processes'][kind],'completion_record_present':False}
        active={'short':PLAN['performance']['final']['short']}
    else:
        performance=read(A24/PLAN['performance']['independent_audit']);active=PLAN['performance']['final']
    disposition=read(A24/PLAN['authored_disposition']);require((A24/PLAN['authored_disposition_prose']).is_file(),'Authored disposition prose absent')
    bindings=[('source_receipt_sha256',PLAN['source_receipt_sha256']),('memory_completion_sha256',file_sha(A24/'linux-workspace-candidate005/completion.json')),
      ('platform_results_sha256',file_sha(A24/'platform-candidate005/platform-results.json')),
      ('source_acceptance_sha256',file_sha(A24/'009-root-source-acceptance.json'))]
    bindings.append(('short_audit_sha256',file_sha(A24/'short-independent-001/audit.json')) if partial else ('performance_audit_sha256',file_sha(A24/PLAN['performance']['independent_audit'])))
    for key,value in bindings:
        require(disposition.get(key)==value,'Disposition does not bind '+key)
    require(isinstance(disposition.get('milestone4_complete'),bool),'Explicit milestone4 status required')
    require('physical_device_validation_status' in disposition and 'milestone5_status' in disposition,'Explicit pending scopes required')
    if partial:
        require(disposition.get('publication_mode')=='partial_checkpoint' and disposition['milestone4_complete'] is False,'Partial checkpoint cannot claim milestone4 completion')
        require(disposition.get('performance_audit_sha256') is None and set(disposition.get('pending_measurements',[]))=={'larger','rss'},'Partial disposition must explicitly retain missing measurements')
        require(isinstance(disposition.get('missing_measurement_reason'),str) and disposition['missing_measurement_reason'],'Missing-measurement reason required')
        for item in missing.values():item['reason']=disposition['missing_measurement_reason']
    require(performance.get('completed',True) is True,'Independent performance audit incomplete')
    if partial:
        require(performance['audit_script_sha256']==PLAN['performance']['base_audit_sha256'],'Short audit implementation identity')
    else:
        require(performance['completed'] is True and performance['audit_script_sha256']==PLAN['performance']['independent_audit_helper_sha256'],'Mixed audit incomplete/identity')
        require(performance['base_audit_sha256']==PLAN['performance']['base_audit_sha256'],'Mixed audit base implementation changed')
        require(file_sha(A24/PLAN['performance']['independent_audit_helper'])==performance['audit_script_sha256'],'Mixed audit helper changed')
    require(file_sha(A24/'final-candidate005-audit.py')==PLAN['performance']['base_audit_sha256'],'Base audit helper changed')
    for kind,rel in active.items():
        config=PLAN['performance']['package_by_kind'][kind];package=A24/config['directory'];freeze=read(package/'campaign-freeze.json')
        require(file_sha(package/'campaign-freeze.json')==config['freeze_sha256'],'Wrong package freeze for '+kind)
        for name,digest in freeze['files'].items():require(file_sha(package/name)==digest,'Frozen package changed: '+kind+'/'+name)
        run=A24/rel;complete=read(run/'complete.json');audit=performance['runs'][kind]
        if partial:
            require(performance['package_freeze_sha256']==config['freeze_sha256'],'Short package binding changed')
        else:
            binding=performance['packages'][kind]
            require(Path(binding['path']).resolve()==package.resolve() and binding['freeze_sha256']==config['freeze_sha256'],'Independent per-kind package binding')
            require(binding['helper_sha256']==file_sha(package/'diag72_runner.py') and binding['identity_sha256']==file_sha(package/'identity.json'),'Independent helper/identity binding')
            require(audit['package_binding']==binding and Path(audit['run']).resolve()==run.resolve(),'Independent run binding')
        require(complete['completed'] is True and complete['processes']==PLAN['performance']['expected_processes'][kind],'Incomplete final '+kind)
        for f in ['raw.jsonl','events.jsonl','conditions.jsonl','summary.json','frozen_schedule.json']:
            require(file_sha(run/f)==audit['hashes'][f],'Independent performance audit input changed: '+kind+'/'+f)
        require(file_sha(run/'campaign-freeze.json')==config['freeze_sha256'],'Run package freeze changed')
        names={'frozen_schedule.json':'schedules/'+('short1032-3arms' if kind=='short' else 'larger15-guard' if kind=='larger' else 'rss528-4arms')+'-005.json',
               'campaign_identity.py':'campaign_identity.py','identity.json':'identity.json'}
        if kind=='rss':names.update({x:x for x in ['rss528_runner.py','rss528_analyse.py','diag72_runner.py']})
        else:
            names.update({'frozen_runner.py':'short1032_runner.py' if kind=='short' else 'larger15_runner.py','frozen_shared_helper.py':'diag72_runner.py'})
            names.update({'frozen_analyse.py':'short1032_analyse.py'} if kind=='short' else {'frozen_larger_guard_plan.json':'larger-guard-plan.json'})
        if kind!='short':
            names['persistent-service-identities.json']='persistent-service-identities.json'
            require(audit['selected_service_identity_conditions']['identity_definition_sha256']==file_sha(package/'persistent-service-identities.json'),'Selected identities audit binding')
        for copied,original in names.items():require(file_sha(run/copied)==file_sha(package/original),'Frozen measured script changed')
        if kind in {'short','rss'}:require(audit['replay']['exact_replay_equal'] is True,'Independent bootstrap replay absent')
    if not partial:
        for receipt_name,preflight_name,key in [('013-root-larger003-admission.json','preflight-006.json','new_freeze_sha256'),('017-root-rss-admission.json','preflight-007.json','freeze_sha256')]:
            decision=read(A24/receipt_name)
            require(decision[key]==PLAN['performance']['package_by_kind']['larger']['freeze_sha256'] and decision['preflight_sha256']==file_sha(A24/preflight_name),'Root package/preflight admission mismatch')
        initial=read(A24/'013-root-larger003-admission.json')['independent_guard_review_sha256']
        require(initial==file_sha(A24/'016-shared-service-admission/independent-method-review-initial.json'),'Initial independent review admission binding')
        require(read(A24/'017-root-rss-admission.json')['larger_complete_sha256']==file_sha(A24/active['larger']/'complete.json'),'RSS admission larger completion binding')
    for policy,key in [('009-larger-ac-interruption-policy.json','run'),('012-larger-workload-interruption-policy.json','retained_attempt')]:
        prior=read(A24/policy);require(prior['completed_processes']==0,'Startup attempt incorrectly counted as measurement')
        for f,h in prior['preservation_hashes'].items():require(file_sha(Path(prior[key])/f)==h,'Retained zero-process attempt changed')
    prior=read(A24/'006-short1032-interruption-policy.json');require(prior['completed_processes']==468,'Interrupted run count changed')
    for f,h in prior['preservation_hashes'].items():require(file_sha(A24/PLAN['performance']['interrupted']/f)==h,'Interrupted evidence changed')
    interop=read(A24/'interop-candidate005/run-001/summary.json')
    require(interop['status']=='passed' and interop['verified_total']==990 and interop['source_receipt_sha256']==PLAN['source_receipt_sha256'],'Interop identity/status')
    require(interop['preflight']['passed'] and interop['postflight']['passed'] and all(c['exit_code']==0 for c in interop['commands']),'Interop commands/guards')
    for report in interop['reports'].values():require(file_sha(report['path'])==report['sha256'],'Interop report changed')
    for name,entry in read(A24/'interop-candidate005/run-001/encoded-inventory.json').items():
        encoded=A24/'interop-candidate005/run-001/encoded'/name
        require(file_sha(encoded)==entry['sha256'] and encoded.stat().st_size==entry['bytes'],'Interop exported stream changed')
    cli=read(A24/'cli-candidate005/process/report.json');payload=read(A24/'cli-candidate005/payload.json')
    require(cli['status']=='passed' and cli['checks']==103 and len(payload)==73,'CLI counts/status')
    ordinary=[x for x in payload if set(x)=={'args','exit','expected'}]
    pipes=[x for x in payload if set(x)=={'condition','exit'}]
    require(len(ordinary)==70 and all(x['exit']==x['expected'] for x in ordinary),'CLI payload outcome')
    require(len(pipes)==3 and {x['condition']:x['exit'] for x in pipes}=={'deadline blocked pipe':5,'cancel blocked pipe':130,'closed binary output':6},'CLI pipe control outcomes')
    platform=read(A24/'platform-candidate005/platform-results.json')
    require(platform['status'].startswith('passed') and platform['source_receipt_sha256']==PLAN['source_receipt_sha256'],'Platform source/status')
    require(platform['source_named_suite_declarations']==28,'Platform named suites')
    apple=platform['apple'];require(len(apple['sdk_builds'])==5 and apple['simulator_consumers']==5 and apple['exact_runtime']=='26.0' and apple['resource_platforms']==4 and apple['resource_frames_each']==32,'Apple platform coverage')
    native=platform['native'];require(native['architecture']=='arm64' and re.search(r'ProductVersion:\s+26\.0(?:\s|$)',native['os']) is not None,'Exact native OS')
    require(set(native['tests'])=={'release','debug','asan','tsan'},'Native modes')
    for t in native['tests'].values():require(t['declarations']==157 and t['xunit_classnames']==29 and t['failures']==t['errors']==t['skipped']==0,'Native test results')
    require(native['payload_cli_checks']==73 and native['process_cli_checks']==103 and native['resource_frames']==32 and native['runtime_consumer']=='passed','Native extra checks')
    require(native['vm_initial_final_state']=='stopped' and apple['simulator_states_restored'] is True,'Platform cleanup missing')
    if not partial:require(disposition['simulator_restoration_receipt']=='018-final-simulator-restoration/command.json','Final restoration receipt required')
    restore=A24/disposition['simulator_restoration_receipt'];require(read(restore)['exit_code']==0,'Root simulator restoration failed')
    before=read(A24/('007-simulator-pause/before.json' if partial else '015-final-benchmark-window/before.json'))['devices'];after=read(restore.parent/'after.json')['devices']
    originally_booted={d['udid'] for ds in before.values() for d in ds if d['state']=='Booted'}
    finally_booted={d['udid'] for ds in after.values() for d in ds if d['state']=='Booted'}
    require(originally_booted<=finally_booted,'Root-paused simulator state not restored')
    for rel,h in platform['artifact_sha256'].items():
        path=Path(rel);path=path if path.is_absolute() else A24/'platform-candidate005'/path
        require(file_sha(path)==h,'Platform receipt changed: '+rel)
    private_review=read(A24/'platform-candidate005/privacy-review.json')
    require(private_review['no_credential_spill_in_public_files'] is True,'Platform credential review missing')
    for rel,h in private_review['reviewed_public_file_sha256'].items():
        require(file_sha(A24/'platform-candidate005'/rel)==h,'Privacy-reviewed public artifact changed')
    redaction=private_review['redaction']
    require(file_sha(A24/'platform-candidate005'/redaction['public_relative_path'])==redaction['public_sha256'],'Platform derivative mismatch')
    return receipt,pins,disposition,active,missing
def structured_json(logical,path):
    if logical in OPAQUE_OUTPUT:
        require(file_sha(path)==OPAQUE_OUTPUT[logical]['sha256'], 'Retained historical self-test output changed')
        return False
    return path.suffix in {'.json','.jsonl'}
def tree(root):
    for base,dirs,files in os.walk(root):
        dirs[:]=[d for d in dirs if d not in PRUNE and not d.endswith(('-build','.app','.dSYM')) and not d.startswith('build-')]
        for n in sorted(files):
            p=Path(base)/n
            if n in PRIVATE or '.private.' in n or n.startswith(('id_rsa','id_ed25519')):continue
            if p.suffix in EXT and not p.is_symlink():yield p
def selection(partial=False):
    selected={}
    def add(p,logical):require(p.is_file(),'Required artifact missing: '+str(p));selected[logical]=p
    for n in PLAN['mandatory_root_records']:
        if partial and n in {'010-larger-replacement-admission.json','preflight-004.json'} and not (A24/n).exists():continue
        add(A24/n,'review/'+n)
    for p in sorted(A24.iterdir()):
        if p.is_file() and p.suffix in {'.json','.md','.py'}:add(p,'review/'+p.name)
    for completed in sorted(A24.glob('publication-stage-*-command.json')):
        record=read(completed)
        for suffix in ['stdout','stderr']:
            p=A24/(completed.name.removesuffix('-command.json')+'.'+suffix)
            if p.is_file():add(p,'review/archive-preparation/'+p.name)
    for dirname,target in [('campaigns005','performance/prior516-preparation'),('campaigns005-confirmation','performance'),('campaigns005-final-services','performance/final-services'),
      ('015-final-benchmark-window','platform/final-benchmark-window'),('018-final-simulator-restoration','platform/final-simulator-restoration'),('016-shared-service-admission','review/016-shared-service-admission'),
      ('campaign-preparation','performance/preparation'),('controls005-short1032-fullschema-synthetic','performance/synthetic1032'),
      ('007-simulator-pause','platform/simulator-pause'),('cli-candidate005','cli'),('interop-candidate005','interop'),
      ('platform-candidate005','platform'),('final-performance-audit-001','review/final-performance-audit'),
      ('short-independent-001','review/short-independent')]:
        root=A24/dirname
        if partial and dirname in {'final-performance-audit-001','018-final-simulator-restoration'} and not root.exists():continue
        require(root.is_dir(),'Required directory missing: '+dirname)
        for p in tree(root):add(p,target+'/'+str(p.relative_to(root)))
    for p in tree(A24/'010-simulator-restoration'):add(p,'platform/root-simulator-restoration/'+p.name)
    # Native payload contents contain reused executables/fixtures; retain only
    # its source-bound manifest and guest driver, never private access material.
    for n in ['manifest.json','run-native.py']:
        add(A24/'platform-candidate005/native-payload'/n,'platform/native-payload/'+n)
    for p in (A24/'candidate005-001').iterdir():
        if p.is_file() and p.suffix in EXT:add(p,'host/'+p.name)
    for name in ['final-candidate005-audit.py','final-candidate005-audit-mixed-packages.py']:
        add(A24/name,'tools/'+name)
    for name in ['replay-performance.py','publication-privacy.py','integrated-plan.json','package-candidate005.py']:
        add(HERE/name,'tools/'+name)
    historical=PLAN['unpublished_preparation']
    add(A24/historical['manifest'],'review/unpublished-stage003/manifest.json')
    require(file_sha(A24/historical['manifest'])==historical['manifest_sha256'],'Unpublished stage history changed')
    return selected
def stage(args):
    receipt,pins,disposition,active,missing=admission(args.partial_checkpoint);selected=selection(args.partial_checkpoint);pool=set()
    # Gather sensitive strings from structured host records, not executable
    # source or immutable timing/event rows. This also covers quoted error copies.
    upstream=read(A24/'platform-candidate005/privacy-review.json')['redaction']
    privacy.configure_selected_identities(read(A24/'campaigns005-final-services/persistent-service-identities.json'))
    for logical,path in selected.items():
        if structured_json(logical,path) and path.name not in {'raw.jsonl','events.jsonl'}:
            values=[json.loads(x) for x in path.read_text().splitlines()] if path.suffix=='.jsonl' else [read(path)]
            for value in values:privacy.collect_strings(value,pool)
    parent=args.stage_parent.resolve();require(parent.is_relative_to(A24),'Stage outside repository, under A24')
    output=parent/NAME;require(not output.exists() and not (parent/(NAME+'.json')).exists(),'Fresh staging path required')
    output.mkdir(parents=True);entries=[];memory=output/'memory'
    component=PLAN['memory_component'];memory_source=A24/component['directory']
    require(file_sha(memory_source/'manifest.json')==component['manifest_sha256'],'Memory component manifest changed')
    require(file_sha(A24/component['replay_receipt'])==component['replay_receipt_sha256'],'Memory replay receipt changed')
    replay=read(A24/component['replay_receipt']);require(replay['replay_exit_code']==0 and replay['manifest_sha256']==component['manifest_sha256'],'Memory replay not bound')
    for f in read(memory_source/'manifest.json')['files']:
        require(file_sha(memory_source/f['path'])==f['sha256'],'Memory component artifact changed')
    shutil.copytree(memory_source,memory)
    def add_bytes(logical,data,original=None,reason=None,compress=False):
        require(not Path(logical).is_absolute() and '..' not in Path(logical).parts,'Unsafe logical path')
        require(privacy.SECRET.search(data) is None,'Credential-shaped content requires manual review: '+logical)
        stored=gzip.compress(data,mtime=0) if compress else data;relative=logical+('.gz' if compress else '')
        dest=output/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open('xb') as f:f.write(stored)
        e=dict(logical_path=logical,path=NAME+'/'+relative,sha256=sha(stored),uncompressed_sha256=sha(data),bytes=len(stored),uncompressed_bytes=len(data))
        if compress:e['compression']='gzip'
        if original is not None:e.update(redacted_public_derivative=True,local_original_sha256=sha(original),local_original_bytes=len(original),derivation=reason,numeric_fields_preserved=True)
        entries.append(e)
    for logical,path in selected.items():
        original=path.read_bytes();data=original;changed=False
        immutable=path.name in {'raw.jsonl','events.jsonl'}
        if structured_json(logical,path) and not immutable:
            data,changed=privacy.public_json(original,pool,path.suffix=='.jsonl')
        elif path.suffix in {'.md','.txt','.log','.stdout','.stderr'}:
            text=original.decode('utf-8');redacted=privacy.scrub(text,pool)
            if redacted!=text:data=redacted.encode();changed=True
        compress=path.suffix=='.jsonl' or (len(data)>131072 and path.suffix in {'.json','.log','.stdout','.stderr','.txt','.xml'})
        add_bytes(logical,data,original if changed else None,'Unrelated argv/container text removed; all structured numeric values and list positions preserved.' if changed else None,compress)
        if logical in OPAQUE_OUTPUT:
            entries[-1].update({k:v for k,v in OPAQUE_OUTPUT[logical].items() if k!='sha256'})
        if logical=='platform/'+upstream['public_relative_path']:
            entries[-1].update(redacted_public_derivative=True,local_original_sha256=upstream['original_sha256'],
                local_original_bytes=upstream['original_bytes'],upstream_public_sha256=upstream['public_sha256'],
                derivation=upstream['reason']+' Original remains private locally. Any further structural argv derivative is also identified.',
                numeric_fields_preserved=True)
    # Memory component is already independently scoped/redacted by its packager.
    # Index its exact stored bytes so the inner portable manifest stays valid.
    inner={e['path']:e for e in read(memory/'manifest.json')['files']}
    for p in sorted(memory.rglob('*')):
        if not p.is_file():continue
        stored=p.read_bytes();plain=gzip.decompress(stored) if p.suffix=='.gz' else stored
        rel=str(p.relative_to(output));e=dict(logical_path=rel,path=NAME+'/'+rel,sha256=sha(stored),uncompressed_sha256=sha(plain),bytes=len(stored),uncompressed_bytes=len(plain))
        if p.suffix=='.gz':e['compression']='gzip'
        inherited=inner.get(str(p.relative_to(memory)),{})
        for k in ['redacted_public_derivative','local_original_sha256','local_original_bytes','derivation','derived_metric_subset','source_reports']:
            if k in inherited:e[k]=inherited[k]
        entries.append(e)
    snap=A24/'linux-workspace-candidate005/SwiftJLS'
    for rel,digest in {**receipt['swiftjls_file_sha256'],**receipt['test_file_sha256']}.items():
        data=(snap/rel).read_bytes();require(sha(data)==digest,'Snapshot identity');add_bytes('source/'+rel,data)
    for rel in ['Package.swift','VERSION','Scripts/Benchmark/Consumer.swift']:
        add_bytes('source/'+rel,(snap/rel).read_bytes())
    changes=[];patches=[]
    for rel,digest in {**receipt['swiftjls_file_sha256'],**receipt['test_file_sha256']}.items():
        c=subprocess.run(['git','show',PLAN['base_head']+':'+rel],cwd=REPO,capture_output=True)
        old=c.stdout if c.returncode==0 else b'';new=(snap/rel).read_bytes()
        if old==new:continue
        require(c.returncode in {0,128},'Unexpected base source failure')
        patch='diff --git a/'+rel+' b/'+rel+'\n'
        if c.returncode:patch+='new file mode 100644\n'
        patch+=''.join(difflib.unified_diff(old.decode().splitlines(True),new.decode().splitlines(True),fromfile='a/'+rel if c.returncode==0 else '/dev/null',tofile='b/'+rel))
        patches.append(patch);changes.append(dict(path=rel,base_sha256=sha(old) if c.returncode==0 else None,candidate_sha256=digest,new_file=c.returncode!=0))
        add_bytes('source/patches/'+rel.replace('/','__')+'.patch',patch.encode())
    require({x['path'] for x in changes}==set(PLAN['expected_changed_files']),'Unexpected candidate source diff')
    add_bytes('source/candidate005.patch',''.join(patches).encode());add_bytes('source/changes.json',(json.dumps(changes,indent=2)+'\n').encode())
    readme='''# Candidate005 qualification evidence

This archive preserves preparation, an interrupted environment-guard attempt, final measurements, software qualification, independent reviews and the authored disposition. Prior archives are immutable. Measurements are identified by exact source and binary receipts, not by the base commit alone.

Raw timing/event JSONL is unchanged and losslessly gzipped. Condition derivatives preserve numeric fields/list positions while removing unrelated process arguments; original hashes are retained. Shared services remained active. The interrupted 468-process attempt is retained separately and never pooled into final results. Physical qualification and milestone5 retain their authored status.

Portable numerical replay (no new measurements):

```sh
python3 tools/replay-performance.py --archive .
python3 memory/replay-workspace.py --archive memory
```

The optional `--bootstrap` argument repeats the frozen 50,000-resample short/RSS analyses and requires NumPy. Historical collection drivers retain original local paths as provenance; they are not advertised as directly portable. Full host tests require the repository fixtures matching the archived source pins; only probe-required fixtures are duplicated here. Binaries, build trees and private VM access files are excluded.
'''
    if args.partial_checkpoint:
        readme='# Partial candidate005 checkpoint\n\nLarger-image and RSS candidate005 comparisons were not executed because AC admission remained unavailable. Milestone4 is incomplete. This checkpoint publishes completed short-run/software/memory evidence without weakening the original criteria. See missing-measurements.json and the authored disposition.\n\n'+readme
    add_bytes('README.md',readme.encode());source_guard();history_guard()
    require(len({e['logical_path'] for e in entries})==len(entries),'Duplicate archive logical paths')
    add_bytes('missing-measurements.json',(json.dumps(missing,indent=2)+'\n').encode())
    manifest=dict(schema_version=1,archive_id=NAME,generated_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
      base_revision=PLAN['base_head'],selected_candidate=receipt['candidate'],source_receipt_sha256=PLAN['source_receipt_sha256'],
      source_manifest_sha256=receipt['all_source_pins_sha256'],source_files=39,test_files=32,host_tests=157,named_suites=28,xunit_classnames=29,
      candidate_patch_sha256=sha(''.join(patches).encode()),milestone4_complete=disposition['milestone4_complete'],
      automatic_performance_acceptance=False,physical_device_validation_status=disposition['physical_device_validation_status'],milestone5_status=disposition['milestone5_status'],
      production_peakWorkspaceBytes=None,pure_algorithm_workspace_complete=False,performance_disposition_path='review/'+PLAN['authored_disposition'],
      publication_mode='partial_checkpoint' if args.partial_checkpoint else 'full_evidence',missing_measurements=missing,
      interrupted_processes=468,final_processes={k:PLAN['performance']['expected_processes'][k] for k in active},
      final_runs={k:Path(v).name for k,v in active.items()},
      final_run_paths={k:PLAN['performance']['package_by_kind'][k]['archive_prefix']+'/'+PLAN['performance']['package_by_kind'][k]['run_directory'] for k in active},
      package_bindings={k:PLAN['performance']['package_by_kind'][k] for k in active},
      independent_audit_helper_sha256=PLAN['performance']['independent_audit_helper_sha256'],
      base_audit_sha256=PLAN['performance']['base_audit_sha256'],
      file_count=len(entries),total_compressed_bytes=sum(e['bytes'] for e in entries),total_uncompressed_bytes=sum(e['uncompressed_bytes'] for e in entries),
      redacted_derivative_count=sum(bool(e.get('redacted_public_derivative')) for e in entries),
      source_commit=None,source_identity='Exact source receipt/pins; no uncommitted candidate claimed as base commit.',
      released_window_note=args.released_window_note,files=entries)
    (parent/(NAME+'.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(status='staged only; full independent privacy/hash/replay audit and explicit publication release required',directory=str(output),manifest=str(parent/(NAME+'.json')),files=len(entries))))
def publish(args):
    parent=args.stage_parent.resolve();source=parent/NAME;manifest=read(parent/(NAME+'.json'))
    partial=manifest.get('publication_mode')=='partial_checkpoint'
    require(partial==args.partial_checkpoint,'Explicit partial publication flag must match reviewed manifest')
    admission(partial)
    require(args.accepted_manifest_sha256==file_sha(parent/(NAME+'.json')),'Independent acceptance digest mismatch')
    require(not (RESULTS/NAME).exists() and not (RESULTS/(NAME+'.json')).exists(),'Never overwrite a published archive')
    for e in manifest['files']:
        path=(parent/e['path']).resolve();require(path.is_relative_to(source),'Path escape')
        require(file_sha(path)==e['sha256'],'Staged artifact changed')
    shutil.copytree(source,RESULTS/NAME);shutil.copy2(parent/(NAME+'.json'),RESULTS/(NAME+'.json'))
    history_guard();print('Published new archive only; no commit, push, CI verification or merge performed.')
if __name__=='__main__':
    parser=argparse.ArgumentParser();sub=parser.add_subparsers(dest='mode',required=True)
    s=sub.add_parser('stage');s.add_argument('--stage-parent',type=Path,required=True);s.add_argument('--released-window-note',required=True)
    p=sub.add_parser('publish');p.add_argument('--stage-parent',type=Path,required=True);p.add_argument('--accepted-manifest-sha256',required=True)
    s.add_argument('--partial-checkpoint',action='store_true');p.add_argument('--partial-checkpoint',action='store_true')
    args=parser.parse_args();(stage if args.mode=='stage' else publish)(args)
