#!/usr/bin/env python3
"""Final all-campaign audit using an independently completed, hash-bound short-only replay."""
import argparse,importlib.util,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parent
BASE=ROOT/'final-candidate005-audit.py'
spec=importlib.util.spec_from_file_location('baseaudit',BASE);a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
p=argparse.ArgumentParser(add_help=False);p.add_argument('--reuse-short',type=pathlib.Path,required=True);args,remainder=p.parse_known_args()
base_replay=a.replay

def replay(kind,run,out):
 if kind!='short':return base_replay(kind,run,out)
 # Called only inside base main after --timing-complete/all-three-complete validation,
 # complete raw/event/schedule checks and all condition admissions for the short run.
 receipt=a.load(args.reuse_short)
 a.require(receipt['completed'] is True and receipt['package_freeze_sha256']==a.FREEZE,'Incomplete/wrong replay receipt')
 a.require(pathlib.Path(receipt['run']).resolve()==run.resolve(),'Replay receipt is for another run')
 a.require(receipt['audit_script_sha256']==a.sha(BASE),'Audited function implementation changed')
 a.require(a.sha(receipt['report_path'])==receipt['report_sha256'],'Independent report changed')
 report=a.load(receipt['report_path']);a.require(report['completed'] is True,'Independent short audit incomplete')
 for n,h in receipt['hashes'].items():a.require(a.sha(run/n)==h,'Raw/evidence changed since independent replay: '+n)
 a.require(a.sha(run/'frozen_analyse.py')==receipt['frozen_analyser_sha256'],'Frozen analyser changed')
 a.require(a.sha(run/'bootstrap-metadata.json')==receipt['bootstrap_metadata_sha256'],'Original bootstrap metadata changed')
 for path_key,hash_key in [('replay_summary','replay_summary_sha256'),('replay_metadata','replay_metadata_sha256')]:a.require(a.sha(receipt[path_key])==receipt[hash_key],'Prior replay changed')
 a.require(a.load(receipt['replay_summary'])==a.load(run/'summary.json'),'Prior exact summary differs')
 a.require(a.load(receipt['replay_metadata'])==a.load(run/'bootstrap-metadata.json'),'Prior exact metadata differs')
 return {'exact_replay_equal':True,'fresh_short_replay_performed':False,'reused_completed_independent_replay':str(args.reuse_short.resolve()),'reuse_receipt_sha256':a.sha(args.reuse_short),'replay_summary_sha256':receipt['replay_summary_sha256'],'reuse_wrapper_sha256':a.sha(__file__),'explanation':'Frozen50k replay was independently completed while measurements were paused; exact input/script/summary/metadata hashes are reverified, then raw medians/pairs and48 classifications are independently recomputed again.'}
a.replay=replay
sys.argv=[sys.argv[0]]+remainder
a.main()
