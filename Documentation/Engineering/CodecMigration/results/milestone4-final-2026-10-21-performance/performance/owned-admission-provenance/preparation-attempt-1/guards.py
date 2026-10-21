#!/usr/bin/env python3
"""Identity guards for the fixed distinct admission-source measurements."""
import hashlib,json,pathlib,subprocess,xml.etree.ElementTree as ET
HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CANDIDATE_ROOT=ROOT/'work/m4-owned-admission-diagnostic'
REFERENCE_ROOT=ROOT/'work/m4-short-path-diagnostic'
BASE='bee49a2ad47eae4ea149bdced2043b7a45df3dae'
PINNED='15aa75164145414f3d5ffb801401c52d40cc5bcc'
CONSUMER='27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'


def require(value,message):
    if not value: raise RuntimeError(message)


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path): return json.loads(path.read_text())
def record(command,env,cwd=ROOT):
    r=subprocess.run(command,capture_output=True,text=True,env=env,cwd=cwd)
    return dict(command=command,exit_code=r.returncode,output=r.stdout+r.stderr)


def inventory(folder):
    paths=[folder/'Package.swift',folder/'VERSION']
    paths += [p for p in (folder/'Sources').rglob('*') if p.is_file()]
    paths += [p for p in (folder/'Tests').rglob('*.swift') if p.is_file()]
    require(all(not p.is_symlink() for p in paths),'Symlink in source inventory')
    return {str(p.relative_to(folder)):sha(p) for p in sorted(paths)}


def snapshot(folder,expected):
    identity=read(folder/'build-identity.json'); source=identity['source']
    require(sha(folder/'build-identity.json')==expected['build_identity_sha256'],'Frozen build record changed')
    require(source==read(folder/'source-identity.json'),'Source/build records differ')
    require(source['base_source']==BASE and source['developer_dir']=='/Library/Developer/CommandLineTools','Build base/toolchain differs')
    require(identity['command']['exit_code']==0 and identity['source_unchanged'] and identity['consumer_unchanged'],'Unsuccessful or changed build')
    require(identity['release']['exit_code']==0 and identity['asan']['exit_code']==0,'Focused validation failed')
    require(source['source_files']==inventory(folder/'codec'),'Frozen source changed')
    for name,digest in source['patches'].items(): require(sha(folder/name)==digest,'Frozen patch changed: '+name)
    require(sha(folder/'consumer/Sources/Benchmark/main.swift')==source['consumer_sha256']==CONSUMER,'Original Consumer differs')
    require(sha(folder/'consumer/Package.swift')==source['consumer_package_sha256'],'Consumer package differs')
    require(identity['binary_sha256']==expected['binary_sha256']==sha(pathlib.Path(identity['binary'])),'Frozen binary changed')
    for evidence in expected['validation_files']:
        path=folder/evidence['path']; require(sha(path)==evidence['sha256'],'Validation XML changed')
        cases=ET.parse(path).findall('.//testcase')
        require(len(cases)==evidence['tests'] and cases and all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases),'Validation XML incomplete')
    return identity


def admit_conditions(value):
    require(value['power']['exit_code']==0 and "Now drawing from 'AC Power'" in value['power']['output'],'AC power required; partial evidence retained')
    require(value['thermal']['exit_code']==0 and 'No thermal warning level has been recorded' in value['thermal']['output'] and 'No performance warning level has been recorded' in value['thermal']['output'],'Thermal/performance admission failed; partial evidence retained')


def source_guards(env):
    frozen=read(HERE/'plan.json')
    for name,digest in frozen['script_sha256'].items(): require(sha(HERE/name)==digest,'Frozen measurement script changed: '+name)
    for name,digest in frozen['schedule_sha256'].items(): require(sha(HERE/'schedules'/name)==digest,'Frozen schedule changed: '+name)
    require(sha(HERE/'analyse.py')=='62d00e3776e7cad0199c68fd87e2e955ab5eb7a70c866c6196f5fe685d17d186','128 analysis differs from original frozen method')
    candidate=snapshot(CANDIDATE_ROOT,frozen['candidate']); reference=snapshot(REFERENCE_ROOT,frozen['three_change'])
    preflight=candidate['preflight']
    expected={f'37x23-{pattern}-p{bits}' for bits in (12,16) for pattern in ('flat','ramp','noise')}
    require(preflight['all_six_passed'] is True and {c['case'] for c in preflight['cases']}==expected and len(preflight['cases'])==6 and all(c['exit_code']==0 and c['full_sample_verification']=='passed' for c in preflight['cases']),'Six-case full-sample preflight failed')
    require(inventory(ROOT)==reference['source']['source_files'],'Production tree changed during isolated experiment')
    for evidence in frozen['candidate']['preflight_files']:
        require(sha(CANDIDATE_ROOT/evidence['path'])==evidence['sha256'],'Candidate preflight changed')
    head=record(['git','rev-parse','HEAD'],env)
    require(head['output'].strip()==frozen['production_head_at_plan'],'Production HEAD changed during isolated experiment')
    pinned_head=record(['git','rev-parse','HEAD'],env,ROOT.parent/'JLSwift')
    pinned_diff=record(['git','diff','--exit-code',PINNED,'--','Sources','Package.swift'],env,ROOT.parent/'JLSwift')
    require(pinned_head['output'].strip()==PINNED and pinned_diff['exit_code']==0,'Pinned predecessor changed')
    predecessor=ROOT/'work/m4-benchmark/predecessor/.build/release/Benchmark'
    require(sha(predecessor)==frozen['pinned']['binary_sha256'],'Pinned binary changed')
    require(sha(ROOT/'Scripts/Benchmark/Consumer.swift')==sha(ROOT/'work/m4-benchmark/predecessor/Sources/Benchmark/main.swift')==CONSUMER,'Common Consumer changed')
    swift=record(['swift','--version'],env)
    require(swift['output']==candidate['source']['swift']==reference['source']['swift'],'Compiler differs from frozen builds')
    return dict(plan_sha256=sha(HERE/'plan.json'),production_head=head,pinned_head=pinned_head,pinned_diff=pinned_diff,swift=swift,
        candidate_build_identity_sha256=frozen['candidate']['build_identity_sha256'],candidate_binary_sha256=frozen['candidate']['binary_sha256'],
        candidate_source_files=candidate['source']['source_files'],reference_build_identity_sha256=frozen['three_change']['build_identity_sha256'],
        reference_binary_sha256=frozen['three_change']['binary_sha256'],pinned_binary_sha256=frozen['pinned']['binary_sha256'],
        exact_production_tree_matches_three_change_reference=True)
