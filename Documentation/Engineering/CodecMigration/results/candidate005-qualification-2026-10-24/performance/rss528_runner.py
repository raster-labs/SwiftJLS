#!/usr/bin/env python3
"""Fixed RSS528 qualification, no optional extension; shared host, original Consumer 5+5."""
import argparse,datetime,hashlib,itertools,json,os,pathlib,random,shutil,signal,subprocess,sys,time
import campaign_identity as identity
from diag72_runner import conditions,admit_conditions,self_test_host_guards
import rss528_analyse as analysis
HERE=pathlib.Path(__file__).resolve().parent
REPO=identity.REPO
LABELS=['62309d3','e66f7da','candidate','candidate-copy']
SEED=20261022
BLOCKS=528
sha=identity.sha
require=identity.require

def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def append(f,v):f.write(json.dumps(v)+'\n');f.flush();os.fsync(f.fileno())
def plan():
 c=identity.config();perms=list(itertools.permutations(LABELS));indices=[i for i in range(24) for _ in range(22)];random.Random(SEED).shuffle(indices)
 rows=[]
 for b,i in enumerate(indices):
  for pos,label in enumerate(perms[i]):
   underlying='candidate' if label=='candidate-copy' else label
   binary=c['binaries'][underlying]
   rows.append({'process_index':len(rows),'block':b,'position':pos,'permutation_index':i,'order':list(perms[i]),'label':label,'underlying_source':underlying,'binary_path':binary['path'],'binary_sha256':binary['sha256']})
 return {'schema':1,'candidate':'candidate_005','seed':SEED,'blocks':BLOCKS,'processes':rows,'expected_processes':2112,'warmups':5,'observations':5,'fixture':{'width':512,'height':512,'bits':12,'pattern':'noise','components':1,'near':0,'interleave':0,'encoded_bytes':410542},'permutation_counts':[22]*24,'position_counts':{x:[132]*4 for x in LABELS},'comparisons':[list(x) for x in analysis.COMPARISONS_PART2],'bootstrap':{'resamples':50000,'seed':20261022,'cluster':'whole four-arm block, all four contrasts jointly','family_size':4,'quantiles':[.00625,.99375]},'host_scope':'Shared host; resident services remain running; named-workload/AC/thermal guards unchanged; no CPU-idleness guarantee'}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--prepare',action='store_true');p.add_argument('--check-only',action='store_true');p.add_argument('--self-test',action='store_true');p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
 schedule=HERE/'schedules/rss528-4arms-005.json';expected=plan()
 if a.prepare:
  require(not schedule.exists(),'Fresh schedule required');schedule.parent.mkdir(exist_ok=True);write(schedule,expected);print(sha(schedule));return
 require(json.loads(schedule.read_text())==expected,'Schedule changed from deterministic plan')
 require(len(expected['processes'])==2112,'Bad process count')
 from collections import Counter
 require(Counter(x['permutation_index'] for x in expected['processes'] if x['position']==0)=={i:22 for i in range(24)},'Permutation imbalance')
 env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools',SWIFTJLS_BENCHMARK_END_TO_END='1')
 for k in ['SWIFTJLS_BENCHMARK_EXPORT','SWIFTJLS_BENCHMARK_DECODE']:env.pop(k,None)
 proof=identity.verify(env)
 if a.self_test:
  print(json.dumps({'source_guards':proof,'host_guard_synthetic':self_test_host_guards(),'analysis_synthetic':analysis.self_test()},indent=2));return
 if a.check_only:print(json.dumps({'status':'identity and schedule only; no benchmark execution','source_guards':proof,'expected_processes':2112,'schedule_sha256':sha(schedule)},indent=2));return
 require(a.output is not None,'--output required');out=a.output.resolve();require(not out.exists(),'Fresh output directory required');out.mkdir(parents=True)
 frozen={}
 for f in ['rss528_runner.py','rss528_analyse.py','diag72_runner.py','campaign_identity.py','identity.json','campaign-freeze.json']:
  src=HERE/f;shutil.copy2(src,out/f);frozen[f]=sha(src)
 shutil.copy2(schedule,out/'frozen_schedule.json');frozen['schedules/rss528-4arms-005.json']=sha(schedule)
 rows=[];current=None;process=None
 def frozen_guard():
  for n,h in frozen.items():require(sha(HERE/n)==h,'Frozen script/schedule changed: '+n)
  return identity.verify(env)
 try:
  start=conditions(env);write(out/'environment.json',{'source_guards':proof,'conditions':start,'host_scope':expected['host_scope'],'script_hashes':frozen});admit_conditions(start)
  with (out/'events.jsonl').open('w') as events,(out/'raw.jsonl').open('w') as raw,(out/'conditions.jsonl').open('w') as cond:
   last=0
   def snapshot(tag):
    nonlocal last
    c=conditions(env);c.update(tag=tag,completed_processes=len(rows));append(cond,c);last=time.monotonic();admit_conditions(c)
   snapshot('start')
   for entry in expected['processes']:
    if entry['position']==0:snapshot('block_'+str(entry['block']))
    cmd=[entry['binary_path'],'512','512','12','noise','5','5',entry['label'],'1','0','0']
    current={'entry':entry,'command':cmd,'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat()};t=time.monotonic()
    process=subprocess.Popen(cmd,cwd=REPO,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    while True:
     try:stdout,stderr=process.communicate(timeout=1);break
     except subprocess.TimeoutExpired:
      if time.monotonic()-last>=10:snapshot('during_process')
      require(time.monotonic()-t<300,'Process exceeded 300 seconds')
    current.update(stdout=stdout,stderr=stderr,exit_code=process.returncode,process_seconds=time.monotonic()-t,completed_utc=datetime.datetime.now(datetime.timezone.utc).isoformat());append(events,current);process=None
    require(current['exit_code']==0,'Consumer failed; evidence retained')
    rep=json.loads(stdout);analysis.validate_part2_report(rep,entry)
    row=dict(entry,report=rep,started_utc=current['started_utc'],completed_utc=current['completed_utc'],process_seconds=current['process_seconds']);rows.append(row);append(raw,row)
    if entry['position']==3 and (entry['block']+1)%24==0:print('Completed',entry['block']+1,'/528 blocks;',len(rows),'/2112 processes',flush=True)
   snapshot('end')
  endproof=frozen_guard();require(len(rows)==2112,'Incomplete campaign');write(out/'measurement-complete.json',{'completed':True,'processes':len(rows),'source_guards':endproof})
  summary=analysis.analyse_part2(rows);write(out/'summary.json',summary);frozen_guard()
  write(out/'complete.json',{'completed':True,'processes':len(rows),'source_guards':endproof,'hashes':{n:sha(out/n) for n in ['raw.jsonl','events.jsonl','conditions.jsonl','summary.json','frozen_schedule.json']}})
 except BaseException as e:
  if process is not None and process.poll() is None:
   try:os.killpg(process.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   so,se=process.communicate();current.update(stdout=so,stderr=se,exit_code=process.returncode)
  write(out/'interrupted.json',{'completed':False,'error':repr(e),'completed_processes':len(rows),'current':current,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()});raise
if __name__=='__main__':main()
