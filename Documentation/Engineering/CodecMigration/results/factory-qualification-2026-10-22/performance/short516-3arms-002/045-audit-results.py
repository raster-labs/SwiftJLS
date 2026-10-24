"""Independent receipt and scalar-statistics audit; does not run benchmarks."""
from pathlib import Path
import collections, datetime, hashlib, json, math, statistics

ROOT = Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch')
OUT = Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022')
REPO = Path('/Users/pushparaj/projects/SwiftJLS')
OPS = ['encode', 'decode', 'prepare', 'prepare_encode']
PREFLIGHT = {'short516_runner.py': '625695877ec9236653eae284e908b93b2f49ebac21a3d4dbd28bd762966b6b62', 'larger15_runner.py': '0a46e04b46f028d480359ec4653a49eba863fd59498f012b67f51a6589993d69', 'short516_analyse.py': 'f72c4294b16ffd6e04919468980275e538102207e2d8204590f5f40faa8c7746', 'schedules/short516-3arms-002.json': 'f9c0a901120c14be71775daa96b5cdf3d19fe0f30f0d17e3e225772fb7c425bc', 'schedules/larger15-guard-002.json': 'e3580c90c8f0bb7e1d8bfd0dd65518fd6691cf2d9eeb7ea2cb53de43e1de2c0e'}
errors = []
def check(v, note):
    if not v: errors.append(note)
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(p): return json.loads(p.read_text())
def lines(p): return [json.loads(s) for s in p.read_text().splitlines()]
def eq(a,b,note): check(math.isclose(a,b,rel_tol=1e-13,abs_tol=1e-18),note)
def quantile(values,q):
    s=sorted(values);x=(len(s)-1)*q;i=int(x);return s[i]+(s[min(i+1,len(s)-1)]-s[i])*(x-i)
def ratio(rows,op,ref,cand):
    med={a:statistics.median(v for r in rows if r['producer']==a for v in r[op+'_seconds']) for a in [ref,cand]}
    return med[cand]/med[ref]

