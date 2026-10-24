#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Collect the marked workspace matrix; preserve every command and profile."""
import argparse, hashlib, json, pathlib, subprocess


def verify_operation_report(name, operation, report, expected_revision, profile_path=None):
    if report.get('revision') != expected_revision:
        raise AssertionError(f'{name}: revision mismatch ({report.get("revision")} != {expected_revision})')
    if profile_path is not None:
        expected_sha = hashlib.sha256(profile_path.read_bytes()).hexdigest()
        if report.get('profile_sha256') != expected_sha:
            raise AssertionError(f'{name}: profile_sha256 mismatch')
    if report.get('codec_heap_attribution_complete') is not True:
        raise AssertionError(f'{name}: codec_heap_attribution_complete is not true')
    groups = report.get('groups', {})
    unattributed = groups.get('unattributed_codec', {})
    if unattributed.get('phase_allocation_calls', 0) != 0 or unattributed.get('baseline_live_bytes', 0) != 0:
        raise AssertionError(f'{name}: non-zero unattributed_codec activity: {unattributed}')
    phase_peak = report['phase_total_requested_heap_peak_bytes']
    baseline_total = report['baseline_total_requested_heap_bytes']
    if report['phase_total_peak_above_baseline_bytes'] != phase_peak - baseline_total:
        raise AssertionError(f'{name}: phase_total_peak_above_baseline_bytes identity failed')
    simultaneous = report.get('simultaneous_categories_at_phase_peak_bytes', {})
    if phase_peak > baseline_total and sum(simultaneous.values()) != phase_peak:
        raise AssertionError(f'{name}: simultaneous category sum {sum(simultaneous.values())} != {phase_peak}')
    for group_name, g in groups.items():
        if g['peak_above_baseline_bytes'] != g['peak_live_bytes'] - g['baseline_live_bytes']:
            raise AssertionError(f'{name}: {group_name} peak_above_baseline_bytes mismatch')
    owned_group = groups.get('owned_pixel_buffer', {})
    owned_calls = owned_group.get('phase_allocation_calls', 0)
    owned_peak_delta = owned_group.get('peak_above_baseline_bytes', 0)
    expected_owned_calls = 1 if operation == 'owned' else 0
    if owned_calls != expected_owned_calls:
        raise AssertionError(f'{name}: expected {expected_owned_calls} owned_pixel_buffer calls for {operation}, got {owned_calls}')
    if operation == 'owned' and owned_peak_delta <= 0:
        raise AssertionError(f'{name}: owned operation must record positive owned_pixel_buffer peak_above_baseline_bytes')
    if operation != 'owned' and owned_peak_delta != 0:
        raise AssertionError(f'{name}: {operation} operation must have 0 owned_pixel_buffer peak_above_baseline_bytes, got {owned_peak_delta}')


