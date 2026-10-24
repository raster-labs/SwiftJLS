#!/usr/bin/env python3
"""Final evidence audit: original short package; exact-service-admission larger/RSS package."""
import argparse,hashlib,importlib.util,json,pathlib,re,sys
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT/'final-candidate005-audit.py'
BASE_SHA='65ec9ed0caf840b146712888b34489f550b364fea3f99bf86e5395156f0a6702'
OLD_FREEZE='71487cb4d5272ef0791e04aeeada506ec94ade2fa244f3ec2791539674b0a948'
NEW_FREEZE='fe685af50f458b7d4646817cd1b25247186eee40983bf5c65cebce4f62eae41d'
spec=importlib.util.spec_from_file_location('baseaudit',BASE);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
a.require(a.sha(BASE)==BASE_SHA,'Accepted base audit functions changed')

def accepted_freeze(kind):return OLD_FREEZE if kind=='short' else NEW_FREEZE

def verify_package(package,want):
 a.require(a.sha(package/'campaign-freeze.json')==want,'Wrong accepted package')
 for n,h in a.load(package/'campaign-freeze.json')['files'].items():a.require(a.sha(package/n)==h,'Package source changed '+n)
 identity=a.load(package/'identity.json')
 for p,h in identity['artifacts'].items():a.require(a.sha(p)==h,'Immutable build artifact changed '+p)
 for label,b in identity['binaries'].items():a.require(a.sha(b['path'])==b['sha256'],'Immutable binary changed '+label)
 return {'path':str(package.resolve()),'freeze_sha256':want,'helper_sha256':a.sha(package/'diag72_runner.py'),'identity_sha256':a.sha(package/'identity.json')}

def freeze_check(kind,run,package):
 # Base check is unchanged; the exact package constant is selected explicitly per scope.
 prior=a.FREEZE
 try:
  a.FREEZE=accepted_freeze(kind)
  result=a.freeze_check(kind,run,package)
 finally:a.FREEZE=prior
 if kind!='short':a.require(a.sha(run/'persistent-service-identities.json')==a.sha(package/'persistent-service-identities.json'),'Frozen selected identities differ')
 return result

def reuse_short(run,receipt_path):
 receipt=a.load(receipt_path)
 a.require(receipt['completed'] is True and receipt['package_freeze_sha256']==OLD_FREEZE,'Incomplete/wrong short replay receipt')
 a.require(pathlib.Path(receipt['run']).resolve()==run.resolve(),'Replay receipt belongs to another run')
 a.require(receipt['audit_script_sha256']==BASE_SHA,'Accepted independent audit implementation differs')
 a.require(a.sha(receipt['report_path'])==receipt['report_sha256'],'Independent short report changed')
 a.require(a.load(receipt['report_path'])['completed'] is True,'Independent short audit incomplete')
 for n,h in receipt['hashes'].items():a.require(a.sha(run/n)==h,'Short input changed after independent replay: '+n)
 a.require(a.sha(run/'frozen_analyse.py')==receipt['frozen_analyser_sha256'],'Short frozen analyser changed')
 a.require(a.sha(run/'bootstrap-metadata.json')==receipt['bootstrap_metadata_sha256'],'Short metadata changed')
 for p,h in [('replay_summary','replay_summary_sha256'),('replay_metadata','replay_metadata_sha256')]:a.require(a.sha(receipt[p])==receipt[h],'Short replay artifact changed')
 a.require(a.load(receipt['replay_summary'])==a.load(run/'summary.json'),'Exact short replay summary differs')
 a.require(a.load(receipt['replay_metadata'])==a.load(run/'bootstrap-metadata.json'),'Exact short replay metadata differs')
 return {'exact_replay_equal':True,'fresh_short_replay_performed':False,'completed_independent_replay':str(receipt_path.resolve()),'reuse_receipt_sha256':a.sha(receipt_path),'original_package_freeze_sha256':OLD_FREEZE,'replay_summary_sha256':receipt['replay_summary_sha256'],'replay_metadata_sha256':receipt['replay_metadata_sha256']}

def selected_identities_review(run,package):
 expected={x['identity']['name']:x for x in a.load(package/'persistent-service-identities.json')['services']}
 snapshots=a.lines(run/'conditions.jsonl')
 env=a.load(run/'environment.json')
 if isinstance(env.get('conditions'),dict):snapshots=[env['conditions']]+snapshots
 total=0;by_name={name:0 for name in expected}
 for snapshot in snapshots:
  inventory=snapshot['colima_vm_inventory'];inspections=inventory.get('persistent_service_inspection',{})
  rows={c['Names']:c for c in inventory['running_containers']}
  for name,c in rows.items():
   if name not in expected:continue
   value=dict(c['persistent_service_identity']);a.require(value.pop('status')=='running','Selected service not running')
   a.require(value==expected[name]['identity'],'Selected service drift in retained condition')
   a.require(re.fullmatch(r'[0-9a-f]{12,64}',str(c['ID'])) and value['id'].startswith(c['ID']),'Selected inspection ps-ID mismatch')
   a.require(value['name']==name and value['image']==c['Image'],'Selected inspection ps row mismatch')
   digest=hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   a.require(digest==expected[name]['selected_role_config_sha256'],'Selected identity digest changed')
   matching=[v for v in inspections.get('services',[]) if v['name']==name]
   a.require(len(matching)==1 and matching[0]['identity_matches'] is True,'Selected inspection receipt missing')
   a.require(matching[0]['identity']==c['persistent_service_identity'],'Selected inspection receipt mismatch')
   a.require(inspections['inspection_seconds']>=0 and inspections['started_utc']<=inspections['completed_utc'],'Selected inspection chronology')
   by_name[name]+=1;total+=1
 return {'snapshots':len(snapshots),'exact_identity_observations':total,'by_service':by_name,'identity_definition_sha256':a.sha(package/'persistent-service-identities.json'),'scope':'Independent selected-field equality checks; shared host, no idleness inference'}

