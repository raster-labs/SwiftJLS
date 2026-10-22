#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Retain all three ordinary-build probe runs; never retry or discard failures."""
import argparse
import hashlib
import json
import pathlib
import platform
import subprocess
import time
from prepare_adapters import prepare, verify

p = argparse.ArgumentParser()
p.add_argument('--binary', type=pathlib.Path, required=True)
p.add_argument('--fixtures', type=pathlib.Path, required=True)
p.add_argument('--output', type=pathlib.Path, required=True)
p.add_argument('--timeout-seconds', type=int, default=120)
p.add_argument('--explicit-standard-defaults', action='store_true',
               help='Retain and use labelled standard-LSE adapters for high-NEAR default differences')
a = p.parse_args()
if a.timeout_seconds <= 0:
    p.error('--timeout-seconds must be positive')
a.output.mkdir(parents=True, exist_ok=False)
binary = a.binary.resolve()
fixtures = a.fixtures.resolve()
digest = hashlib.sha256(binary.read_bytes()).hexdigest()
adaptations = prepare(fixtures, a.output / 'adapted-inputs') if a.explicit_standard_defaults else None
adapter_cases = json.loads(adaptations.read_text())['cases'] if adaptations else []
results = []
allocation_keys = ['malloc', 'calloc', 'realloc', 'memalign', 'posix_memalign',
                   'aligned_alloc', 'valloc', 'pvalloc', 'reallocarray']


def observed_calls(counts):
    for key in allocation_keys + ['free', 'requested_bytes', 'overflow', 'allocation_calls']:
        if type(counts[key]) is not int or counts[key] < 0:
            raise ValueError('Invalid allocator counter: ' + key)
    calls = sum(counts[key] for key in allocation_keys)
    if counts['allocation_calls'] != calls:
        raise ValueError('Allocator call total does not reconcile')
    return calls


for mode in ['cold-inspect', 'cold-decode', 'matrix']:
    command = [str(binary), '--' + mode, str(fixtures)]
    if adaptations:
        verify(adaptations)
        command.append(str(adaptations.resolve()))
    start = time.monotonic()
    record = dict(mode=mode, command=command, timeout_seconds=a.timeout_seconds)
    with (a.output / (mode + '.jsonl')).open('wb') as out, (a.output / (mode + '.stderr')).open('wb') as err:
        try:
            completed = subprocess.run(command, stdout=out, stderr=err, timeout=a.timeout_seconds)
            record['exit_code'] = completed.returncode
        except subprocess.TimeoutExpired:
            record.update(exit_code=None, timeout=True)
        except OSError as error:
            record.update(exit_code=None, launch_error=str(error))
    record['elapsed_seconds'] = time.monotonic() - start
    try:
        lines = [json.loads(line) for line in (a.output / (mode + '.jsonl')).read_text().splitlines()]
        operations = [r for r in lines if r.get('kind') == 'operation']
        summaries = [r for r in lines if r.get('kind') == 'summary']
        controls = [r for r in lines if r.get('kind') in ['allocator_positive_controls', 'swift_runtime_positive_control']]
        controls_by_kind = {c['kind']: c for c in controls}
        controls_valid = len(controls) == 2 and len(controls_by_kind) == 2 and all(c['passed'] is True for c in controls)
        if controls_valid:
            c = controls_by_kind['allocator_positive_controls']
            s = controls_by_kind['swift_runtime_positive_control']['counts']
            controls_valid = c['observed_mask'] == c['required_mask'] == 511 and observed_calls(s) > 0 and s['overflow'] == 0
        failures = 0
        for r in operations:
            counts = r['counts']
            clean = observed_calls(counts) == 0 and counts['overflow'] == 0
            if r['allocation_observation_passed'] is not clean:
                raise ValueError('Allocation verdict contradicts observed counters')
            failures += not (clean and r['correctness_passed'] is True and r['canaries_and_input_unchanged'] is True)
        case_names = {r['case'] for r in operations}
        pairs = {(r['case'], r['operation']) for r in operations}
        complete = (len(summaries) == 1 and summaries[0]['operations'] == len(operations) and
                    summaries[0]['cases'] == len(case_names) and summaries[0]['failed_operations'] == failures and
                    len(pairs) == len(operations) and len(operations) > 0)
        if mode == 'matrix':
            complete = complete and pairs == {(name, op) for name in case_names for op in ['inspect', 'decode']}
        adapted = [r for r in operations if 'input_adapter' in r]
        expected_adaptations = {(c['name'] + '-explicit-standard-defaults', op)
            for c in adapter_cases for op in ['inspect', 'decode']} if mode == 'matrix' else set()
        if {(r['case'], r['operation']) for r in adapted} != expected_adaptations:
            raise ValueError('Adapted operation coverage does not match the retained manifest')
        for r in adapted:
            c = next(c for c in adapter_cases if r['case'] == c['name'] + '-explicit-standard-defaults')
            for key, manifest_key in [('original_case', 'name'), ('original_sha256', 'originalSha256'),
                    ('adapted_sha256', 'adaptedSha256'), ('unchanged_samples_sha256', 'samplesSha256'),
                    ('standard_thresholds', 'standardThresholds'), ('legacy_thresholds', 'legacyThresholds'), ('reason', 'reason')]:
                if r['input_adapter'][key] != c[manifest_key]:
                    raise ValueError('Adapted operation provenance differs from the manifest: ' + key)
        record.update(operations=len(operations), positive_controls_passed=controls_valid,
                      complete=complete, failed_operations=failures)
        first = [r for r in operations if r['first_qualified_api_call_in_process']]
        record['cold_identity_valid'] = len(first) == 1 and first[0] is operations[0] and (
            mode == 'matrix' or (len(operations) == 1 and first[0]['operation'] == mode.removeprefix('cold-')))
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
        record['parse_error'] = str(error)
    record['passed'] = record['exit_code'] == 0 and record.get('complete', False) and record.get('positive_controls_passed', False) and record.get('cold_identity_valid', False) and record.get('failed_operations') == 0
    results.append(record)
    (a.output / 'results.json').write_text(json.dumps(dict(binary=str(binary), binary_sha256=digest,
        platform=platform.platform(), libc=platform.libc_ver(), adaptation_manifest=str(adaptations) if adaptations else None,
        results=results), indent=2) + '\n')
    print(json.dumps(record), flush=True)
if hashlib.sha256(binary.read_bytes()).hexdigest() != digest:
    raise SystemExit('Probe binary changed during runs')
if adaptations:
    verify(adaptations)
raise SystemExit(0 if all(r['passed'] for r in results) else 1)
