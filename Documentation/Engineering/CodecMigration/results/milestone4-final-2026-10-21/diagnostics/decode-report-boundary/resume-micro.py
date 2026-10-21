#!/usr/bin/env python3
"""Continue only unexecuted micro entries; preserve and recover the zero-valued completed process."""
import importlib.util,json,math,os,pathlib,signal,subprocess,time
HERE=pathlib.Path(__file__).resolve().parent;ROOT=HERE.parents[3];out=HERE/'results-3'
spec=importlib.util.spec_from_file_location('common',HERE.parent/'tiny-confirmatory/run.py');common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
req=common.require;write=common.write
old=json.loads((out/'interrupted.json').read_text());plan=json.loads((HERE/'schedule.json').read_text());build=json.loads((HERE/'build.json').read_text())
req(old['decode_processes']==128 and old['micro_processes']==4 and old['error']=="RuntimeError('Invalid micro samples')",'Unexpected partial state')
rows=[json.loads(x) for x in (out/'micro-raw.jsonl').read_text().splitlines()];req(len(rows)==4,'Unexpected retained micro count')
entry=plan['micro_schedule'][4];recovered=json.loads(old['current']['stdout']);req(recovered['mode']==entry['constructor'] and recovered['warmups']==entry['warmups'] and recovered['iterations']==entry['iterations'],'Recovery identity mismatch')
req(old['current']['exit_code']==0 and all(math.isfinite(v) and v>=0 for v in recovered['seconds']),'Invalid recovery data')
recovered.update(entry=entry,binary_sha256=build['binaries']['UUIDBenchmark']['sha256'],command=old['current']['command'],stderr=old['current']['stderr'],exit_code=0,process_seconds=None,recovered_from='interrupted.json.current.stdout; no rerun; zero durations retained at clock resolution')
rows.append(recovered)
env=dict(os.environ,DEVELOPER_DIR='/Library/Developer/CommandLineTools');common.source_guards(env)
for binary in build['binaries'].values():req(common.sha(pathlib.Path(binary['path']))==binary['sha256'],'Diagnostic binary changed')
start=common.conditions(env);req("Now drawing from 'AC Power'" in start['power']['output'],'AC required')
write(out/'micro-resume.json',dict(reason='Micro clock quantisation permits zero durations. Recover the completed fifth process unchanged and run only91 previously unstarted entries. No rerun/drop of any observation.',recovered_zeros=sum(v==0 for v in recovered['seconds']),remaining_processes=91,runner_sha256=common.sha(pathlib.Path(__file__)),conditions=start))
process=None;current=None;last_snapshot=0
try:
 with (out/'micro-raw-complete.jsonl').open('x') as raw,(out/'resume-conditions.jsonl').open('x') as cond:
  for row in rows:raw.write(json.dumps(row)+'\n')
  raw.flush()
  def snapshot():
   global last_snapshot
   c=common.conditions(env);c['micro_processes']=len(rows);cond.write(json.dumps(c)+'\n');cond.flush();last_snapshot=time.monotonic();req("Now drawing from 'AC Power'" in c['power']['output'],'AC lost')
  snapshot()
  for entry in plan['micro_schedule'][5:]:
   cmd=[build['binaries']['UUIDBenchmark']['path'],entry['constructor'],str(entry['warmups']),str(entry['iterations'])];current=dict(command=cmd,entry=entry)
   start_time=time.monotonic();process=subprocess.Popen(cmd,env=env,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   while True:
    try:stdout,stderr=process.communicate(timeout=1);break
    except subprocess.TimeoutExpired:
     if time.monotonic()-last_snapshot>=10:snapshot()
     req(time.monotonic()-start_time<600,'Micro timeout')
   current.update(stdout=stdout,stderr=stderr,exit_code=process.returncode);req(process.returncode==0,'Micro failed')
   row=json.loads(stdout);req(row['mode']==entry['constructor'] and row['warmups']==entry['warmups'] and row['iterations']==entry['iterations'],'Micro profile mismatch')
   req(len(row['seconds'])==entry['iterations'] and all(math.isfinite(v) and v>=0 for v in row['seconds']),'Invalid nonnegative micro values')
   row.update(entry=entry,binary_sha256=build['binaries']['UUIDBenchmark']['sha256'],command=cmd,exit_code=0,stderr=stderr,process_seconds=time.monotonic()-start_time);rows.append(row);raw.write(json.dumps(row)+'\n');raw.flush();process=None
   if time.monotonic()-last_snapshot>=10:snapshot()
  snapshot()
 req(len(rows)==96,'Wrong micro count');end_guards=common.source_guards(env)
 for binary in build['binaries'].values():req(common.sha(pathlib.Path(binary['path']))==binary['sha256'],'Diagnostic binary changed')
 end=common.conditions(env);req("Now drawing from 'AC Power'" in end['power']['output'],'AC lost at end')
 write(out/'complete.json',dict(completed=True,performance_qualified=False,decode_processes=128,micro_processes=96,source_guards=end_guards,conditions=end,schedule_sha256=common.sha(HERE/'schedule.json'),interruption_preserved='interrupted.json',micro_raw='micro-raw-complete.jsonl',recovery='Fifth process recovered unchanged from retained stdout;91 previously unstarted processes executed; zero durations retained.'))
 print('Completed all128 decode and96 micro processes; no reruns',flush=True)
except BaseException as error:
 if process is not None and process.poll() is None:
  try:os.killpg(process.pid,signal.SIGTERM)
  except ProcessLookupError:pass
  stdout,stderr=process.communicate();current.update(stdout=stdout,stderr=stderr,exit_code=process.returncode)
 write(out/'resume-interrupted.json',dict(error=repr(error),micro_processes=len(rows),current=current,conditions=common.conditions(env)));raise
