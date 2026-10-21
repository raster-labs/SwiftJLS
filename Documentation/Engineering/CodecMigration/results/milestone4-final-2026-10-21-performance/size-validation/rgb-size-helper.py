#!/usr/bin/env python3
"""Export the 13 RGB size outliers, compare headers/entropy, and cross-decode.

Uses existing benchmark binaries with zero warmups and one required iteration.
Their incidental timing output is retained but never qualifies performance.
Cross-decoding the two Swift implementations is not an independent oracle.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def markers(data):
    # Retained check-m4-header-sizes.py parser, with explicit framing/length
    # checks. JPEG-LS FF bytes followed by values below 80 remain entropy.
    require(data.startswith(b'\xff\xd8') and data.endswith(b'\xff\xd9'), 'Missing SOI/EOI')
    i, found, entropy = 0, [], bytearray()
    while i < len(data):
        if i + 1 < len(data) and data[i] == 255 and data[i + 1] >= 128:
            code = data[i + 1]
            if code in [216, 217] or 208 <= code <= 215:
                n = 2
            else:
                require(i + 4 <= len(data), 'Truncated marker length')
                length = int.from_bytes(data[i + 2:i + 4], 'big')
                require(length >= 2, 'Invalid marker length')
                n = 2 + length
            require(i + n <= len(data), 'Truncated marker payload')
            found.append(dict(marker=f'FF{code:02X}', offset=i, bytes=n,
                              raw_hex=data[i:i + n].hex(), payload_hex=data[i + 4:i + n].hex() if n > 2 else ''))
            i += n
        else:
            entropy.append(data[i])
            i += 1
    return found, bytes(entropy)


def parser_controls():
    valid = bytes.fromhex('ffd8fff700040102ffda000212ff7f00ffd9')
    parsed, entropy = markers(valid)
    require([m['marker'] for m in parsed] == ['FFD8', 'FFF7', 'FFDA', 'FFD9'], 'Marker control failed')
    require(entropy == bytes.fromhex('12ff7f00'), 'Stuffed entropy was treated as a marker')
    for bad in [valid[2:], valid[:-2], bytes.fromhex('ffd8ffe80001ffd9'), bytes.fromhex('ffd8ffe8ffffffd9')]:
        try:
            markers(bad)
        except ValueError:
            pass
        else:
            raise ValueError('Malformed marker control was accepted')


def without(data, segments):
    cursor, result = 0, bytearray()
    for segment in sorted(segments, key=lambda item: item['offset']):
        start, end = segment['offset'], segment['offset'] + segment['bytes']
        require(cursor <= start <= end <= len(data), 'Invalid removal range')
        result.extend(data[cursor:start])
        cursor = end
    result.extend(data[cursor:])
    return bytes(result)


def spiff_segments(width, height, bits):
    long = lambda value: value.to_bytes(4, 'big')
    header = (bytes.fromhex('ffe8002053504946460002000003') + long(height) + long(width)
              + bytes([10, bits, 6, 0]) + long(1) + long(1))
    return [header, bytes.fromhex('ffe8000800000001ffd8')]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--predecessor', type=Path, required=True)
    parser.add_argument('--successor', type=Path, required=True)
    parser.add_argument('--revision', required=True, help='Full measured successor source SHA supplied with the binary provenance')
    parser.add_argument('--predecessor-revision', default='15aa75164145414f3d5ffb801401c52d40cc5bcc')
    parser.add_argument('--output', type=Path, required=True, help='Fresh evidence directory')
    parser.add_argument('--disposition', type=Path, default=Path(__file__).resolve().parent / 'powered/performance-disposition.json')
    args = parser.parse_args()
    for value in [args.revision, args.predecessor_revision]:
        require(re.fullmatch(r'[0-9a-f]{40}', value), 'Expected full lowercase source SHAs')
    parser_controls()
    report_source = json.loads(args.disposition.read_text())
    keys = ['width', 'height', 'bits', 'pattern', 'components', 'near', 'interleave']
    cases = [row for row in report_source['measurements']['colour']['cases'] if row['encoded_size']['ratio'] > 1.01]
    expected = {(512, 512, bits, 'flat', 3, near, mode) for bits in [12, 16] for near in [0, 3] for mode in [0, 1, 2]}
    expected.add((4096, 3073, 12, 'flat', 3, 0, 2))
    require(len(cases) == 13 and {tuple(row[k] for k in keys) for row in cases} == expected, 'Expected exactly the reviewed 13 RGB outliers')
    binaries = {label: getattr(args, label).resolve() for label in ['predecessor', 'successor']}
    hashes = {label: digest(path.read_bytes()) for label, path in binaries.items()}
    output = args.output.resolve()
    require(not output.exists(), 'Choose a fresh output directory; evidence is never overwritten')
    output.mkdir(parents=True)
    report = dict(source_checkpoint=args.revision, predecessor_checkpoint=args.predecessor_revision,
        reference_size_source_checkpoint=report_source['source_checkpoint'], binary_sha256=hashes,
        script_sha256=digest(Path(__file__).read_bytes()), parser_controls_passed=True,
        scope='Untimed export/marker/entropy diagnostic plus full consumer sample checks and bidirectional Swift cross-decodes. Incidental benchmark timings are not qualification.',
        provenance_note='Source revisions are supplied by the caller; retain the build provenance connecting them to these binary hashes.',
        independent_oracle_run=False, cases=[], commands=[], complete=False)

    def save():
        (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')

    def run(label, row, folder, action, extra):
        command = [str(binaries[label]), str(row['width']), str(row['height']), str(row['bits']),
                   row['pattern'], '0', '1', label, '3', str(row['near']), str(row['interleave'])]
        environment = {key: value for key, value in os.environ.items() if not key.startswith('SWIFTJLS_BENCHMARK_')}
        environment.update(extra)
        record = dict(case=folder.name, action=action, producer=label, command=command, environment=extra)
        try:
            result = subprocess.run(command, env=environment, capture_output=True, timeout=180)
        except subprocess.TimeoutExpired:
            record.update(exit_code=None, error='Command exceeded 180 seconds')
            report['commands'].append(record); save()
            raise
        prefix = folder / (label + '-' + action)
        prefix.with_suffix('.stdout').write_bytes(result.stdout)
        prefix.with_suffix('.stderr').write_bytes(result.stderr)
        record['exit_code'] = result.returncode
        report['commands'].append(record); save()
        result.check_returncode()
        return result

    for row in cases:
        name = f"{row['width']}x{row['height']}-p{row['bits']}-n{row['near']}-i{row['interleave']}"
        folder = output / name; folder.mkdir()
        entry = {key: row[key] for key in keys}
        entry.update(producers={}, cross_decodes={})
        report['cases'].append(entry)
        streams, parsed, entropies = {}, {}, {}
        for label in binaries:
            path = folder / (label + '.jls')
            run(label, row, folder, 'export', {'SWIFTJLS_BENCHMARK_EXPORT': str(path)})
            data = path.read_bytes(); found, entropy = markers(data)
            streams[label], parsed[label], entropies[label] = data, found, entropy
            entry['producers'][label] = dict(bytes=len(data), sha256=digest(data), markers=found,
                entropy_bytes=len(entropy), entropy_sha256=digest(entropy), full_consumer_sample_check=True)
        spi = [m for m in parsed['successor'] if m['marker'] == 'FFE8']
        lse = [m for m in parsed['predecessor'] if m['marker'] == 'FFF8']
        expected_spi = spiff_segments(row['width'], row['height'], row['bits'])
        expected_lse = bytes.fromhex('fff8000d01') + ((1 << row['bits']) - 1).to_bytes(2, 'big') + bytes.fromhex('001b005201290040')
        exact_headers = ([bytes.fromhex(m['raw_hex']) for m in spi] == expected_spi
            and [m['offset'] for m in spi] == [2, 36]
            and not any(m['marker'] == 'FFE8' for m in parsed['predecessor'])
            and not any(m['marker'] == 'FFF8' for m in parsed['successor'])
            and [bytes.fromhex(m['raw_hex']) for m in lse] == ([expected_lse] if row['near'] else []))
        delta = len(streams['successor']) - len(streams['predecessor'])
        expected_delta = 29 if row['near'] else 44
        normalized_predecessor = without(streams['predecessor'], lse)
        normalized_successor = without(streams['successor'], spi)
        entry.update(delta_bytes=delta, expected_delta_bytes=expected_delta,
            matches_recorded_benchmark_sizes=all(len(streams[label]) == row['encoded_size']['bytes'][label] for label in binaries),
            exact_signalling_segments=exact_headers,
            entropy_identical=entropies['predecessor'] == entropies['successor'],
            normalized_streams_identical=normalized_predecessor == normalized_successor,
            normalized_sha256={label: digest(data) for label, data in [('predecessor', normalized_predecessor), ('successor', normalized_successor)]})
        for label, other in [('predecessor', 'successor'), ('successor', 'predecessor')]:
            run(label, row, folder, 'cross-decode', {'SWIFTJLS_BENCHMARK_DECODE': str(folder / (other + '.jls'))})
            entry['cross_decodes'][label + '_decodes_' + other] = True
        entry['header_only_difference_verified'] = (exact_headers and delta == expected_delta
            and entry['matches_recorded_benchmark_sizes'] and entry['entropy_identical'] and entry['normalized_streams_identical'])
        save()
    require(all(digest(path.read_bytes()) == hashes[label] for label, path in binaries.items()), 'A binary changed during the diagnostic')
    report.update(complete=True, profile_count=len(cases), successful_cross_decodes=sum(len(row['cross_decodes']) for row in report['cases']),
                  all_header_only_differences_verified=all(row['header_only_difference_verified'] for row in report['cases']))
    save()
    require(report['all_header_only_differences_verified'], 'Some stream differences require investigation; see summary.json')
    print(json.dumps({key: report[key] for key in ['source_checkpoint', 'profile_count', 'successful_cross_decodes', 'all_header_only_differences_verified', 'independent_oracle_run']}))


if __name__ == '__main__':
    main()
