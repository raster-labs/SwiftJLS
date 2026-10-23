from pathlib import Path
import json,hashlib,difflib,subprocess
root=Path(__file__).resolve().parent
plan=json.loads((root/'plan.json').read_text());src=Path(plan['frozen_snapshot'])/'Scripts/StorageEvidence/measure-operation.py';old=src.read_text()
anchor="    # The directly allocated JPEGLSBitstreamReader object in ScalarCodec.decode\n"
block='''    # Candidate004's private reserved-storage initializer constructs exactly
    # one UInt8 pixel array (ImageStorage.swift:65-72). The private symbol's
    # disambiguator changes independently of its semantics. Require the exact
    # allocator/UInt8-array/private-constructor/allocating-constructor prefix;
    # an OwnedImageStorage caller elsewhere in a stack is insufficient.
    reserved_pixel_constructor = (
        r'SwiftJLS\\.OwnedImageStorage\\.\\(in _[0-9A-Fa-f]+\\)\\.init\\('
        r'reservedByteCount: Swift\\.Int, allocationID: FoundationEssentials\\.UUID, '
        r'lease: SwiftJLS\\.StorageWriteLease\\) -> SwiftJLS\\.OwnedImageStorage')
    if (size is not None and size > 32 and len(frames) >= 7
            and frames[:5] == owned_factory_pixel_stack[:5]
            and re.fullmatch(reserved_pixel_constructor, frames[5])
            and frames[6] == 'SwiftJLS.OwnedImageStorage.__allocating_init(reservedByteCount: Swift.Int, allocationID: FoundationEssentials.UUID, lease: SwiftJLS.StorageWriteLease) -> SwiftJLS.OwnedImageStorage'):
        return 'owned_pixel_buffer'
'''
assert old.count(anchor)==1;new=old.replace(anchor,block+anchor)
testanchor="    reader_object_stack = prefix + [\n"
tests='''    reserved_pixel_stack = owned_factory_stack[:5] + [
        'SwiftJLS.OwnedImageStorage.(in _E3A3FF9B1E0185F10C196E0592093825).init(reservedByteCount: Swift.Int, allocationID: FoundationEssentials.UUID, lease: SwiftJLS.StorageWriteLease) -> SwiftJLS.OwnedImageStorage',
        'SwiftJLS.OwnedImageStorage.__allocating_init(reservedByteCount: Swift.Int, allocationID: FoundationEssentials.UUID, lease: SwiftJLS.StorageWriteLease) -> SwiftJLS.OwnedImageStorage',
    ]
    for requested in [33, 1766, 1572896]:
        assert classify(reserved_pixel_stack, requested) == 'owned_pixel_buffer'
    assert classify([f.replace('_E3A3FF9B1E0185F10C196E0592093825', '_ABC123') for f in reserved_pixel_stack], 1766) == 'owned_pixel_buffer'
    for requested in [None, 0, 16, 32]:
        assert classify(reserved_pixel_stack, requested) != 'owned_pixel_buffer'
    for invalid in [
        ['malloc'] + reserved_pixel_stack[1:],
        [reserved_pixel_stack[0], 'malloc'] + reserved_pixel_stack[2:],
        [f.replace('<Swift.UInt8>', '<Swift.Int>') for f in reserved_pixel_stack],
        reserved_pixel_stack[:3] + ['SwiftJLS.Other.allocate'] + reserved_pixel_stack[3:],
        reserved_pixel_stack[:5] + ['SwiftJLS.Other.allocate'] + reserved_pixel_stack[5:],
        reserved_pixel_stack[:6] + ['SwiftJLS.Other.allocate'] + reserved_pixel_stack[6:],
        [f.replace('reservedByteCount:', 'capacity:') for f in reserved_pixel_stack],
        reserved_pixel_stack[:5] + [reserved_pixel_stack[5].replace('lease:', 'unrelated:')] + reserved_pixel_stack[6:],
        reserved_pixel_stack[:6] + [reserved_pixel_stack[6].replace('allocationID:', 'otherID:')],
        reserved_pixel_stack[:6],
    ]:
        assert classify(invalid, 1766) != 'owned_pixel_buffer'
'''
assert new.count(testanchor)==1;new=new.replace(testanchor,tests+testanchor)
target=root/'external-classifier';target.mkdir(exist_ok=False)
(target/'measure-operation-original.py').write_bytes(src.read_bytes());(target/'measure-operation.py').write_text(new)
(target/'classifier.patch').write_text(''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/Scripts/StorageEvidence/measure-operation.py',tofile='b/Scripts/StorageEvidence/measure-operation.py')))
runner=Path(plan['frozen_snapshot'])/'Scripts/StorageEvidence/run-workspace-profiles.py';original=runner.read_text();external=original.replace("'Scripts/StorageEvidence/measure-operation.py'","'/validation/measure-operation.py'")
assert original.count("'Scripts/StorageEvidence/measure-operation.py'")==1
(target/'run-workspace-profiles.py').write_text(external)
result=subprocess.run(['python3',str(target/'measure-operation.py'),'--self-test'],capture_output=True,text=True)
receipt={'command':['python3',str(target/'measure-operation.py'),'--self-test'],'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr,'original_classifier_sha256':hashlib.sha256(src.read_bytes()).hexdigest(),'corrected_classifier_sha256':hashlib.sha256((target/'measure-operation.py').read_bytes()).hexdigest(),'patch_sha256':hashlib.sha256((target/'classifier.patch').read_bytes()).hexdigest(),'external_runner_sha256':hashlib.sha256((target/'run-workspace-profiles.py').read_bytes()).hexdigest(),'scope':'Exact new private reserved UInt8 pixel constructor prefix only; no production change; old fallback categories on deliberately invalid synthetic prefixes are not broadened.'}
(target/'self-test.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt,indent=2));assert result.returncode==0
