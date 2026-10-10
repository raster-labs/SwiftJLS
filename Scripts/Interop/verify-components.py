#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
import argparse, hashlib, json, pathlib, struct, subprocess, tempfile
p = argparse.ArgumentParser()
for name in ['oracle', 'fixtures', 'encoded', 'report']:
    p.add_argument('--' + name, type=pathlib.Path, required=True)
a = p.parse_args()
results = []
with tempfile.TemporaryDirectory() as temporary:
    output = pathlib.Path(temporary) / 'decoded'
    for f in json.loads((a.fixtures / 'components.json').read_text())['cases'] + json.loads((a.fixtures / 'components-hp.json').read_text())['cases']:
        for ext, key in [('jls', 'encoded_sha256'), ('u16le', 'samples_sha256'), ('decoded.u16le', 'decoded_sha256')]:
            assert hashlib.sha256((a.fixtures / (f['name'] + '.' + ext)).read_bytes()).hexdigest() == f[key]
        raw = (a.fixtures / (f['name'] + '.u16le')).read_bytes()
        expected = struct.unpack('<' + 'H' * (len(raw) // 2), raw)
        for restart in ([0, 3] if f['interleave'] == 0 else [0]):
            name = f['name'] + ('' if restart == 0 else '-r3')
            r = subprocess.run([str(a.oracle.resolve()), 'decode', str(a.encoded / (name + '.jls')), str(output)], capture_output=True, check=True)
            assert list(map(int, r.stdout.split())) == [f['width'], f['height'], f['meaningfulBits'], f['near']]
            decoded = output.read_bytes()
            actual = list(decoded) if f['meaningfulBits'] <= 8 else list(struct.unpack('<' + 'H' * (len(decoded) // 2), decoded))
            if f['interleave'] != 0:
                actual = [actual[i * f['components'] + c] for c in range(f['components']) for i in range(f['width'] * f['height'])]
            assert len(actual) == len(expected)
            error = max(abs(x - y) for x, y in zip(actual, expected))
            assert error <= f['near'], (name, error)
            results.append(dict(name=name, maximum_error=error, near=f['near'], passed=True))
a.report.write_text(json.dumps(results, indent=2) + '\n')
print(len(results), 'independent component checks passed')