def self_test():
    valid_owned = dict(
        revision='abc123',
        codec_heap_attribution_complete=True,
        phase_total_requested_heap_peak_bytes=160,
        baseline_total_requested_heap_bytes=100,
        phase_total_peak_above_baseline_bytes=60,
        simultaneous_categories_at_phase_peak_bytes=dict(owned_pixel_buffer=140, algorithm_state=20),
        groups=dict(
            owned_pixel_buffer=dict(baseline_live_bytes=100, peak_live_bytes=140, peak_above_baseline_bytes=40, end_live_bytes=140, phase_allocation_calls=1, phase_allocated_bytes=40),
            algorithm_state=dict(baseline_live_bytes=0, peak_live_bytes=20, peak_above_baseline_bytes=20, end_live_bytes=0, phase_allocation_calls=1, phase_allocated_bytes=20),
        ),
    )
    verify_operation_report('test-owned', 'owned', valid_owned, 'abc123')
    valid_into = json.loads(json.dumps(valid_owned))
    valid_into['groups']['owned_pixel_buffer'] = dict(baseline_live_bytes=100, peak_live_bytes=100, peak_above_baseline_bytes=0, end_live_bytes=100, phase_allocation_calls=0, phase_allocated_bytes=0)
    valid_into['phase_total_requested_heap_peak_bytes'] = 120
    valid_into['phase_total_peak_above_baseline_bytes'] = 20
    valid_into['simultaneous_categories_at_phase_peak_bytes'] = dict(owned_pixel_buffer=100, algorithm_state=20)
    verify_operation_report('test-into', 'into', valid_into, 'abc123')
    for mutator in [
        lambda r: r.update(codec_heap_attribution_complete=False),
        lambda r: r['groups'].update(unattributed_codec=dict(baseline_live_bytes=0, peak_live_bytes=16, peak_above_baseline_bytes=16, end_live_bytes=0, phase_allocation_calls=1, phase_allocated_bytes=16)),
        lambda r: r['groups'].update(unattributed_codec=dict(baseline_live_bytes=16, peak_live_bytes=16, peak_above_baseline_bytes=0, end_live_bytes=16, phase_allocation_calls=0, phase_allocated_bytes=0)),
        lambda r: r.update(phase_total_peak_above_baseline_bytes=999),
        lambda r: r.update(simultaneous_categories_at_phase_peak_bytes=dict(owned_pixel_buffer=100)),
        lambda r: r['groups']['owned_pixel_buffer'].update(phase_allocation_calls=0),
        lambda r: r['groups']['owned_pixel_buffer'].update(phase_allocation_calls=2),
        lambda r: r.update(revision='wrong'),
    ]:
        bad = json.loads(json.dumps(valid_owned))
        mutator(bad)
        try:
            verify_operation_report('bad-owned', 'owned', bad, 'abc123')
        except AssertionError:
            pass
        else:
            raise AssertionError('Invalid workspace operation report was accepted')
    try:
        verify_operation_report('bad-into', 'into', valid_owned, 'abc123')
    except AssertionError:
        pass
    else:
        raise AssertionError('Owned pixel allocation in into mode was accepted')
    print('Workspace profile runner controls passed')


if __name__ == '__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--binary')
    p.add_argument('--output', type=pathlib.Path)
    p.add_argument('--revision')
    p.add_argument('--self-test', action='store_true')
    a=p.parse_args()
    if a.self_test:
        self_test()
        raise SystemExit(0)
    if not all([a.binary, a.output, a.revision]):
        p.error('binary, output, revision required')
    a.output.mkdir(parents=True, exist_ok=True)
    cases=[]
    for size in [17,512]:
        for components in [1,3]:
            for near in [0,3]:
                for operation in ['encode','owned','into','inspect']:
                    cases.append((f'{size}-{components}-{near}-{operation}',[operation,str(size),str(size),str(components),str(near)]))
    for profile,components,near in [('line',3,0),('line',3,3),('planar',3,0),('planar',3,3),('p16',1,0),('p16',3,3),('preset',1,3),('preset',3,0),('restart',3,3),('hp1',3,0),('hp2',3,0),('hp3',3,0)]:
        for operation in ['encode','owned','into','inspect']:
            cases.append((f'{profile}-{components}-{near}-{operation}',[operation,'257','129',str(components),str(near),profile]))
    for name in ['subsampled-zero-n0','map-p16-c3-i0-w1-n0','extended-p12-65537x2']:
        for operation in ['owned','into','inspect']:
            cases.append((f'{name}-{operation}',[operation,'--fixture',f'Tests/SwiftJLSTests/Fixtures/{name}.jls']))
    (a.output/'matrix.json').write_text(json.dumps(dict(revision=a.revision,cases=cases),indent=2)+'\n')
    for name,args in cases:
        output=a.output/name
        profile_path=output/'allocations.gz'
        report_path=output/'operation.json'
        subprocess.run(['python3','Scripts/StorageEvidence/trace-heap.py','--binary',a.binary,'--output',str(output),'--scope','One marked operation; setup retained and verification after the end marker','--',*args],check=True,stdout=subprocess.DEVNULL)
        subprocess.run(['python3','/validation/measure-operation.py','--profile',str(profile_path),'--output',str(report_path),'--revision',a.revision],check=True)
        report=json.loads(report_path.read_text())
        verify_operation_report(name, args[0], report, a.revision, profile_path)
        print(name+' passed',flush=True)
