#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Synthetic independent component vectors; canonical sample files are planar UInt16 LE."""
import argparse, hashlib, json, pathlib, struct, subprocess, tempfile
p = argparse.ArgumentParser()
p.add_argument('--oracle', type=pathlib.Path, required=True)
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('--interleave', type=int, choices=[0, 1, 2], default=0)
a = p.parse_args()
oracle, directory = str(a.oracle.resolve()), a.output.resolve()
path = directory / 'components.json'
manifest = json.loads(path.read_text()) if path.exists() else dict(
    licence='Apache-2.0 original synthetic samples', oracle='CharLS 2.4.2',
    oracle_revision='36dd3307e070d8fbc765c3ba890b7e681046fa39', cases=[])
records = [r for r in manifest['cases'] if r['interleave'] != a.interleave]
manifest['oracleLimitations'] = ['CharLS 2.4.2 does not decode interleaved two-component streams.']
with tempfile.TemporaryDirectory() as temporary:
    temp = pathlib.Path(temporary)
    for bits in [2, 8, 12, 16]:
        maximum = (1 << bits) - 1
        for count in ([2, 3, 4] if a.interleave == 0 else [3, 4]):
            for near in sorted(set([0, min(3, maximum // 2), min(255, maximum // 2)])):
                for width, height, pattern in [(17, 13, 'noise'), (1, 19, 'edge'), (33, 9, 'flat')]:
                    rgb = count == 3 and pattern != 'flat'
                    name = f'c{count}-i{a.interleave}-p{bits}-n{near}-{width}x{height}-{pattern}'
                    plane = width * height
                    samples = [((component * 113 + (i * 1733) ^ (i >> 2)) & maximum) if pattern == 'noise' else
                               ((component + i % 2) * maximum // max(1, count)) if pattern == 'edge' else
                               (component + 1) * maximum // (count + 1)
                               for component in range(count) for i in range(plane)]
                    samples = [min(maximum, value) for value in samples]
                    native = samples if a.interleave == 0 else [samples[c * plane + i] for i in range(plane) for c in range(count)]
                    raw = bytes(native) if bits <= 8 else struct.pack('<' + 'H' * len(native), *native)
                    (temp / 'input').write_bytes(raw)
                    subprocess.run([oracle, 'encode-components', str(width), str(height), str(bits), str(near),
                                    str(count), str(a.interleave), str(int(rgb)), str(temp / 'input'), str(temp / 'output')], check=True)
                    subprocess.run([oracle, 'decode', str(temp / 'output'), str(temp / 'decoded')], check=True, stdout=subprocess.DEVNULL)
                    decoded = (temp / 'decoded').read_bytes()
                    actual = list(decoded) if bits <= 8 else list(struct.unpack('<' + 'H' * (len(decoded) // 2), decoded))
                    if a.interleave != 0:
                        actual = [actual[i * count + c] for c in range(count) for i in range(plane)]
                    assert len(actual) == len(samples) and max(abs(x - y) for x, y in zip(actual, samples)) <= near
                    record = dict(name=name, width=width, height=height, meaningfulBits=bits, near=near,
                                  components=count, interleave=a.interleave, rgb=rgb, pattern=pattern)
                    for ext, data, key in [('jls', (temp / 'output').read_bytes(), 'encoded_sha256'),
                                           ('u16le', struct.pack('<' + 'H' * len(samples), *samples), 'samples_sha256'),
                                           ('decoded.u16le', struct.pack('<' + 'H' * len(actual), *actual), 'decoded_sha256')]:
                        (directory / (name + '.' + ext)).write_bytes(data)
                        record[key] = hashlib.sha256(data).hexdigest()
                    records.append(record)
manifest['cases'] = records
path.write_text(json.dumps(manifest, indent=2) + '\n')
print(len(records), 'component fixtures')
