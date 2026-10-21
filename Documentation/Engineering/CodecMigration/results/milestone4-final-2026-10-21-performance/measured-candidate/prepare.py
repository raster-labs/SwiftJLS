#!/usr/bin/env python3
"""Prepare only the narrow Image.swift delta and regression tests for review."""
import datetime, difflib, hashlib, json, pathlib

HERE=pathlib.Path(__file__).resolve().parent
ROOT=HERE.parents[1]
PARENT=ROOT/'work/m4-short-path-diagnostic'
source=json.loads((PARENT/'source-identity.json').read_text())
path='Sources/SwiftJLS/Image.swift'
original=(PARENT/'codec'/path).read_text()
assert hashlib.sha256(original.encode()).hexdigest()==source['source_files'][path]
assert (ROOT/path).read_text()==original
old='        guard requiredKeys.isSubset(of: Set(entries.keys)) else {'
new='        guard requiredKeys.allSatisfy({ entries[$0] != nil }) else {'
assert original.count(old)==1
candidate=original.replace(old,new)
anchor='''    deinit {
        if !lifecycle.withLock({ $0.finished }) {'''
replacement='''    // Only `allocate` may use this initializer, after descriptor and combined
    // memory admission and construction of an exact-capacity owned allocation.
    // Its immutable byteCount equals requiredByteCount, so the public provider
    // initializer's repeated descriptor/capacity guards cannot newly fail.
    // Keep the same reservation and the original owned-allocation cancellation.
    private init(admittedOwnedDescriptor descriptor: ImageDescriptor,
                 storage: OwnedImageStorage, limits: ResourceLimits) throws {
        self.descriptor = descriptor; self.storage = storage; self.limits = limits
        self.lease = try storage.reserveWrite()
    }

    deinit {
        if !lifecycle.withLock({ $0.finished }) {'''
assert candidate.count(anchor)==1
candidate=candidate.replace(anchor,replacement)
old_return='        return try Self(descriptor: descriptor, storage: storage, limits: limits)'
assert candidate.count(old_return)==1
candidate=candidate.replace(old_return,'        return try Self(admittedOwnedDescriptor: descriptor, storage: storage, limits: limits)')
target=HERE/'codec'/path
target.parent.mkdir(parents=True,exist_ok=True)
target.write_text(candidate)
test_path='Tests/SwiftJLSTests/OwnedAdmissionTests.swift'
test=(HERE/'codec'/test_path).read_text()
patch=''.join(difflib.unified_diff(original.splitlines(True),candidate.splitlines(True),fromfile='a/'+path,tofile='b/'+path))
patch+=''.join(difflib.unified_diff([],test.splitlines(True),fromfile='/dev/null',tofile='b/'+test_path))
(HERE/'candidate.patch').write_text(patch)
base=(PARENT/'combined.patch').read_bytes()
(HERE/'base-combined.patch').write_bytes(base)
(HERE/'combined.patch').write_bytes(base+b'\n'+patch.encode())
sha=lambda data:hashlib.sha256(data).hexdigest()
expected=dict(source['source_files']);expected[path]=sha(candidate.encode());expected[test_path]=sha(test.encode())
record=dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),base_source=source['base_source'],
    parent_combined_patch_sha256=source['patches']['combined.patch'],
    patches={name:sha((HERE/name).read_bytes()) for name in ['base-combined.patch','candidate.patch','combined.patch']},
    source_files=expected,fixtures_tree=source['fixtures_tree'],consumer_sha256=source['consumer_sha256'],
    consumer_package_sha256=source['consumer_package_sha256'],developer_dir=source['developer_dir'],swift=source['swift'],
    status='Isolated source/test preparation only; no build, test or timing; no production change',
    public_provider_initializer_unchanged=True,owned_allocation_precheck_order_unchanged=True,
    owned_storage_constructor_and_reserveWrite_unchanged=True,required_concurrent_decode_unchanged=True,
    workspace_admission_and_reports_unchanged=True)
(HERE/'source-identity.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k!='source_files'},indent=2))