def preserve_prior_attempts():
 results=[]
 for name,key in [('006-short1032-interruption-policy.json','interrupted_run'),('009-larger-ac-interruption-policy.json','run'),('012-larger-workload-interruption-policy.json','retained_attempt')]:
  path=ROOT/name;prior=a.load(path);run=pathlib.Path(prior[key])
  for n,h in prior['preservation_hashes'].items():a.require(a.sha(run/n)==h,'Prior interrupted evidence changed '+name+':'+n)
  results.append({'receipt':str(path),'receipt_sha256':a.sha(path),'completed_processes':prior['completed_processes'],'preservation_hashes_unchanged':True,'not_pooled_or_analysed':True})
 return results

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--self-test',action='store_true');p.add_argument('--timing-complete',action='store_true')
 for key in ['old-package','new-package','short','larger','rss','reuse-short','output']:p.add_argument('--'+key,type=pathlib.Path)
 args=p.parse_args()
 if args.self_test:
  a.self_test();a.require(accepted_freeze('short')==OLD_FREEZE and all(accepted_freeze(x)==NEW_FREEZE for x in ['larger','rss']) and OLD_FREEZE!=NEW_FREEZE,'Per-scope package selection')
  print(json.dumps({'mixed_package_controls':True,'short_uses_old_helper_only':True,'no_live_commands_or_replay':True}));return
 a.require(args.timing_complete,'ALL timing must finish before this audit')
 a.require(all([args.old_package,args.new_package,args.short,args.larger,args.rss,args.reuse_short,args.output]),'All paths required')
 for run in [args.short,args.larger,args.rss]:a.require((run/'complete.json').exists() and a.load(run/'complete.json')['completed'] is True,'All three scopes must complete before outcomes are read')
 a.require(not args.output.exists(),'Fresh output directory required');args.output.mkdir(parents=True)
 old=verify_package(args.old_package,OLD_FREEZE);new=verify_package(args.new_package,NEW_FREEZE)
 a.require(old['identity_sha256']==new['identity_sha256'],'Candidate/baseline identity drift between packages')
 report={'scope':'candidate005 completed short1032 original host helper; larger15/RSS528 exact persistent-service identity admission amendment; shared host throughout','audit_script_sha256':a.sha(__file__),'base_audit_sha256':BASE_SHA,'packages':{'short':old,'larger':new,'rss':new},'retained_interrupted_attempts':preserve_prior_attempts(),'runs':{}}
 for kind,run in [('short',args.short),('larger',args.larger),('rss',args.rss)]:
  package=args.old_package if kind=='short' else args.new_package
  hashes=freeze_check(kind,run,package);raw=a.lines(run/'raw.jsonl');events=a.lines(run/'events.jsonl');plan=a.load(run/'frozen_schedule.json')
  result={'run':str(run.resolve()),'package_binding':report['packages'][kind],'hashes':hashes,**a.counts_and_events(kind,run,plan,raw,events),'conditions':a.conditions_review(run)}
  if kind=='short':result['replay']=reuse_short(run,args.reuse_short)
  if kind=='rss':result['replay']=a.replay(kind,run,args.output)
  if kind!='short':result['selected_service_identity_conditions']=selected_identities_review(run,package)
  summary=a.load(run/'summary.json')
  if kind=='short':
   meta=a.load(run/'bootstrap-metadata.json');a.require(meta['rounds']==1032 and meta['rounds_per_permutation_stratum']==172 and meta['resamples']==50000 and meta['seed']==20261022 and meta['family_size_combined']==48,'Short inference metadata')
  if kind=='rss':
   meta=summary['bootstrap_metadata'];a.require(meta['resamples']==50000 and meta['seed']==20261022 and meta['family_size']==4 and meta['bonferroni_95_quantiles']==[.00625,.99375],'RSS inference metadata')
  result['results']=({'short':a.short_metrics,'larger':a.larger_metrics,'rss':a.rss_metrics}[kind])(raw,summary)
  report['runs'][kind]=result;a.write(args.output/'audit.json',report)
 report['completed']=True;a.write(args.output/'audit.json',report)
 print(json.dumps({'audit':str(args.output/'audit.json'),'short_counts':report['runs']['short']['results']['counts'],'larger_above_gate':len(report['runs']['larger']['results']['pooled_above_1_05']),'rss_within_finite_criterion':report['runs']['rss']['results']['candidate_within_finite_criterion_vs_both_baselines']},indent=2))
if __name__=='__main__':main()
