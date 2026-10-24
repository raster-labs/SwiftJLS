#!/usr/bin/env python3
"""Apply the reviewed owned-admission delta; preserve prior validation verbatim."""
import datetime, hashlib, json, pathlib, shutil, subprocess
HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CANDIDATE = ROOT/'work/m4-owned-admission-diagnostic'
BASE = 'bee49a2ad47eae4ea149bdced2043b7a45df3dae'
DELTA = '349466c2329a5dd96f434308b034268a9d7dcbb39f8a1e2bcb7ea8b460f84f8b'
FULL = '907bcd3c166dae4fbd4aacdb3bd427b6fc0c9eb9c7814168fb8fd8cb157b7046'
OUT = HERE/'precommit-source-bridge.json'
HISTORY = HERE/'diagnostics/three-change-host-validation'
def git(*args): return subprocess.check_output(['git',*args],cwd=ROOT,text=True).strip()
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def nonfixtures(folder):
    paths = [folder/'Package.swift',folder/'VERSION']
    paths += [p for name in ['Sources','Tests'] for p in (folder/name).rglob('*') if p.is_file()
              and 'Tests/SwiftJLSTests/Fixtures/' not in str(p.relative_to(folder))]
    assert all(not p.is_symlink() for p in paths)
    return {str(p.relative_to(folder)):sha(p) for p in sorted(paths)}
assert not HISTORY.exists(), 'Refusing to replace historical validation.'
previous=json.loads(OUT.read_text())
assert git('rev-parse','HEAD') == BASE
assert previous['applied_patch_sha256']=='7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a'
assert nonfixtures(ROOT)==previous['source_files'], 'Current production differs from validated three-change source.'
results=json.loads((HERE/'tests/results.json').read_text())
assert len(results)==4 and {r['label'] for r in results}=={'debug','release','asan','tsan'}
assert all(r['exit_code']==0 and r['declarations']==117 and r['failures']==r['skipped']==0 for r in results)
source=json.loads((CANDIDATE/'source-identity.json').read_text())
build=json.loads((CANDIDATE/'build-identity.json').read_text())
assert build['source']==source and build['source_unchanged'] and build['consumer_unchanged']
assert build['command']['exit_code']==0 and build['release']['test_count']==build['asan']['test_count']==15
assert build['preflight']['all_six_passed']
assert sha(CANDIDATE/'candidate.patch')==DELTA and sha(CANDIDATE/'combined.patch')==source['patches']['combined.patch']==FULL
assert nonfixtures(CANDIDATE/'codec')==source['source_files']
fixtures='Tests/SwiftJLSTests/Fixtures'
assert git('rev-parse',BASE+':'+fixtures)==source['fixtures_tree']
assert not git('status','--porcelain','--untracked-files=all','--',fixtures)
subprocess.run(['git','apply','--check',str(CANDIDATE/'candidate.patch')],cwd=ROOT,check=True)
# Preserve the prior successful records byte-for-byte; scratch build products
# stay in place and may be reused incrementally by the fresh host driver.
HISTORY.mkdir(parents=True)
old_paths=[HERE/'precommit-source-bridge.json',HERE/'promote-reviewed-candidate.py',HERE/'run-tests.py',HERE/'qualification-source.py']
for path in old_paths: shutil.copyfile(path,HISTORY/path.name)
old_hashes={str(p.relative_to(HERE)):sha(p) for p in (HERE/'tests').rglob('*') if p.is_file()}
(HERE/'tests').rename(HISTORY/'tests')
assert all(sha(HISTORY/name)==digest for name,digest in old_hashes.items())
(HISTORY/'preservation.json').write_text(json.dumps(dict(status='Historical three-change host validation; not relabelled as selected fourth source',test_files=old_hashes,precommit_bridge_sha256=sha(HISTORY/'precommit-source-bridge.json')),indent=2)+'\n')
subprocess.run(['git','apply',str(CANDIDATE/'candidate.patch')],cwd=ROOT,check=True)
actual=nonfixtures(ROOT)
assert actual==source['source_files'], 'Selected production differs from measured candidate.'
assert not git('status','--porcelain','--untracked-files=all','--',fixtures)
subprocess.run(['git','diff','--check','--','Sources','Tests'],cwd=ROOT,check=True)
assert '@concurrent public func decode(_ data: Data, options: DecodeOptions = .init()) async throws -> DecodedImage {' in (ROOT/'Sources/SwiftJLS/CodecAPI.swift').read_text()
record=dict(recorded_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_head=BASE,source_commit=None,
    status='Selected fourth candidate applied; uncommitted; fresh final host validation pending',
    candidate_build_identity=str((CANDIDATE/'build-identity.json').relative_to(ROOT)),candidate_build_identity_sha256=sha(CANDIDATE/'build-identity.json'),
    candidate_binary_sha256=build['binary_sha256'],applied_patch=str((CANDIDATE/'candidate.patch').relative_to(ROOT)),applied_patch_sha256=DELTA,
    combined_patch_sha256=FULL,previous_three_change_validation=str(HISTORY.relative_to(ROOT)),source_files=actual,
    fixtures_tree=source['fixtures_tree'],exact_nonfixture_identity=True,fixture_working_tree_unchanged=True,
    required_concurrent_decode_signature_preserved=True,
    working_tree_changes=git('status','--porcelain','--untracked-files=all','--','Sources','Tests','Package.swift','VERSION'),
    performance_status='Four short decode uncertainties and the direct16-noise outlier remain open; promotion does not waive them.')
OUT.write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='source_files'},indent=2))
