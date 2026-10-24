"""Source and artifact guards for the prospective candidate005 campaigns; no collection."""
import hashlib,json,os,pathlib,subprocess
HERE=pathlib.Path(__file__).resolve().parent
REPO=pathlib.Path('/Users/pushparaj/projects/SwiftJLS')
CONSUMER='27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'
PACKAGE='b8c00c41dda983f6cee24c45f3e352ebde71c0f25b42abd379a431f1a556394b'
def sha(p):return hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
def require(c,m):
 if not c:raise RuntimeError(m)
def config():return json.loads((HERE/'identity.json').read_text())
def verify(env=None):
 c=config();env=env or os.environ
 for name,want in c['artifacts'].items():require(sha(name)==want,'Artifact changed: '+name)
 r=json.loads(pathlib.Path(c['receipt']).read_text());root=pathlib.Path(c['receipt']).parent
 pins=json.loads((root/'all-source-pins.json').read_text())
 for n,h in pins.items():require(sha(REPO/n)==h,'Repository source changed: '+n)
 sources={str(p.relative_to(REPO)):sha(p) for p in sorted((REPO/'Sources/SwiftJLS').rglob('*.swift'))}
 tests={str(p.relative_to(REPO)):sha(p) for p in sorted((REPO/'Tests/SwiftJLSTests').rglob('*.swift'))}
 arm=root/'arm_candidate';snap={str(p.relative_to(arm)):sha(p) for p in sorted((arm/'Sources/SwiftJLS').rglob('*.swift'))}
 require(sources==snap==r['swiftjls_file_sha256'],'Exact library file sets/bytes differ')
 require(tests==r['test_file_sha256'],'Exact test file sets/bytes differ')
 require(sha(REPO/'Scripts/Benchmark/Consumer.swift')==sha(arm/'Sources/Benchmark/main.swift')==CONSUMER,'Consumer changed')
 require(sha(arm/'Package.swift')==PACKAGE,'Benchmark package changed')
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,env=env,text=True).strip()
 require(head==r['base_head'],'Repository HEAD changed')
 for name,b in c['binaries'].items():require(sha(b['path'])==b['sha256'],'Binary changed: '+name)
 return {'candidate':r['candidate'],'repo_head':head,'receipt_sha256':sha(c['receipt']),'all_source_pins_sha256':sha(root/'all-source-pins.json'),'consumer_sha256':CONSUMER,'package_swift_sha256':PACKAGE,'production_files':len(sources),'test_files':len(tests),'binary_sha256':{k:v['sha256'] for k,v in c['binaries'].items()},'host_scope':'shared services running; no claim of host idleness'}

# Freeze is generated only after deterministic schedules. Verify it on every source guard.
_original_verify=verify
_FREEZE_SHA=sha(HERE/'campaign-freeze.json') if (HERE/'campaign-freeze.json').exists() else None
def verify(env=None):
 require(_FREEZE_SHA is not None,'Campaign package not prepared/frozen')
 require(sha(HERE/'campaign-freeze.json')==_FREEZE_SHA,'Campaign freeze changed during process')
 frozen=json.loads((HERE/'campaign-freeze.json').read_text())
 for n,h in frozen['files'].items():require(sha(HERE/n)==h,'Campaign file changed: '+n)
 return _original_verify(env)