reports={}
for name, expected_count in [('short516-3arms-002',9288),('larger15-guard-002',120)]:
    before=len(errors); short=name.startswith('short');p=ROOT/'campaigns'/name
    plan=read(p/'frozen_schedule.json');complete=read(p/'complete.json');env=read(p/'environment.json')
    rows=lines(p/'raw.jsonl');events=lines(p/'events.jsonl');conditions=lines(p/'conditions.jsonl');summary=read(p/'summary.json')
    check(complete['completed'] is True and complete['processes']==expected_count,name+' completion')
    check(len(rows)==len(events)==expected_count,name+' counts')
    check(not (p/'interrupted.json').exists(),name+' interrupted marker')
    for f in ['raw.jsonl','events.jsonl','conditions.jsonl','summary.json']:
        check(sha(p/f)==complete[f.replace('.','_')+'_sha256'],name+' '+f+' digest')
    schedule_key='schedules/short516-3arms-002.json' if short else 'schedules/larger15-guard-002.json'
    check(sha(p/'frozen_schedule.json')==complete['schedule_sha256']==PREFLIGHT[schedule_key],name+' schedule digest')
    runner='short516_runner.py' if short else 'larger15_runner.py'
    check(sha(ROOT/'confirmation_plan'/runner)==complete['runner_sha256']==env['runner_sha256']==PREFLIGHT[runner],name+' runner digest')
    if short:
        check(sha(p/'frozen_analyse.py')==complete['analysis_sha256']==env['analyse_sha256']==PREFLIGHT['short516_analyse.py'],name+' analysis digest')
        check(read(p/'analysis-command.json')['exit_code']==0,name+' analysis exit')
    else:
        check(sha(p/'frozen_runner.py')==PREFLIGHT[runner],name+' frozen runner digest')
        check(sha(p/'frozen_larger_guard_plan.json')==complete['larger_guard_plan_sha256']==env['larger_guard_plan_sha256'],name+' original plan digest')
    check(env['source_guards']==complete['source_guards'],name+' initial/end identity')
    check(set(complete['source_guards']['all_swiftjls_source_hashes'])=={str(f.relative_to(REPO)) for f in (REPO/'Sources/SwiftJLS').rglob('*.swift')},name+' complete current source set')
    for rel,digest in complete['source_guards']['all_swiftjls_source_hashes'].items(): check(sha(REPO/rel)==digest,name+' current source '+rel)
    for arm,meta in plan['producers'].items(): check(sha(Path(meta['path']))==meta['sha256'],name+' binary '+arm)
    schedule=[(e,a) for e in plan['schedule'] for a in e['order']]
    check(len(schedule)==expected_count,name+' schedule length')
    seen=set();last_end='';lookup={};stderr_count=0
    for i,((entry,arm),r,event) in enumerate(zip(schedule,rows,events)):
        note=f'{name} row {i}'
        key=(r['case_id'],r['block'],r['producer']);check(key not in seen,note+' duplicate');seen.add(key);lookup[key]=r
        check(event['entry']==entry and event['producer']==arm,note+' actual order')
        check(r['case_id']==entry['case']['id'] and r['block']==entry['block'] and r['position']==entry['position'] and r['order']==entry['order'] and r['producer']==arm,note+' schedule metadata')
        parsed=json.loads(event['stdout'])
        check(all(r[k]==v for k,v in parsed.items()),note+' stdout/raw mismatch')
        check(all(r[k]==event[k] for k in ['command','exit_code','stderr','started_utc','completed_utc','process_seconds']),note+' receipt mismatch')
        check(event['exit_code']==0,note+' failed exit');stderr_count+=bool(r['stderr'])
        check(r['started_utc']>=last_end and r['completed_utc']>=r['started_utc'],note+' timestamp overlap');last_end=r['completed_utc']
        c=entry['case'];cmd=[plan['producers'][arm]['path'],str(c['width']),str(c['height']),str(c['bits']),c['pattern'],'5','5',arm]
        if not short:cmd += [str(c['components']),str(c['near']),str(c['interleave'])]
        check(r['command']==cmd,note+' command')
        check(r['binary_sha256']==plan['producers'][arm]['sha256'],note+' binary metadata')
        check(all(r[k]==v for k,v in c.items() if k not in ['id','expected_encoded_bytes']),note+' case fields')
        check(r['warmups']==r['iterations']==5 and r['end_to_end'] is True and r['resource_profile']=='successor-workspace-1GiB-memory-2GiB-v1',note+' consumer profile')
        if short:check(r['encoded_bytes']==c['expected_encoded_bytes'],note+' encoded bytes')
        for op in OPS:check(len(r[op+'_seconds'])==5 and all(type(v) in [float,int] and math.isfinite(v) and v>0 for v in r[op+'_seconds']),note+' observations')
        check(all(a>=b for a,b in zip(r['prepare_encode_seconds'],r['prepare_seconds'])),note+' combined time')
    arms=list(plan['producers']);per_case={};metric_results=[]
    for case in plan['cases']:
        cid=case['id'];cr=[r for r in rows if r['case_id']==cid]
        orders=collections.Counter(tuple(r['order']) for r in cr if r['producer']==arms[0])
        check(sorted(orders.values())==([86]*6 if short else [2]*2),name+' balance '+cid)
        per_case[cid]={'processes':len(cr),'encoded_bytes':{a:sorted({r['encoded_bytes'] for r in cr if r['producer']==a}) for a in arms}}
    compare=[('candidate_vs_pinned','pinned','candidate'),('candidate_vs_three_change','three_change','candidate')] if short else [('candidate_vs_pinned','reference','candidate')]
    for comp,ref,cand in compare:
        result_rows=summary[comp] if short else summary
        check(len(result_rows)==len(plan['cases']),name+' summary case count')
        for result in result_rows:
            cid=result['case']['id'];cr=[r for r in rows if r['case_id']==cid]
            if not short:
                sizes={a:{r['encoded_bytes'] for r in cr if r['producer']==a} for a in [ref,cand]}
                check(all(len(v)==1 for v in sizes.values()),name+' stable sizes '+cid)
                sz={a:next(iter(v)) for a,v in sizes.items()};stored=result['encoded_bytes']
                check(all(stored[a]==sz[a] for a in [ref,cand]) and stored['delta_bytes']==sz[cand]-sz[ref],name+' size summary '+cid)
                eq(sz[cand]/sz[ref],stored['ratio'],name+' size ratio '+cid)
                known=(cid=='4096x3073-p12-flat-c3-n0-i2' and sz[ref]==2115 and sz[cand]==2159)
                check(stored['explained_spiff_header_difference']==known,name+' specific SPIFF rule '+cid)
                check(stored['retained_for_review']==(sz[cand]!=sz[ref] and not known),name+' retained size delta '+cid)
                rss={a:[r['peak_process_rss_bytes'] for r in cr if r['producer']==a] for a in [ref,cand]};rssmed={a:statistics.median(v) for a,v in rss.items()}
                check(result['peak_process_rss_bytes']['observations']==rss,name+' RSS observations '+cid)
                check(result['peak_process_rss_bytes']['median']==rssmed,name+' RSS medians '+cid)
                eq(rssmed[cand]/rssmed[ref],result['peak_process_rss_bytes']['ratio'],name+' RSS ratio '+cid)
            for op,s in result['operations'].items():
                note=f'{name}/{comp}/{cid}/{op}';check(op in OPS,note+' operation')
                pooled=ratio(cr,op,ref,cand);eq(pooled,s['pooled_ratio'],note+' pooled ratio')
                for a,m in s['pooled_median_seconds'].items():eq(statistics.median(v for r in cr if r['producer']==a for v in r[op+'_seconds']),m,note+' median '+a)
                pairs=[];deltas=[]
                for b in range(plan['blocks_per_case']):
                    rr=lookup[(cid,b,ref)];cc=lookup[(cid,b,cand)];rm=statistics.median(rr[op+'_seconds']);cm=statistics.median(cc[op+'_seconds']);x=cm/rm;pairs.append(x);deltas.append(cm-rm)
                    stored=s['pairs'][b];check(stored['block']==b and stored['order']==rr['order'],note+' pair order');eq(x,stored['ratio'],note+' pair ratio');eq(cm-rm,stored['delta_seconds'],note+' pair delta')
                    eq(rm,stored['reference_median_seconds'],note+' reference pair median');eq(cm,stored['candidate_median_seconds'],note+' candidate pair median')
                eq(statistics.median(pairs),s['median_block_ratio'],note+' block median');eq(statistics.median(deltas),s['median_block_delta_seconds'],note+' delta median')
                check([min(pairs),max(pairs)]==s['ratio_range'],note+' range');eq(quantile(pairs,.25),s['ratio_iqr'][0],note+' q25');eq(quantile(pairs,.75),s['ratio_iqr'][1],note+' q75')
                check(sum(x>1.05 for x in pairs)==s['blocks_above_1_05'],note+' slower block count')
                record={'comparison':comp,'case':cid,'operation':op,'ratio':pooled,'paired_range':s['ratio_range'],'blocks_above_1_05':s['blocks_above_1_05']}
                if short:
                    for interval,interpretation in [('familywise_bonferroni_48_95','interpretation_family48'),('historical_bonferroni_24_95','interpretation_historical_family24')]:
                        lo,hi=s[interval];expected='within_measured_gate' if hi<=1.05 else ('confirmed_regression' if lo>1.05 else 'unresolved')
                        check(s[interpretation]==expected,note+' decision '+interval)
                    for label,g in s['order_groups'].items():
                        first=ref if label==ref+'_before_'+cand else cand
                        selected=[r for r in cr if (r['order'].index(ref)<r['order'].index(cand))==(first==ref)]
                        eq(ratio(selected,op,ref,cand),g['pooled_ratio'],note+' order pooled')
                    for label,g in s['permutation_groups'].items():eq(ratio([r for r in cr if '->'.join(r['order'])==label],op,ref,cand),g['pooled_ratio'],note+' permutation pooled')
                    for g in s['temporal_groups']:eq(ratio([r for r in cr if g['first_round']<=r['block']<=g['last_round']],op,ref,cand),g['pooled_ratio'],note+' temporal pooled')
                    for key in ['familywise_bonferroni_48_95','interpretation_family48','historical_bonferroni_24_95','interpretation_historical_family24']:record[key]=s[key]
                else:
                    eq(statistics.stdev(pairs),s['ratio_sample_standard_deviation'],note+' stdev')
                    for first,value in s['median_ratio_by_first_producer'].items():eq(statistics.median(pairs[b] for b in range(4) if lookup[(cid,b,ref)]['order'][0]==first),value,note+' first producer median')
                metric_results.append(record)
    allcond=[env['conditions']]+conditions+[complete['end_conditions']]
    for i,c in enumerate(allcond):
        check(c['power']['exit_code']==0 and "Now drawing from 'AC Power'" in c['power']['output'],name+f' AC {i}')
        check(c['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in c['thermal']['output'] and 'No performance warning level has been recorded' in c['thermal']['output'],name+f' thermal {i}')
    check(all(a['utc']<=b['utc'] and a['completed_processes']<=b['completed_processes'] for a,b in zip(conditions,conditions[1:])),name+' conditions order')
    step=18 if short else 30
    check(set(range(0,expected_count+1,step))<=set(c['completed_processes'] for c in conditions),name+' round condition coverage')
    cpu=collections.defaultdict(list)
    for c in allcond:
        for proc in c['processes_above_10_percent']:cpu[proc['comm']].append(proc['cpu'])
    reports[name]={'errors':errors[before:],'counts':{'raw':len(rows),'events':len(events),'conditions':len(conditions),'metrics':len(metric_results),'stderr_nonempty':stderr_count},'start':rows[0]['started_utc'],'end':rows[-1]['completed_utc'],'condition_cpu_range':[min(c['summed_cpu_percent'] for c in allcond),max(c['summed_cpu_percent'] for c in allcond)],'cpu_processes':[{'command':k,'seen':len(v),'maximum_cpu':max(v)} for k,v in sorted(cpu.items(),key=lambda x:max(x[1]),reverse=True)],'cases':per_case,'metrics':metric_results}
    if not short:reports[name]['size_results']=[{'case':r['case']['id'],**r['encoded_bytes']} for r in summary]
check(reports['short516-3arms-002']['end']<reports['larger15-guard-002']['start'],'campaigns overlap')
(OUT/'045-independent-results.json').write_text(json.dumps({'errors':errors,'campaigns':reports},indent=2)+'\n')
for name,r in reports.items():
    print(name,r['counts'],'errors',r['errors'],'cpu',r['condition_cpu_range'])
    if name.startswith('short'):
        print('short dispositions',dict(collections.Counter(m['interpretation_family48'] for m in r['metrics'])))
        for m in r['metrics']:
            if m['interpretation_family48']!='within_measured_gate':print(m)
    else:
        for m in r['metrics']:
            if m['ratio']>1.05:print('larger point ratio above1.05',m)
print('total_errors',len(errors))
