#!/usr/bin/env python3
import datetime,hashlib,importlib.util,json,math,os,pathlib,signal,statistics,subprocess,time
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[3]
spec=importlib.util.spec_from_file_location('common',HERE.parent/'tiny-confirmatory/run.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
require=common.require;write=common.write;sha=common.sha

def plan():
 entries=[]
 for block in range(16):
  for mode in (['short','long'] if block%2==0 else ['long','short']):
   for bits in ([12,16] if block%2==0 else [16,12]):
    order=['report','zero'] if (block+(bits==16))%2==0 else ['zero','report']
    entries.append(dict(block=block,mode=mode,bits=bits,order=order,warmups=5 if mode=='short' else 20000,iterations=5 if mode=='short' else 1000))
 micro=[]
 constructors=['uuid','reference','random']
 for block in range(16):
  for mode in (['short','long'] if block%2==0 else ['long','short']):
   order=constructors[block%3:]+constructors[:block%3]
   if block%2:order.reverse()
   for constructor in order:micro.append(dict(block=block,mode=mode,constructor=constructor,warmups=5 if mode=='short' else 20000,iterations=5 if mode=='short' else 1000))
 return dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),decode_schedule=entries,micro_schedule=micro,decode_processes=128,micro_processes=96,
  source='bee49a2ad47eae4ea149bdced2043b7a45df3dae',scope='Diagnostic only. Same public production method and checks. Same compiled Consumer/Double ABI for report and zero, output masking after outer timer. Short5/5 and long20k/1k,16 independent process blocks each. Separate micro costs include preserved creation/consume/destruction calls and clock overhead; reference-token production forbidden by UUID contract; UUID.random host-only >=26.4.',
  interpretation='First require report outer timing to reproduce short>long direction. Report budget excludes executor entry/return, early public validation, final progress/cancellation and some destruction. Outer-minus-report is not pure executor time. No unmeasured causation or performance waiver.')

