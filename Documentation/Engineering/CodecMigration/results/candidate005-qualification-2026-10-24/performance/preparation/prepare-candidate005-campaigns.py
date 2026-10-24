#!/usr/bin/env python3
"""Prepare external frozen campaigns only. Never builds or runs any benchmark."""
import argparse,ast,hashlib,json,pathlib,shutil,subprocess,sys
ROOT=pathlib.Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024')
TEMPLATES=pathlib.Path(__file__).resolve().parent
OLD=pathlib.Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/campaigns_004')
RSS=pathlib.Path('/Users/pushparaj/projects/SwiftJLS/Documentation/Engineering/CodecMigration/results/factory-qualification-2026-10-22/memory/apple-rss-112-002')
PYTHON=pathlib.Path('/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3')
PINS={'larger15_runner.py':'8dc2c61bbbe96471fdf3e48f0653bc864605d8732880b924fe3763487b13ad53','short516_runner.py':'9fa61c411f6c66d0f6553017344b1391928d03045dfe36f5757c878a3471b3af','short516_analyse.py':'f72c4294b16ffd6e04919468980275e538102207e2d8204590f5f40faa8c7746','diag72_runner.py':'41d857d93c6442ad31c446a2ee82ce86bcd3730bf5f3989f5a1e721108e1b5ea'}
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def require(v,m):
 if not v:raise RuntimeError(m)
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def replace_nodes(source,replacements):
 lines=source.splitlines(keepends=True);edits=[]
 for n in ast.parse(source).body:
  name=n.name if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) else n.targets[0].id if isinstance(n,ast.Assign) and isinstance(n.targets[0],ast.Name) else None
  if name in replacements:edits.append((n.lineno-1,n.end_lineno,replacements[name]+'\n'))
 require(len(edits)==len(replacements),'AST replacement mismatch')
 for first,last,value in sorted(edits,reverse=True):lines[first:last]=[value]
 return ''.join(lines)
