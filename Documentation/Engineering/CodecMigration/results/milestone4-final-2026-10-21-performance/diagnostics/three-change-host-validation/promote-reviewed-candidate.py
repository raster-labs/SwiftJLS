#!/usr/bin/env python3
"""Apply only the reviewed three-change patch and record its precommit bridge."""
import datetime, hashlib, json, pathlib, subprocess

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE = ROOT/'work/m4-short-path-diagnostic'
BASE = 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'
EXPECTED_PATCH = '7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a'
OUT = HERE/'precommit-source-bridge.json'

def git(*args):
    return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def nonfixtures(folder):
    paths = [folder/'Package.swift',folder/'VERSION']
    for directory in ['Sources','Tests']:
        paths += [p for p in (folder/directory).rglob('*') if p.is_file()
                  and 'Tests/SwiftJLSTests/Fixtures/' not in str(p.relative_to(folder))]
    return {str(p.relative_to(folder)):sha(p) for p in sorted(paths)}

assert not OUT.exists(), 'Refusing to overwrite promotion provenance.'
source=json.loads((CANDIDATE/'source-identity.json').read_text())
build=json.loads((CANDIDATE/'build-identity.json').read_text())
assert git('rev-parse','HEAD')==BASE
assert not git('status','--porcelain','--untracked-files=all','--','Sources','Tests','Package.swift','VERSION')
assert sha(CANDIDATE/'combined.patch')==source['patches']['combined.patch']==EXPECTED_PATCH
assert nonfixtures(CANDIDATE/'codec')==source['source_files']
fixture_tree=git('rev-parse',BASE+':Tests/SwiftJLSTests/Fixtures')
assert fixture_tree==source['fixtures_tree']
subprocess.run(['git','apply','--check',str(CANDIDATE/'combined.patch')],cwd=ROOT,check=True)
subprocess.run(['git','apply',str(CANDIDATE/'combined.patch')],cwd=ROOT,check=True)
actual=nonfixtures(ROOT)
assert actual==source['source_files'], 'Applied production bytes differ from the measured candidate.'
assert not git('status','--porcelain','--untracked-files=all','--','Tests/SwiftJLSTests/Fixtures')
subprocess.run(['git','diff','--check','--','Sources','Tests'],cwd=ROOT,check=True)
assert '@concurrent public func decode(_ data: Data, options: DecodeOptions = .init()) async throws -> DecodedImage {' in (ROOT/'Sources/SwiftJLS/CodecAPI.swift').read_text()
record=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    base_head=BASE,source_commit=None,status='Reviewed candidate applied; uncommitted; final host validation pending',
    candidate_build_identity=str((CANDIDATE/'build-identity.json').relative_to(ROOT)),
    candidate_build_identity_sha256=sha(CANDIDATE/'build-identity.json'),
    candidate_binary_sha256=build['binary_sha256'],applied_patch=str((CANDIDATE/'combined.patch').relative_to(ROOT)),
    applied_patch_sha256=EXPECTED_PATCH,source_files=actual,fixtures_tree=fixture_tree,
    exact_nonfixture_identity=True,fixture_working_tree_unchanged=True,
    required_concurrent_decode_signature_preserved=True,
    working_tree_changes=git('status','--porcelain','--untracked-files=all','--','Sources','Tests','Package.swift','VERSION'),
    exclusions=['Executor counterfactual was not applied.','Speculative Image.swift changes were not applied.'])
OUT.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='source_files'},indent=2))
