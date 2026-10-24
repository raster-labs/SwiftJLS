#!/usr/bin/env python3
"""Prepare a forbidden-for-production executor counterfactual, source only."""
import datetime, difflib, hashlib, json, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PARENT = ROOT / 'work/m4-short-path-diagnostic'
source = json.loads((PARENT / 'source-identity.json').read_text())
parent_build = json.loads((PARENT / 'build-identity.json').read_text())
CODEC = HERE / 'codec'
CONSUMER = HERE / 'consumer'

def digest(data):
    return hashlib.sha256(data).hexdigest()

assert not CODEC.exists() and not CONSUMER.exists()
assert source['patches']['combined.patch'] == '7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a'
for name, expected in source['source_files'].items():
    data = (PARENT / 'codec' / name).read_bytes()
    assert digest(data) == expected, name
    target = CODEC / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
for name, expected in [('Sources/Benchmark/main.swift', source['consumer_sha256']), ('Package.swift', source['consumer_package_sha256'])]:
    data = (PARENT / 'consumer' / name).read_bytes()
    assert digest(data) == expected
    target = CONSUMER / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)

path = 'Sources/SwiftJLS/CodecAPI.swift'
original = (CODEC / path).read_text()
old = '    @concurrent public func decode(_ data: Data, options: DecodeOptions = .init()) async throws -> DecodedImage {'
new = '    public func decode(_ data: Data, options: DecodeOptions = .init()) throws -> DecodedImage {'
assert original.count(old) == 1
candidate = original.replace(old, new)
assert candidate.replace(new, old) == original
body = original.split(old + '\n', 1)[1].split('\n    }', 1)[0]
assert candidate.split(new + '\n', 1)[1].split('\n    }', 1)[0] == body
assert body == '''        try Task.checkCancellation()
        try validateInput(data, options)
        return try ScalarCodec.decode(data, into: nil, options: options, codecOptions: configuration.codecOptions)'''
(CODEC / path).write_text(candidate)
patch = ''.join(difflib.unified_diff(original.splitlines(True), candidate.splitlines(True), fromfile='a/'+path, tofile='b/'+path))
(HERE / 'synchronous-owned-decode.patch').write_text(patch)
base_patch = (PARENT / 'combined.patch').read_bytes()
assert digest(base_patch) == source['patches']['combined.patch']
(HERE / 'base-combined.patch').write_bytes(base_patch)
(HERE / 'diagnostic.patch').write_bytes(base_patch + b'\n' + patch.encode())
(HERE / 'parent-build-identity.json').write_bytes((PARENT / 'build-identity.json').read_bytes())
record = dict(created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    base_source=source['base_source'], parent_patch_sha256=digest(base_patch),
    parent_binary=parent_build['binary'], parent_binary_sha256=parent_build['binary_sha256'],
    parent_build_identity_sha256=digest((PARENT/'build-identity.json').read_bytes()),
    patches={name:digest((HERE/name).read_bytes()) for name in ['base-combined.patch','synchronous-owned-decode.patch','diagnostic.patch']},
    source_files={name:digest((CODEC/name).read_bytes()) for name in source['source_files']},
    fixtures_tree=source['fixtures_tree'], fixture_materialisation='Deferred until exclusive build window',
    consumer_sha256=source['consumer_sha256'], consumer_package_sha256=source['consumer_package_sha256'],
    developer_dir=source['developer_dir'], swift=source['swift'],
    exact_scope='One owned Decoder.decode signature only: remove @concurrent and async. All body bytes and every other source/test file unchanged.',
    owned_decode_body_sha256=digest(body.encode()), exact_inverse_reconstructs_parent_file=True,
    status='Diagnostic only; violates required generic-executor policy; never a permitted production optimisation or automatic waiver',
    promoted=False, timings_run=False)
(HERE/'source-identity.json').write_text(json.dumps(record, indent=2)+'\n')
print(json.dumps({k:v for k,v in record.items() if k != 'source_files'}, indent=2))
