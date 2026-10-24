#!/usr/bin/env python3
"""Correctness-only final-source proof of the one selected larger size flag."""
import datetime
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
BUILD = HERE.parent / 'benchmark-build.json'
SUMMARY = HERE.parent / 'larger-guard-summary.json'
SOURCE = 'e6a6436c692f5af226bffceb70b7ee65c774edf3'
PREDECESSOR = '15aa75164145414f3d5ffb801401c52d40cc5bcc'
CASE = '4096x3073-p12-flat-c3-n0-i2'
spec = importlib.util.spec_from_file_location('retained_helper', HERE / 'rgb-size-helper.py')
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
require, digest = helper.require, helper.digest

def read_json(path):
    return json.loads(path.read_text())

def save():
    (HERE / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')

def guard():
    require(build['source_commit'] == SOURCE and build['predecessor_commit'] == PREDECESSOR,
            'Unexpected source revisions')
    require(build['builds_verified'] and build['successor_build_mode'] == 'reused_frozen_candidate',
            'Missing verified immutable build bridge')
    for relative, expected in build['source_files'].items():
        require(digest((ROOT / relative).read_bytes()) == expected, 'Current source drift: ' + relative)
        committed = subprocess.run(['git', 'show', SOURCE + ':' + relative], cwd=ROOT,
                                   capture_output=True, check=True).stdout
        require(digest(committed) == expected, 'Commit/source bridge mismatch: ' + relative)
    for label, binary in binaries.items():
        require(digest(binary.read_bytes()) == build['binary_sha256'][label], 'Binary drift: ' + label)
    for consumer in [HERE / 'Consumer.swift', ROOT / 'Scripts/Benchmark/Consumer.swift',
                     ROOT / 'work/m4-owned-admission-diagnostic/consumer/Sources/Benchmark/main.swift',
                     ROOT / 'work/m4-benchmark/predecessor/Sources/Benchmark/main.swift']:
        require(digest(consumer.read_bytes()) == build['consumer_sha256'], 'Consumer drift: ' + str(consumer))
    return True

def run(label, action, environment):
    command = [str(binaries[label]), '4096', '3073', '12', 'flat', '0', '1', label, '3', '0', '2']
    env = {k: v for k, v in os.environ.items() if not k.startswith('SWIFTJLS_BENCHMARK_')}
    env.update(environment)
    env['DEVELOPER_DIR'] = build['developer_dir']
    record = dict(producer=label, action=action, command=command, environment=environment,
                  developer_dir=build['developer_dir'], utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    started = time.monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=180)
        record.update(exit_code=result.returncode, wall_seconds=time.monotonic()-started)
        for stream in ['stdout', 'stderr']:
            data = getattr(result, stream)
            path = HERE / (label + '-' + action + '.' + stream)
            path.write_bytes(data)
            record[stream] = dict(path=path.name, bytes=len(data), sha256=digest(data))
        report['commands'].append(record); save()
        result.check_returncode()
        output = json.loads(result.stdout)
        require(output['warmups'] == 0 and output['iterations'] == 1, 'Unexpected diagnostic iteration count')
        require(output['encoded_bytes'] == row['encoded_bytes'][labels[label]], 'Output size differs from campaign')
        return output
    except Exception as exc:
        record['error'] = repr(exc)
        if record not in report['commands']:
            report['commands'].append(record)
        save()
        raise

require(not (HERE / 'summary.json').exists(), 'Never overwrite an executed proof')
build = read_json(BUILD)
summary = read_json(SUMMARY)
row = next(r for r in summary['rows'] if r['case']['id'] == CASE)
require(summary['source'] == SOURCE and row['encoded_byte_delta'] == 44, 'Unexpected measured finding')
binaries = {k: Path(v).resolve() for k, v in build['binaries'].items()}
labels = {'predecessor': 'reference', 'successor': 'candidate'}
report = dict(source_checkpoint=SOURCE, predecessor_checkpoint=PREDECESSOR, case=row['case'],
    scope='Correctness-only export, exact header/entropy comparison, and two full-sample cross-decodes. Incidental timings are retained but are not performance qualification.',
    independent_oracle_run=False, required_samples_per_decode=4096*3073*3,
    scripts={p.name: digest(p.read_bytes()) for p in [Path(__file__), HERE/'rgb-size-helper.py']},
    consumer_sha256=build['consumer_sha256'], build_record_sha256=digest(BUILD.read_bytes()),
    measured_summary_sha256=digest(SUMMARY.read_bytes()), binary_sha256=build['binary_sha256'],
    binaries={k: str(v) for k, v in binaries.items()}, commands=[], producers={}, complete=False)
save()
helper.parser_controls()
report['parser_controls_passed'] = True
report['start_source_binary_guards_passed'] = guard(); save()
streams, parsed, entropies = {}, {}, {}
for label in binaries:
    path = HERE / (label + '.jls')
    run(label, 'export', {'SWIFTJLS_BENCHMARK_EXPORT': str(path)})
    data = path.read_bytes()
    found, entropy = helper.markers(data)
    require(len(data) == row['encoded_bytes'][labels[label]], 'Export size differs from campaign')
    streams[label], parsed[label], entropies[label] = data, found, entropy
    report['producers'][label] = dict(bytes=len(data), sha256=digest(data), markers=found,
        entropy_bytes=len(entropy), entropy_sha256=digest(entropy), full_consumer_sample_check=True)
    save()
spiff = [m for m in parsed['successor'] if m['marker'] == 'FFE8']
expected = helper.spiff_segments(4096, 3073, 12)
exact_headers = ([bytes.fromhex(m['raw_hex']) for m in spiff] == expected
    and [m['offset'] for m in spiff] == [2,36]
    and not any(m['marker'] == 'FFE8' for m in parsed['predecessor'])
    and not any(m['marker'] == 'FFF8' for label in parsed for m in parsed[label]))
normalised = helper.without(streams['successor'], spiff)
report.update(delta_bytes=len(streams['successor'])-len(streams['predecessor']),
    matches_recorded_benchmark_sizes=True, exact_signalling_segments=exact_headers,
    signalling_segment_bytes=[m['bytes'] for m in spiff],
    entropy_identical=entropies['predecessor']==entropies['successor'],
    header_normalised_streams_identical=normalised==streams['predecessor'],
    normalised_sha256=digest(normalised), cross_decodes={})
save()
for label, other in [('predecessor','successor'), ('successor','predecessor')]:
    run(label, 'cross-decode', {'SWIFTJLS_BENCHMARK_DECODE': str(HERE/(other+'.jls'))})
    report['cross_decodes'][label+'_decodes_'+other] = dict(passed=True, samples=4096*3073*3, maximum_error=0)
    save()
report['end_source_binary_guards_passed'] = guard()
report['header_only_difference_verified'] = (exact_headers and report['delta_bytes']==44
    and report['entropy_identical'] and report['header_normalised_streams_identical'])
report['complete'] = True
save()
require(report['header_only_difference_verified'], 'Header-only attribution failed; retain raw evidence for investigation')
print(json.dumps({k: report[k] for k in ['source_checkpoint','delta_bytes','signalling_segment_bytes',
    'entropy_identical','header_normalised_streams_identical','cross_decodes','header_only_difference_verified',
    'independent_oracle_run','complete']}, indent=2))
