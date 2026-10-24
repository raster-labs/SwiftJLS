#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Make explicit standard presets for a deliberately legacy decoder profile.

Only metadata is inserted. Original bytes, independent expected samples and all
hashes are retained. The predicate is formula-based, never outcome-based.
"""
import hashlib
import json
from pathlib import Path
import struct


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(fixtures, output):
    output.mkdir(exist_ok=False)
    manifest = json.loads((fixtures / 'manifest.json').read_text())
    cases = []
    for f in manifest['cases']:
        bits, near = f['meaningfulBits'], f.get('near', 0)
        if bits < 8 or f.get('preset') is not None:
            continue
        maximum = (1 << bits) - 1
        factor = (min(maximum, 4095) + 128) // 256
        raw = [factor + 2 + 3 * near, factor * 4 + 3 + 5 * near, factor * 17 + 4 + 7 * near]
        standard, legacy = [], []
        for value in raw:
            lower = standard[-1] if standard else near + 1
            standard.append(lower if value < lower or value > maximum else value)
            lower = legacy[-1] if legacy else near + 1
            legacy.append(min(max(value, lower), maximum))
        if standard == legacy:
            continue
        name = f['name']
        original = (fixtures / (name + '.jls')).read_bytes()
        if sha(original) != f['encoded_sha256']:
            raise ValueError('Original fixture hash mismatch: ' + name)
        cursor = 2
        while cursor + 4 <= len(original):
            if original[cursor] != 255:
                raise ValueError('Noncanonical fixture marker: ' + name)
            length = int.from_bytes(original[cursor + 2:cursor + 4], 'big')
            if length < 2 or cursor + 2 + length > len(original):
                raise ValueError('Invalid fixture segment: ' + name)
            marker = original[cursor + 1]
            if marker == 218:
                break
            if marker == 248 and original[cursor + 4] == 1:
                raise ValueError('Unadvertised explicit preset: ' + name)
            cursor += 2 + length
        else:
            raise ValueError('Fixture SOS not found: ' + name)
        lse = bytes([255, 248, 0, 13, 1]) + struct.pack('>5H', maximum, *standard, 64)
        adapted = original[:cursor] + lse + original[cursor:]
        expected_path = fixtures / (name + '.decoded.u16le')
        sample_key = 'decoded_sha256'
        if not expected_path.exists():
            expected_path = fixtures / (name + '.u16le')
            sample_key = 'samples_sha256'
        expected = expected_path.read_bytes()
        if sha(expected) != f[sample_key]:
            raise ValueError('Independent sample hash mismatch: ' + name)
        original_file, adapted_file, expected_file = name + '.original.jls', name + '.explicit.jls', name + '.expected.u16le'
        for filename, data in [(original_file, original), (adapted_file, adapted), (expected_file, expected)]:
            (output / filename).write_bytes(data)
        cases.append(dict(name=name, adaptedFile=adapted_file, originalFile=original_file, expectedFile=expected_file,
            originalSha256=sha(original), adaptedSha256=sha(adapted), samplesSha256=sha(expected),
            standardThresholds=standard, legacyThresholds=legacy, maximum=maximum, near=near, reset=64,
            insertedBeforeSOS=cursor, insertedHex=lse.hex(),
            reason='Explicit standard default LSE replaces the standard-oracle reliance on implicit thresholds; jlswift0101 intentionally retains different high-NEAR CLAMP semantics. Entropy/restart bytes and expected samples are unchanged.'))
    record = dict(profile='jlswift0101', adapterSourceSha256=sha(Path(__file__).read_bytes()), cases=cases)
    path = output / 'adaptations.json'
    path.write_text(json.dumps(record, indent=2) + '\n')
    return path


def verify(path):
    record = json.loads(path.read_text())
    for c in record['cases']:
        for file_key, hash_key in [('originalFile', 'originalSha256'), ('adaptedFile', 'adaptedSha256'), ('expectedFile', 'samplesSha256')]:
            if sha((path.parent / c[file_key]).read_bytes()) != c[hash_key]:
                raise ValueError('Adaptation changed: ' + c[file_key])