def main():
 import argparse
 ap=argparse.ArgumentParser();ap.add_argument('--prepare',action='store_true');ap.add_argument('--output',type=pathlib.Path);args=ap.parse_args()
 if args.prepare:
  require(not (HERE/'schedule.json').exists(),'Schedule exists');write(HERE/'schedule.json',plan());print(sha(HERE/'schedule.json'));return
 require(args.output is not None,'Output required');out=args.output.resolve();require(not out.exists(),'Fresh output required');out.mkdir(parents=True)
 schedule=json.loads((HERE/'schedule.json').read_text());build=json.loads((HERE/'build.json').read_text())
 env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools',SWIFTJLS_BENCHMARK_END_TO_END='1')
 for k in ['SWIFTJLS_BENCHMARK_EXPORT','SWIFTJLS_BENCHMARK_DECODE']:env.pop(k,None)
 binaries=build['binaries'];rows=[];micro=[];process=None;current=None
 try:
  guards=common.source_guards(env)
  for b in binaries.values():require(sha(pathlib.Path(b['path']))==b['sha256'],'Diagnostic binary changed')
  start=common.conditions(env);require("Now drawing from 'AC Power'" in start['power']['output'],'AC required')
  write(out/'environment.json',dict(schedule=schedule,schedule_sha256=sha(HERE/'schedule.json'),runner_sha256=sha(pathlib.Path(__file__)),build=build,source_guards=guards,conditions=start,performance_qualified=False))
  last_snapshot=0
  with (out/'conditions.jsonl').open('w') as conditions_log,(out/'decode-raw.jsonl').open('w') as decode_log,(out/'micro-raw.jsonl').open('w') as micro_log:
   def snapshot():
    nonlocal last_snapshot
    c=common.conditions(env);c.update(decode_processes=len(rows),micro_processes=len(micro));conditions_log.write(json.dumps(c)+'\n');conditions_log.flush();last_snapshot=time.monotonic();require("Now drawing from 'AC Power'" in c['power']['output'],'AC lost')
   def run(command,run_env):
    nonlocal process,current
    current=dict(command=command);start=time.monotonic()
    if start-last_snapshot>=10:snapshot()
    process=subprocess.Popen(command,cwd=ROOT,env=run_env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    while True:
     try:stdout,stderr=process.communicate(timeout=1);break
     except subprocess.TimeoutExpired:
      if time.monotonic()-last_snapshot>=10:snapshot()
      require(time.monotonic()-start<600,'Process timeout')
    current.update(stdout=stdout,stderr=stderr,exit_code=process.returncode);require(process.returncode==0,'Process failed')
    row=json.loads(stdout);row.update(command=command,stderr=stderr,exit_code=process.returncode,process_seconds=time.monotonic()-start);process=None;return row
   snapshot()
   for entry in schedule['decode_schedule']:
    for control in entry['order']:
     cmd=[binaries['ReportBenchmark']['path'],'37','23',str(entry['bits']),'flat',str(entry['warmups']),str(entry['iterations']),control]
     row=run(cmd,dict(env,SWIFTJLS_DIAGNOSTIC_REPORT='1' if control=='report' else '0'))
     for key,expected in dict(width=37,height=23,bits=entry['bits'],pattern='flat',label=control,components=1,near=0,interleave=0,warmups=entry['warmups'],iterations=entry['iterations'],end_to_end=True,retain_report=control=='report').items():require(row.get(key)==expected,'Consumer profile mismatch '+key)
     for key in ['encode_seconds','decode_seconds','prepare_seconds','prepare_encode_seconds','reported_decode_seconds']:
      values=row[key];require(len(values)==entry['iterations'] and all(isinstance(v,(int,float)) and math.isfinite(v) and (v>0 if key!='reported_decode_seconds' or control=='report' else v==0) for v in values),'Invalid samples '+key)
     row.update(entry=entry,control=control,binary_sha256=binaries['ReportBenchmark']['sha256']);rows.append(row);decode_log.write(json.dumps(row)+'\n');decode_log.flush()
    if len(rows)%8==0:print(f'Decode round {len(rows)//8}/16 complete; {len(rows)}/128 processes',flush=True);snapshot()
   for entry in schedule['micro_schedule']:
    cmd=[binaries['UUIDBenchmark']['path'],entry['constructor'],str(entry['warmups']),str(entry['iterations'])]
    row=run(cmd,env);require(row['mode']==entry['constructor'] and row['warmups']==entry['warmups'] and row['iterations']==entry['iterations'],'Micro profile mismatch');require(len(row['seconds'])==entry['iterations'] and all(math.isfinite(v) and v>0 for v in row['seconds']),'Invalid micro samples')
    row.update(entry=entry,binary_sha256=binaries['UUIDBenchmark']['sha256']);micro.append(row);micro_log.write(json.dumps(row)+'\n');micro_log.flush()
   snapshot()
  end_guards=common.source_guards(env)
  for b in binaries.values():require(sha(pathlib.Path(b['path']))==b['sha256'],'Diagnostic binary changed')
  require(len(rows)==128 and len(micro)==96,'Process count mismatch')
  end=common.conditions(env);require("Now drawing from 'AC Power'" in end['power']['output'],'AC lost at end')
  write(out/'complete.json',dict(completed=True,performance_qualified=False,decode_processes=len(rows),micro_processes=len(micro),source_guards=end_guards,conditions=end,schedule_sha256=sha(HERE/'schedule.json')))
  print('All decode and micro processes completed',flush=True)
 except BaseException as error:
  if process is not None and process.poll() is None:
   try:os.killpg(process.pid,signal.SIGTERM)
   except ProcessLookupError:pass
   stdout,stderr=process.communicate();current.update(stdout=stdout,stderr=stderr,exit_code=process.returncode)
  write(out/'interrupted.json',dict(completed=False,error=repr(error),decode_processes=len(rows),micro_processes=len(micro),current=current,conditions=common.conditions(env)));raise
if __name__=='__main__':main()
