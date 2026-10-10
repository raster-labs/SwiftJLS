#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Import synthetic preset vectors produced by the isolated T.87 reference job.

The reference executables are conformance-only and never enter this package.
Use reference-windows.py and its hash-pinned download to reproduce the report.
CharLS 2.4.2 is not used for arbitrary MAXVAL presets: its prediction correction
assumes a power-of-two alphabet. Unsupported reference cases remain recorded as
coverage gaps, not accepted vectors.
"""
import argparse, base64, hashlib, json
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument('--candidates', type=Path, required=True)
p.add_argument('--report', type=Path, required=True)
p.add_argument('--output', type=Path, required=True)
a = p.parse_args()
manifest = json.loads((a.output / 'manifest.json').read_text())
report = json.loads(a.report.read_text())
candidates = {c['name']: c for c in json.loads(a.candidates.read_text())['cases']}
records = [c for c in manifest['cases'] if not c.get('preset')]
for result in report['cases']:
    case = candidates[result['name']]
    if result.get('unsupported'):
        continue
    assert result['passed'], result
    encoded = base64.b64decode(result['reference_encoded'], validate=True)
    raw = base64.b64decode(case['samples'], validate=True)
    decoded = base64.b64decode(result['reference_decoded_u16le'], validate=True)
    assert len(raw) == len(decoded) == case['width'] * case['height'] * 2
    sof = encoded.index(b'\xff\xf7')
    bits = encoded[sof + 4]
    record = {k: case[k] for k in ('name', 'width', 'height', 'near', 'preset')}
    # Keep the candidate name stable for traceability; the reference encoder
    # chooses its SOF precision from MAXVAL, which may be lower than the input.
    record.update(meaningfulBits=bits, candidateMeaningfulBits=base64.b64decode(case['encoded'])[base64.b64decode(case['encoded']).index(b'\xff\xf7') + 4],
                  generator=report['oracle'])
    for suffix, data, key in [('jls', encoded, 'encoded_sha256'),
                              ('u16le', raw, 'samples_sha256'),
                              ('decoded.u16le', decoded, 'decoded_sha256')]:
        (a.output / (case['name'] + '.' + suffix)).write_bytes(data)
        record[key] = hashlib.sha256(data).hexdigest()
    records.append(record)
manifest['cases'] = records
manifest['presetOracle'] = {k: report[k] for k in ('oracle', 'archive_sha256', 'source')}
manifest['presetOracle']['unsupportedCases'] = [r for r in report['cases'] if r.get('unsupported')]
(a.output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print(len(records), 'accepted fixtures')
