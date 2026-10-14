import argparse,datetime,hashlib,json,os,pathlib,signal,statistics,subprocess,time
base=pathlib.Path(__file__).resolve().parent;repo=base.parents[1]
p=argparse.ArgumentParser();p.add_argument('mode',choices=['rgb','tiny']);a=p.parse_args()
env=os.environ.copy();env['DEVELOPER_DIR']='/Library/Developer/CommandLineTools'
for key in ['SWIFTJLS_BENCHMARK_EXPORT','SWIFTJLS_BENCHMARK_DECODE']:env.pop(key,None)
binaries={'c330':repo/'work/m4-benchmark/successor/.build/release/Benchmark','pinned':repo/'work/m4-benchmark/predecessor/.build/release/Benchmark','candidate':base/'consumer/.build/release/Benchmark'}
hashes={label:hashlib.sha256(path.read_bytes()).hexdigest() for label,path in binaries.items()}
(base/'timed-binaries.json').write_text(json.dumps(hashes,indent=2)+'\n')
def record(command):
 r=subprocess.run(command,capture_output=True,text=True,env=env)
 return dict(command=command,exit_code=r.returncode,output=r.stdout+r.stderr)
commands=[]
for label in (['c330','pinned'] if a.mode=='rgb' else ['pinned']):
 folder=base/(a.mode+'-against-'+label)
 command=['python3',str(base/('compare-candidate.py' if a.mode=='rgb' else 'compare-candidate-deep.py')),'--predecessor',str(binaries[label]),'--successor',str(binaries['candidate']),'--baseline-kind',label,'--output',str(folder),'--end-to-end','--cases',str(base/('cases.json' if a.mode=='rgb' else 'tiny-cases.json'))]
 if a.mode=='rgb':command.append('--colour')
 with (base/(folder.name+'.log')).open('w') as log,(base/(folder.name+'-conditions.jsonl')).open('w') as conditions:
  power=record(['pmset','-g','batt']);assert "Now drawing from 'AC Power'" in power['output'],'AC power required'
  start=time.monotonic();process=subprocess.Popen(command,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
  while process.poll() is None:
   snapshot=dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),power=record(['pmset','-g','batt']),thermal=record(['pmset','-g','therm']),load=record(['sysctl','-n','vm.loadavg']))
   conditions.write(json.dumps(snapshot)+'\n');conditions.flush()
   if "Now drawing from 'AC Power'" not in snapshot['power']['output']:
    os.killpg(process.pid,signal.SIGTERM);raise RuntimeError('Power disconnected; partial evidence preserved')
   time.sleep(10)
  row=dict(label=folder.name,command=command,exit_code=process.returncode,seconds=time.monotonic()-start,developer_dir=env['DEVELOPER_DIR'])
  commands.append(row);(base/(a.mode+'-commands.json')).write_text(json.dumps(commands,indent=2)+'\n');print(json.dumps(row),flush=True)
  if process.returncode:raise SystemExit(process.returncode)
 keys=['width','height','bits','pattern','components','near','interleave'];groups={}
 for line in (folder/'raw.jsonl').read_text().splitlines():
  r=json.loads(line);groups.setdefault(tuple(r[k] for k in keys),[]).append(r)
 results=[]
 for key,rows in groups.items():
  case=dict(zip(keys,key));case['operations']={}
  for operation in ['encode','decode','prepare','prepare_encode']:
   med={label:statistics.median(v for r in rows if r['label']==label for v in r[operation+'_seconds']) for label in ['predecessor','successor']}
   ratios=[]
   for block in range(4):
    pair={r['label']:r for r in rows if r['block']==block};ratios.append(statistics.median(pair['successor'][operation+'_seconds'])/statistics.median(pair['predecessor'][operation+'_seconds']))
   case['operations'][operation]=dict(ratio=med['successor']/med['predecessor'],paired=ratios,medians=med,all_over_5_percent=all(v>1.05 for v in ratios))
  results.append(case)
 (folder/'paired-analysis.json').write_text(json.dumps(results,indent=2)+'\n')
 print(json.dumps(dict(label=folder.name,results=[dict(case=[r[k] for k in keys],encode=round(r['operations']['encode']['ratio'],4),decode=round(r['operations']['decode']['ratio'],4),decode_paired=[round(v,4) for v in r['operations']['decode']['paired']]) for r in results])),flush=True)
assert {label:hashlib.sha256(path.read_bytes()).hexdigest() for label,path in binaries.items()}==hashes,'A benchmark binary changed during timing'
