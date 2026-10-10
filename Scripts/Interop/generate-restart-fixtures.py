#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble independent CharLS row groups; verify the complete restart stream."""
from pathlib import Path
import argparse, json, struct, subprocess, tempfile, hashlib
p = argparse.ArgumentParser()
p.add_argument('--oracle', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
d, oracle = a.output.resolve(), str(a.oracle.resolve())
manifest = json.loads((d / 'manifest.json').read_text())
records = [r for r in manifest['cases'] if not r.get('restartInterval', 0)]

def scan(data):
    pos = 2
    while pos < len(data):
        marker = data[pos + 1]
        length = int.from_bytes(data[pos + 2:pos + 4], 'big')
        if marker == 0xda:
            return pos, pos + 2 + length
        pos += 2 + length
    raise ValueError('No scan')

with tempfile.TemporaryDirectory() as temporary:
    temp = Path(temporary)
    for bits in (2, 7, 8, 12, 16):
        for w, h, pattern in [(1, 19, 'noise'), (17, 13, 'noise'), (33, 9, 'zero'), (33, 9, 'max')]:
            base = f'p{bits}-{w}x{h}-{pattern}'
            source = (d / (base + '.u16le')).read_bytes()
            native = source[::2] if bits <= 8 else source
            original = (d / (base + '.jls')).read_bytes()
            sos, start = scan(original)
            for near in sorted(set([0, min(3, ((1 << bits) - 1) // 2), min(255, ((1 << bits) - 1) // 2)])):
                (temp / 'input').write_bytes(native)
                subprocess.run([oracle, 'encode', str(w), str(h), str(bits), str(near), str(temp / 'input'), str(temp / 'full')], check=True)
                original = (temp / 'full').read_bytes()
                sos, start = scan(original)
                for interval in (1, 3, 13, 65535):
                    name = f'r{interval}-{base}' if near == 0 else f'r{interval}-n{near}-{base}'
                    output = bytearray(original[:sos] + b'\xff\xdd\x00\x04' + interval.to_bytes(2, 'big') + original[sos:start])
                    output[-3] = near
                    for n, y in enumerate(range(0, h, interval)):
                        rows, stride = min(interval, h - y), w * (1 if bits <= 8 else 2)
                        (temp / 'input').write_bytes(native[y * stride:(y + rows) * stride])
                        subprocess.run([oracle, 'encode', str(w), str(rows), str(bits), str(near), str(temp / 'input'), str(temp / 'chunk')], check=True)
                        chunk = (temp / 'chunk').read_bytes()
                        _, offset = scan(chunk)
                        output.extend(chunk[offset:-2])
                        if y + rows < h:
                            output.extend(bytes([255, 0xd0 + n % 8]))
                    output.extend(b'\xff\xd9')
                    (temp / 'assembled').write_bytes(output)
                    subprocess.run([oracle, 'decode', str(temp / 'assembled'), str(temp / 'decoded')], check=True, stdout=subprocess.DEVNULL)
                    decoded = (temp / 'decoded').read_bytes()
                    expected = b''.join(bytes([v, 0]) for v in decoded) if bits <= 8 else decoded
                    original_samples = struct.unpack('<' + 'H' * (len(source) // 2), source)
                    actual = struct.unpack('<' + 'H' * (len(expected) // 2), expected)
                    assert max(abs(x - y) for x, y in zip(original_samples, actual)) <= near, name
                    record = dict(name=name, width=w, height=h, meaningfulBits=bits, restartInterval=interval,
                                  near=near, generator='CharLS row groups; independently decoded after marker assembly')
                    for ext, content, key in [('jls', output, 'encoded_sha256'), ('u16le', source, 'samples_sha256'), ('decoded.u16le', expected, 'decoded_sha256')]:
                        (d / (name + '.' + ext)).write_bytes(content)
                        record[key] = hashlib.sha256(content).hexdigest()
                    records.append(record)
manifest['cases'] = records
(d / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(len(records), 'fixtures')