def function(source,name):
 for n in ast.parse(source).body:
  if isinstance(n,ast.FunctionDef) and n.name==name:return ast.get_source_segment(source,n)
 raise ValueError(name)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--receipt',type=pathlib.Path,required=True);p.add_argument('--output',type=pathlib.Path,required=True);a=p.parse_args()
 receipt=a.receipt.resolve();r=json.loads(receipt.read_text());out=a.output.resolve();require(not out.exists(),'Fresh campaign output directory required');require(r['candidate']=='candidate_005','Wrong candidate')
 for n,h in PINS.items():require(sha(OLD/n)==h,'Accepted template changed: '+n)
 require(sha(RSS/'frozen_runner.py')=='ff90d4ca26cd6c6aa372c98b00e9d22954862c9ebe74b31bdf6e8aeccdcede53','RSS method template changed')
 require(r['consumer_sha256']=='27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34','Original Consumer required')
 require(sha(receipt.parent/'all-source-pins.json')==r['all_source_pins_sha256'],'Source pins receipt mismatch')
 require(sha(r['binaries']['Benchmark']['path'])==r['binaries']['Benchmark']['sha256'],'Candidate binary mismatch')
 require(len(r['validation'])==4 and {v['label'] for v in r['validation']}=={'release','debug','asan','tsan'},'Four validation configurations required')
 require(all(v['exit_code']==0 and not (v['failures'] or v['errors'] or v['skipped']) for v in r['validation']),'Validation failed/incomplete')
 out.mkdir();(out/'schedules').mkdir();(out/'baseline-provenance').mkdir()
 for n in ['campaign_identity.py','rss528_runner.py','preflight.py']:shutil.copy2(TEMPLATES/n,out/n)
 for n in ['short516_analyse.py','diag72_runner.py']:shutil.copy2(OLD/n,out/n)
 oldplan=json.loads((OLD/'schedules/short516-3arms-004.json').read_text());oldrss=json.loads((RSS/'frozen_schedule.json').read_text())
 producers={n:oldplan['producers'][n] for n in ['pinned','three_change']}
 candidate=dict(r['binaries']['Benchmark'],base_revision=r['base_head'],candidate=r['candidate'],build_receipt_path=str(receipt),build_receipt_sha256=sha(receipt),all_swiftjls_source_hashes=r['swiftjls_file_sha256'],all_test_hashes=r['test_file_sha256'])
 producers['candidate']=candidate
 binaries={n:{'path':v['path'],'sha256':v['sha256']} for n,v in producers.items()}
 for label in ['62309d3','e66f7da']:
  old=oldrss['arms'][label];binaries[label]={'path':old['benchmark_binary_path'],'sha256':old['benchmark_binary_sha256'],'revision':old['revision']}
 for n,b in binaries.items():require(sha(b['path'])==b['sha256'],'Frozen binary absent/changed: '+n)
 shutil.copy2(OLD/'schedules/short516-3arms-004.json',out/'baseline-provenance/short004-schedule.json');shutil.copy2(RSS/'frozen_schedule.json',out/'baseline-provenance/rss002-schedule.json')
 artifacts={str(receipt):sha(receipt),str(receipt.parent/'all-source-pins.json'):sha(receipt.parent/'all-source-pins.json'),str(receipt.parent/'events.jsonl'):sha(receipt.parent/'events.jsonl')}
 # Pin actual build descriptions if emitted by this build; never invent an XCBuildData path.
 for n in sorted((receipt.parent/'arm_candidate/.build').rglob('description.json')):artifacts[str(n)]=sha(n)
 for n in sorted((receipt.parent/'arm_candidate/.build').rglob('swift-version*.txt')):artifacts[str(n)]=sha(n)
 write(out/'identity.json',{'schema':1,'receipt':str(receipt),'artifacts':artifacts,'binaries':binaries,'accepted_templates':PINS,'host_scope':'shared host; services remain running'})
 short=(OLD/'short516_runner.py').read_text();short=replace_nodes(short,{'ALL_CANDIDATE_SWIFTJLS_HASHES':'ALL_CANDIDATE_SWIFTJLS_HASHES = '+repr(r['swiftjls_file_sha256']),'PRODUCERS':'PRODUCERS = '+repr(producers),'source_guards':'def source_guards(env):\n    from campaign_identity import verify\n    return verify(env)'})
 short=short.replace('short516-3arms-004.json','short516-3arms-005.json').replace('candidate (1db8b6a3)','candidate005 (receipt-pinned)').replace('guards all 38 Sources/SwiftJLS files against the admitted candidate snapshot','guards the exact library/test/source inventory against the admitted candidate receipt')
 short=short.replace('    ALL_CANDIDATE_TEST_HASHES,\n','')
 short=short.replace('    output.mkdir(parents=True)\n','    output.mkdir(parents=True)\n    for name in ["campaign_identity.py", "identity.json", "campaign-freeze.json"]:\n        shutil.copy2(HERE / name, output / name)\n')
 (out/'short516_runner.py').write_text(short)
 larger=(OLD/'larger15_runner.py').read_text()
 larger=replace_nodes(larger,{'ALL_CANDIDATE_SWIFTJLS_HASHES':'ALL_CANDIDATE_SWIFTJLS_HASHES = '+repr(r['swiftjls_file_sha256']),'PRODUCERS':'PRODUCERS = '+repr({'reference':producers['pinned'],'candidate':candidate}),'source_guards':'def source_guards(env):\n    require(sha(LARGER_PLAN_PATH) == LARGER_PLAN_SHA, "Larger original plan changed")\n    from campaign_identity import verify\n    return verify(env)','LARGER_PLAN_PATH':'LARGER_PLAN_PATH = HERE / "larger-guard-plan.json"'})
 original_larger=pathlib.Path('/Users/pushparaj/projects/SwiftJLS/Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21-performance/performance/larger-guard-plan.json')
 require(sha(original_larger)=='e53e2e11ff679398dbb5de160e72c08a53ca5809fb2117e42777510158048bef','Original larger plan changed')
 shutil.copy2(original_larger,out/'larger-guard-plan.json')
 larger=larger.replace('    ALL_CANDIDATE_TEST_HASHES,\n','').replace('larger15-guard-004.json','larger15-guard-005.json').replace('candidate (1db8b6a3)','candidate005 (receipt-pinned)')
 larger=larger.replace('    output.mkdir(parents=True)\n','    output.mkdir(parents=True)\n    for name in ["campaign_identity.py", "identity.json", "campaign-freeze.json"]:\n        shutil.copy2(HERE / name, output / name)\n')
 (out/'larger15_runner.py').write_text(larger)
 old=(RSS/'frozen_runner.py').read_text()
 names=['require','validate_part2_report','evaluate_part2_dispositions','self_test','analyse_part2']
 funcs={n:function(old,n) for n in names}
 stats='''#!/usr/bin/env python3
"""RSS528: original full-process peak metric, four contrasts, finite-max gate; whole-block bootstrap."""
import hashlib,json,math,statistics,sys
import numpy as np
SEED=20261022
RESAMPLES=50000
BLOCKS=528
TAIL_4=.05/(2*4)
OPERATIONS=['encode','decode','prepare','prepare_encode']
LABELS_PART2=['62309d3','e66f7da','candidate','candidate-copy']
COMPARISONS_PART2=[('e66_vs_623','62309d3','e66f7da'),('candidate_vs_623','62309d3','candidate'),('candidate_vs_e66','e66f7da','candidate'),('candidate_copy_vs_candidate','candidate','candidate-copy')]
'''
 # Preserve one full draw matrix and the original RNG stream, chunk only temporary gathered values.
 stats+=funcs['require']+'\n\n'+'''def bootstrap_part2_rss(rss_matrix,n=RESAMPLES):
    require(rss_matrix.shape==(4,BLOCKS),'Invalid matrix shape')
    rng=np.random.default_rng(SEED)
    indices=rng.integers(0,BLOCKS,size=(n,BLOCKS),dtype=np.int16)
    ratios={name:np.empty(n,dtype=np.float64) for name,_,_ in COMPARISONS_PART2}
    for first in range(0,n,512):
        sampled=np.take(rss_matrix,indices[first:first+512],axis=1)
        medians=np.median(sampled,axis=2)
        for name,ref,cand in COMPARISONS_PART2:
            ratios[name][first:first+512]=medians[LABELS_PART2.index(cand)]/medians[LABELS_PART2.index(ref)]
    return indices,ratios
\n'''
 for n in names[1:]:
  f=funcs[n]
  if n=='self_test':f=f.replace('joint 24-block','joint 528-block')
  if n=='analyse_part2':
   f=f.replace('len(records) == 96','len(records) == BLOCKS * 4').replace('Expected 96 Part 2 records','Expected 2112 Part 2 records')
   f=f.replace('len(pos_vals) == 6','len(pos_vals) == BLOCKS // 4').replace('Expected 6 runs','Expected 132 runs').replace('"count": 6','"count": BLOCKS // 4')
   f=f.replace('len(ref_first_blks) == 12 and len(cand_first_blks) == 12','len(ref_first_blks) == BLOCKS // 2 and len(cand_first_blks) == BLOCKS // 2').replace('"blocks": 12','"blocks": BLOCKS // 2')
   f=f.replace('range(0, BLOCKS, 6)','range(0, BLOCKS, BLOCKS // 4)').replace('first : first + 6','first : first + BLOCKS // 4').replace('first + 5','first + BLOCKS // 4 - 1')
  stats+=f+'\n\n'
 stats+='''if __name__=='__main__':
    import argparse,pathlib
    p=argparse.ArgumentParser();p.add_argument('--self-test',action='store_true');p.add_argument('--raw',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args()
    if a.self_test:print(json.dumps(self_test(),indent=2))
    else:
        require(a.raw is not None and a.output is not None,'--raw and --output required')
        require(not a.output.exists(),'Fresh analysis output required')
        records=[json.loads(x) for x in a.raw.read_text().splitlines()]
        a.output.write_text(json.dumps(analyse_part2(records),indent=2)+'\\n')
'''
 (out/'rss528_analyse.py').write_text(stats)
 # Pure schedule generation only; no identity/preflight/binary execution.
 for name in ['short516_runner.py','larger15_runner.py','rss528_runner.py']:subprocess.run([str(PYTHON),str(out/name),'--prepare'],check=True)
 for path in out.glob('*.py'):compile(path.read_text(),str(path),'exec')
 files={str(p.relative_to(out)):sha(p) for p in sorted(out.rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
 write(out/'campaign-freeze.json',{'schema':1,'candidate':'candidate_005','files':files,'preparation_script_sha256':sha(__file__),'receipt_sha256':sha(receipt),'collection_authorised':False,'note':'Source/root review and fresh host preflight remain required. This preparation has not run benchmarks.'})
 print('PREPARED',out,'FREEZE',sha(out/'campaign-freeze.json'))
if __name__=='__main__':main()
