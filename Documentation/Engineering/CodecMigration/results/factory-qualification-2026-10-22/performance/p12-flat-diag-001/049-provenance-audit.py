from pathlib import Path
import hashlib,json,datetime,math,re,struct,difflib
D=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/p12_flat_prepare_encode_diag_001')
O=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022')
S=D.parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
inv=lambda p:{str(f.relative_to(p)):sha(f) for f in sorted((p/'Sources/SwiftJLS').rglob('*.swift'))}
errors=[]
def ck(x,s):
 if not x:errors.append(s)
files=[D/'prepare-receipt.json',D/'prepare-build-events.jsonl',D/'prepare-smoke-receipts.json',D/'prepare_p12_flat_diag.py']
before={str(f):sha(f) for f in files}
r=json.loads(files[0].read_text());events={x['arm']:x for x in map(json.loads,files[1].read_text().splitlines())};smokes={x['arm']:x for x in json.loads(files[2].read_text())}
ck(sha(r['build_events_jsonl'])==r['build_events_sha256'],'build receipt hash');ck(sha(r['smoke_receipts_json'])==r['smoke_receipts_sha256'],'smoke receipt hash')
roots={'three_change_ref':Path('/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS/work/m4-short-path-diagnostic/codec'),'admission_001':S/'perf_ablation_arms/arm_owned_admission_only','factory_002':S/'snapshots/apple-rss-final-003/arm_candidate'}
roots['factory_002_zero_icc']=roots['factory_002'];roots['three_change_inst']=roots['three_change_ref'];roots['factory_002_inst']=roots['factory_002']
class Unpack:
 def __init__(self,b):self.b=b;self.i=0
 def take(self,n):r=self.b[self.i:self.i+n];self.i+=n;return r
 def num(self,n):return int.from_bytes(self.take(n),'big')
 def one(self):
  x=self.num(1)
  if x<128:return x
  if x>=224:return x-256
  if 160<=x<=191:return self.take(x-160).decode('utf-8','replace')
  if 144<=x<=159:return [self.one() for _ in range(x-144)]
  if 128<=x<=143:return [(self.one(),self.one()) for _ in range(x-128)]
  if x in [192,194,195]:return {192:None,194:False,195:True}[x]
  if x in [196,197,198]:return self.take(self.num({196:1,197:2,198:4}[x]))
  if x in [202,203]:return struct.unpack('>f' if x==202 else '>d',self.take(4 if x==202 else 8))[0]
  if 204<=x<=207:return self.num(2**(x-204))
  if 208<=x<=211:return int.from_bytes(self.take(2**(x-208)),'big',signed=True)
  if x in [217,218,219]:return self.take(self.num({217:1,218:2,219:4}[x])).decode('utf-8','replace')
  if x in [220,221]:return [self.one() for _ in range(self.num(2 if x==220 else 4))]
  if x in [222,223]:return [(self.one(),self.one()) for _ in range(self.num(2 if x==222 else 4))]
  if 212<=x<=216:return ('ext',self.take(1+2**(x-212)))
  if 199<=x<=201:return ('ext',self.take(self.num(2**(x-199))+1))
  raise ValueError((x,self.i))
def walk(x):
 if isinstance(x,(list,tuple)):
  if '-module-name' in x and all(isinstance(v,str) for v in x):yield x
  for v in x:yield from walk(v)
