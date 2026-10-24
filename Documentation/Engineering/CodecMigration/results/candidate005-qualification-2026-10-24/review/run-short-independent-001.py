"""Root-authorised short-only audit while all measurements are paused; no new timing."""
import datetime,importlib.util,json,pathlib,traceback
ROOT=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024');script=ROOT/'final-candidate005-audit.py'
spec=importlib.util.spec_from_file_location('finalaudit',script);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
package=ROOT/'campaigns005-confirmation';run=package/'runs/short1032-002';out=ROOT/'short-independent-001';a.require(not out.exists(),'Fresh scoped audit required');out.mkdir()
try:
 a.require(a.load(run/'complete.json')['completed'] is True,'Short campaign incomplete')
 a.require(a.sha(package/'campaign-freeze.json')==a.FREEZE,'Accepted package changed')
 for n,h in a.load(package/'campaign-freeze.json')['files'].items():a.require(a.sha(package/n)==h,'Package changed '+n)
 identity=a.load(package/'identity.json')
 for p,h in identity['artifacts'].items():a.require(a.sha(p)==h,'Build artifact changed '+p)
 for label,b in identity['binaries'].items():a.require(a.sha(b['path'])==b['sha256'],'Binary changed '+label)
 hashes=a.freeze_check('short',run,package);raw=a.lines(run/'raw.jsonl');events=a.lines(run/'events.jsonl');plan=a.load(run/'frozen_schedule.json')
 report={'scope':'SHORT ONLY; larger/RSS and overall task acceptance pending','authorisation':'Root explicitly authorised short-only50k replay while AC-dependent collection is paused and platform validation proceeds','started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'audit_script_sha256':a.sha(script),'wrapper_sha256':a.sha(__file__),'run':str(run),'package_freeze_sha256':a.FREEZE,'hashes':hashes,'count_and_fidelity':a.counts_and_events('short',run,plan,raw,events),'conditions':a.conditions_review(run)}
 a.write(out/'pre-replay-receipt.json',report);print('Short18576 receipt/fidelity/conditions verified; starting exact50k replay',flush=True)
 report['replay']=a.replay('short',run,out);report['results']=a.short_metrics(raw,a.load(run/'summary.json'))
 m=a.load(run/'bootstrap-metadata.json');a.require(m['rounds']==1032 and m['rounds_per_permutation_stratum']==172 and m['resamples']==50000 and m['seed']==20261022 and m['family_size_combined']==48,'Inference family/counts')
 a.require(a.freeze_check('short',run,package)==hashes,'Evidence changed during replay')
 report.update(completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),completed=True,bootstrap_metadata_sha256=a.sha(run/'bootstrap-metadata.json'),frozen_analyser_sha256=a.sha(run/'frozen_analyse.py'),summary_replay_sha256=a.sha(out/'short-replay/summary.json'),metadata_replay_sha256=a.sha(out/'short-replay/bootstrap-metadata.json'))
 a.write(out/'audit.json',report);a.write(out/'reuse-receipt.json',{'scope':'Exact short1032-002 independent replay only','completed':True,'report_path':str(out/'audit.json'),'report_sha256':a.sha(out/'audit.json'),'audit_script_sha256':a.sha(script),'wrapper_sha256':a.sha(__file__),'package_freeze_sha256':a.FREEZE,'run':str(run),'hashes':hashes,'frozen_analyser_sha256':report['frozen_analyser_sha256'],'bootstrap_metadata_sha256':report['bootstrap_metadata_sha256'],'replay_summary':str(out/'short-replay/summary.json'),'replay_summary_sha256':report['summary_replay_sha256'],'replay_metadata':str(out/'short-replay/bootstrap-metadata.json'),'replay_metadata_sha256':report['metadata_replay_sha256']})
 print(json.dumps({'completed':True,'short_counts':report['results']['counts'],'findings':report['results']['findings'],'audit':str(out/'audit.json'),'reuse_receipt_sha256':a.sha(out/'reuse-receipt.json')},indent=2),flush=True)
except BaseException as e:
 a.write(out/'failure.json',{'error':repr(e),'traceback':traceback.format_exc()});raise
