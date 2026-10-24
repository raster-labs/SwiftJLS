#!/usr/bin/env python3
"""Read-only source reconciliation; writes only the external audit JSON."""
from pathlib import Path
import hashlib, json, runpy, subprocess, datetime
A=Path('/Users/pushparaj/projects/SwiftJLS-audit/m4-20261022')
S=Path('/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch')
D=S/'p12_flat_prepare_encode_diag_001'
R=Path('/Users/pushparaj/projects/SwiftJLS')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def inv(r, sub='Sources/SwiftJLS', suffix='*.swift'):
 return {str(p.relative_to(r)):sha(p) for p in sorted((r/sub).rglob(suffix)) if p.is_file()}
generator=D/'prepare_p12_flat_diag.py'
generator_before=sha(generator)
g=runpy.run_path(str(generator))
receipt_path=D/'prepare-receipt.json'; receipt_sha=sha(receipt_path)
d=json.loads(receipt_path.read_text())
base={'three_change_ref':g['THREE_CHANGE_CODEC_ROOT'], 'admission_001':g['ADMISSION_001_ROOT'], 'factory_002':g['FACTORY_002_SNAP_ROOT']}
source_before=inv(R)
tests_before=inv(R,'Tests')
assert len(source_before)==38
assert source_before==inv(S/'snapshots/frozen-candidate-validation-002/SwiftJLS')==inv(base['factory_002'])
assert tests_before==inv(S/'snapshots/frozen-candidate-validation-002/SwiftJLS','Tests')
for name in ('Package.swift','VERSION'):
 assert sha(R/name)==sha(S/'snapshots/frozen-candidate-validation-002/SwiftJLS'/name)
consumer=(R/'Scripts/Benchmark/Consumer.swift').read_text()
assert sha(R/'Scripts/Benchmark/Consumer.swift')==d['ordinary_consumer_sha256']==g['EXPECTED_ORDINARY_CONSUMER_SHA']
rows=[]
for arm,x in d['arms'].items():
 p=Path(x['package_dir']); actual=inv(p)
 assert actual==x['swiftjls_files'] and len(actual)==x['swiftjls_file_count']
 reference_arm=arm if arm in base else ('three_change_ref' if arm=='three_change_inst' else 'factory_002')
 b=base[reference_arm]; expected=inv(b)
 changed=[n for n in expected if actual.get(n)!=expected[n]]
 expected_changed=[]
 if arm=='factory_002_zero_icc':
  name='Sources/SwiftJLS/JPEGLS/ScalarCodec.swift'; expected_changed=[name]
  assert (p/name).read_text()==g['apply_zero_icc_ablation']((b/name).read_text())
 elif arm.endswith('_inst'):
  name='Sources/SwiftJLS/CodecAPI.swift'; expected_changed=[name]
  assert (p/name).read_text()==g['apply_codec_api_instrumentation']((b/name).read_text())
 assert set(actual)==set(expected) and changed==expected_changed,(arm,changed)
 assert (p/'Package.swift').read_text()==g['PACKAGE_SWIFT_TEXT']
 assert sha(p/'Package.swift')==x['package_swift_sha256']==d['package_swift_sha256']
 expected_consumer=g['apply_consumer_instrumentation'](consumer) if arm.endswith('_inst') else consumer
 assert Path(x['consumer_path']).read_text()==expected_consumer
 assert sha(Path(x['consumer_path']))==x['consumer_sha256']
 for patch in x['patches'].values(): assert sha(Path(patch['path']))==patch['sha256']
 rows.append({'arm':arm,'file_count':len(actual),'changed_files_from_base':changed,'source_manifest':actual,'consumer_sha256':x['consumer_sha256'],'patches':x['patches'],'recorded_binary_sha256_not_rehashed_by_this_source_audit':x['binary_sha256']})
assert len(rows)==6
assert sha(Path(d['build_events_jsonl']))==d['build_events_sha256']
assert sha(Path(d['smoke_receipts_json']))==d['smoke_receipts_sha256']
assert source_before==inv(R) and tests_before==inv(R,'Tests')
assert generator_before==sha(generator) and receipt_sha==sha(receipt_path)
status=subprocess.check_output(['git','status','--short'],cwd=R,text=True)
expected_paths={'Scripts/StorageEvidence/measure-operation.py','Scripts/StorageEvidence/run-workspace-profiles.py','Sources/SwiftJLS/Image.swift','Sources/SwiftJLS/ImageStorage.swift','Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift','Sources/SwiftJLS/JPEGLS/ScalarCodec.swift','Tests/SwiftJLSTests/OwnedAdmissionTests.swift'}
assert {s[3:] for s in status.splitlines()}==expected_paths
assert sha(R/'Scripts/StorageEvidence/measure-operation.py')=='8049e2a475dd2e34f9c5bc476df4d760553affec07e677b905f70a5602f8b452'
assert sha(R/'Scripts/StorageEvidence/run-workspace-profiles.py')=='2e7b0e9ebb84d6ca5692882b6bd4159e831d7ea28a0dfcb6ee563b94ff47b017'
out={'status':'source_identity_accepted','checked_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'generator_sha256':generator_before,'prepare_receipt_sha256':receipt_sha,'ordinary_consumer_sha256':d['ordinary_consumer_sha256'],'instrumented_consumer_sha256':d['instrumented_consumer_sha256'],'package_sha256':d['package_swift_sha256'],'production_file_count':len(source_before),'production_source_inventory':source_before,'test_swift_count':len(tests_before),'test_swift_inventory':tests_before,'repo_status':status,'source_tests_package_version_equal_frozen_validation_002':True,'source_equal_factory_002_snapshot':True,'before_after_source_test_generator_receipt_hashes_stable':True,'arms':rows,'scope':'Source only: binary, compiler, runner, schedule, statistics and collection authorisation are separately owned.'}
(A/'050-source-check.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({k:v for k,v in out.items() if k not in ('production_source_inventory','test_swift_inventory','arms','repo_status')},indent=2))