report={};normalized={}
for arm,a in r['arms'].items():
 p=Path(a['package_dir']);actual=inv(p);original=inv(roots[arm]);ck(actual==a['swiftjls_files'],arm+' sourcehashes/set');ck(len(actual)==a['swiftjls_file_count'],arm+' sourcecount');ck(set(actual)==set(original),arm+' original fileset')
 changed=[k for k in actual if actual[k]!=original[k]]
 expected=['Sources/SwiftJLS/JPEGLS/ScalarCodec.swift'] if arm.endswith('zero_icc') else (['Sources/SwiftJLS/CodecAPI.swift'] if arm.endswith('_inst') else [])
 ck(changed==expected,arm+' exact changed files')
 for key in ['consumer','task_store']:
  ck(sha(a[key+'_path'])==a[key+'_sha256'],arm+' '+key)
 ck(sha(p/'Package.swift')==a['package_swift_sha256']==r['package_swift_sha256'],arm+' package')
 ck(a['consumer_sha256']==r['instrumented_consumer_sha256' if arm.endswith('_inst') else 'ordinary_consumer_sha256'],arm+' selectedconsumer')
 ck(sha(a['built_binary_path'])==sha(a['copied_binary_path'])==a['binary_sha256'],arm+' binaries')
 for key,patch in a['patches'].items():
  ck(sha(patch['path'])==patch['sha256'],arm+' patch hash')
  rel='Sources/Benchmark/main.swift' if key=='Consumer.patch' else ('Sources/SwiftJLS/CodecAPI.swift' if key=='CodecAPI.patch' else 'Sources/SwiftJLS/JPEGLS/ScalarCodec.swift')
  source=Path('/Users/pushparaj/projects/SwiftJLS/Scripts/Benchmark/Consumer.swift') if key=='Consumer.patch' else roots[arm]/rel
  exact=''.join(difflib.unified_diff(source.read_text().splitlines(keepends=True),(p/rel).read_text().splitlines(keepends=True),fromfile='a/'+rel,tofile='b/'+rel))
  ck(exact==Path(patch['path']).read_text(),arm+' exact patch bytes')
 e=events[arm];ck(e['exit_code']==0 and e['stderr']=='',arm+' build status');ck(e['command']==['swift','build','-c','release','--package-path',str(p)],arm+' build command')
 mtime=Path(a['built_binary_path']).stat().st_mtime
 ck(datetime.datetime.fromisoformat(e['started_utc']).timestamp()<=mtime<=datetime.datetime.fromisoformat(e['completed_utc']).timestamp(),arm+' binary mtime in build')
 ck(max((p/k).stat().st_mtime for k in actual)<=mtime,arm+' source before binary')
 st=smokes[arm];data=json.loads(st['stdout']);ck(data==st['parsed'],arm+' smoke parsed');ck(st['exit_code']==0 and st['stderr']=='',arm+' smoke exit');ck(st['command']==[a['copied_binary_path'],'37','23','12','flat','5','5',arm],arm+' smoke command');ck(st['binary_sha256']==a['binary_sha256'],arm+' smoke identity')
 ck(e['completed_utc']<=st['started_utc']<st['completed_utc'],arm+' smoke order')
 for k,v in {'width':37,'height':23,'bits':12,'pattern':'flat','components':1,'near':0,'interleave':0,'warmups':5,'iterations':5,'end_to_end':True,'encoded_bytes':56,'label':arm}.items():ck(data[k]==v,arm+' smoke '+k)
 fields=['encode_seconds','decode_seconds','prepare_seconds','prepare_encode_seconds']+(['fresh_entry_seconds','fresh_body_seconds','fresh_exit_seconds'] if arm.endswith('_inst') else [])
 for k in fields:ck(len(data[k])==5 and all(math.isfinite(x) and x>0 for x in data[k]),arm+' smoke samples '+k)
 u=Unpack(Path(a['task_store_path']).read_bytes());commands=[]
 while u.i<len(u.b):
  for c in walk(u.one()):
   if c not in commands:commands.append(c)
 ck(len(commands)==2,arm+' two compiler commands')
 normalized[arm]={}
 for c in commands:
  module=c[c.index('-module-name')+1];n=[v.replace(str(p),'<PACKAGE>').replace(str(p.parent),'<ARM>') for v in c]
  normalized[arm][module]=n
  for flag in ['-O','-whole-module-optimization','-no-emit-module-separately-wmo']:ck(flag in c,arm+' '+flag)
  for flag,value in {'-swift-version':'6','-target':'arm64-apple-macos26.0','-sdk':'/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX27.0.sdk','-package-name':'perfdiagarm'}.items():ck(c[c.index(flag)+1]==value,arm+' '+flag)
 report[arm]={'source_count':len(actual),'source_changes_from_original':changed,'binary_sha256':a['binary_sha256'],'build_start':e['started_utc'],'build_end':e['completed_utc'],'smoke_exit':st['exit_code'],'compiler_commands':commands}
reference=normalized['three_change_ref']
for arm,c in normalized.items():ck(c==reference,arm+' normalized compiler equality')
after={str(f):sha(f) for f in files};ck(before==after,'audit input changed during read')
(O/'049-provenance-results.json').write_text(json.dumps({'errors':errors,'input_pins':after,'arms':report},indent=2)+'\n')
print('errors',errors)
for k,a in report.items():print(k,a['source_count'],a['source_changes_from_original'],a['binary_sha256'][:16])
print('pins',after)
