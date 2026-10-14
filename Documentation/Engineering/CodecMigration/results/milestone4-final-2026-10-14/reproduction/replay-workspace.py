#!/usr/bin/env python3
"""Replay a downloaded, source-pinned workspace matrix; never query CI status."""
import argparse
import collections
import contextlib
import gzip
import hashlib
import importlib.util
import io
import json
import pathlib
import re
import shutil
import sys


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def expected_matrix():
    cases = []
    for size in [17, 512]:
        for components in [1, 3]:
            for near in [0, 3]:
                for operation in ['encode', 'owned', 'into', 'inspect']:
                    cases.append([f'{size}-{components}-{near}-{operation}',
                                  [operation, str(size), str(size), str(components), str(near)]])
    profiles = [('line', 3, 0), ('line', 3, 3), ('planar', 3, 0), ('planar', 3, 3),
                ('p16', 1, 0), ('p16', 3, 3), ('preset', 1, 3), ('preset', 3, 0),
                ('restart', 3, 3), ('hp1', 3, 0), ('hp2', 3, 0), ('hp3', 3, 0)]
    for profile, components, near in profiles:
        for operation in ['encode', 'owned', 'into', 'inspect']:
            cases.append([f'{profile}-{components}-{near}-{operation}',
                          [operation, '257', '129', str(components), str(near), profile]])
    for name in ['subsampled-zero-n0', 'map-p16-c3-i0-w1-n0', 'extended-p12-65537x2']:
        for operation in ['owned', 'into', 'inspect']:
            cases.append([f'{name}-{operation}',
                          [operation, '--fixture', f'Tests/SwiftJLSTests/Fixtures/{name}.jls']])
    return cases


def main():
    scratch = pathlib.Path(__file__).resolve().parent
    repo = scratch.parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', required=True, help='Full source SHA recorded in the new artifact')
    parser.add_argument('--run', required=True, help='GitHub measurement run URL; no network lookup is performed')
    parser.add_argument('--source', type=pathlib.Path, default=scratch / 'workspace-artifact/per-operation-workspace')
    parser.add_argument('--output', type=pathlib.Path, default=scratch / 'workspace-accounting-evidence')
    args = parser.parse_args()
    require(not sys.flags.optimize, 'Run without -O so classifier negative-control assertions remain active')
    require(re.fullmatch(r'[0-9a-f]{40}', args.revision), 'Expected a full lowercase source SHA')
    require(re.fullmatch(r'https://github\.com/raster-labs/SwiftJLS/actions/runs/[0-9]+', args.run), 'Expected a SwiftJLS measurement run URL')
    source, output = args.source.resolve(), args.output.resolve()
    partial = output.with_name(output.name + '.partial')
    require(not output.exists() and not partial.exists(), 'Output or partial output already exists; choose a fresh --output')
    matrix = read_json(source / 'matrix.json')
    require(matrix['revision'] == args.revision, 'Matrix source revision does not match --revision')
    require(matrix['cases'] == expected_matrix() and len(matrix['cases']) == 89,
            'Expected the complete, unique 89-case matrix and exact invocation arguments')

    # Infer one binary identity from the artifact; never inherit a previous build hash.
    binary_hashes = {read_json(source / name / 'summary.json')['binary_sha256'] for name, _ in matrix['cases']}
    require(len(binary_hashes) == 1, 'Profiles contain different consumer binaries')
    binary_hash = next(iter(binary_hashes))
    require(re.fullmatch(r'[0-9a-f]{64}', binary_hash), 'Invalid binary SHA-256')
    classifier = repo / 'Scripts/StorageEvidence/measure-operation.py'
    classifier_hash = sha(classifier)
    spec = importlib.util.spec_from_file_location('measurement', classifier)
    measurement = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(measurement)
    controls = io.StringIO()
    with contextlib.redirect_stdout(controls):
        measurement.self_test()
    partial.mkdir(parents=True)
    (partial / 'classifier-controls.txt').write_text(controls.getvalue())
    shutil.copy2(classifier, partial / 'measure-operation.py')
    shutil.copy2(source / 'matrix.json', partial / 'matrix.json')
    shutil.copy2(pathlib.Path(__file__), partial / 'replay-workspace.py')
    rows = []
    operations = collections.Counter()
    for name, arguments in matrix['cases']:
        case, target = source / name, partial / name
        target.mkdir()
        recorded = read_json(case / 'operation.json')
        require(recorded['revision'] == args.revision, f'{name}: recorded source revision differs')
        commands = read_json(case / 'commands.json')
        require(commands and all(command['exit_code'] == 0 for command in commands), f'{name}: recorded command failed')
        provenance = read_json(case / 'summary.json')
        require(provenance['commands'] == commands, f'{name}: command provenance differs')
        require(provenance['build'] == 'Swift release with debug symbols, no sanitizers', f'{name}: unexpected build scope')
        profile_hash = sha(case / 'allocations.gz')
        require(provenance['profile_sha256'] == profile_hash, f'{name}: profile hash differs')
        require(provenance['binary_sha256'] == binary_hash, f'{name}: binary identity differs')
        launches = [item['command'] for item in commands
                    if item['command'][:2] == ['heaptrack', '-o']]
        require(len(launches) == 1 and launches[0][4:] == arguments, f'{name}: measured invocation differs')
        observations = [json.loads(line) for line in (case / 'consumer.stdout').read_text().splitlines()
                        if line.startswith('{')]
        require(len(observations) == 1 and observations[0].get('samples_verified') is True,
                f'{name}: missing successful post-operation verification')
        observation = observations[0]
        operation = observation['operation']
        require(operation == arguments[0], f'{name}: observation operation differs')
        if arguments[1] == '--fixture':
            require(observation['fixture'] == pathlib.Path(arguments[2]).name, f'{name}: fixture differs')
        else:
            require([observation[k] for k in ['width', 'height', 'components', 'near']] == list(map(int, arguments[1:5])),
                    f'{name}: observed sample geometry differs')
            require(observation['profile'] == (arguments[5] if len(arguments) == 6 else 'base'),
                    f'{name}: observed coding profile differs')
        with gzip.open(case / 'allocations.gz', 'rt') as stream:
            result = measurement.replay(stream.readlines())
        result.update(revision=args.revision, profile_sha256=profile_hash, classifier_sha256=classifier_hash)
        (target / 'operation.json.gz').write_bytes(gzip.compress((json.dumps(result, indent=2) + '\n').encode(), mtime=0))
        groups = result['groups']
        unknown = groups.get('unattributed_codec', {})
        require(result['codec_heap_attribution_complete'] and unknown.get('phase_allocation_calls', 0) == 0
                and unknown.get('baseline_live_bytes', 0) == 0, f'{name}: unattributed codec storage remains; inspect partial ledger')
        require(sum(result['simultaneous_categories_at_phase_peak_bytes'].values()) == result['phase_total_requested_heap_peak_bytes'],
                f'{name}: simultaneous peak does not reconcile')
        require(sum(group['baseline_live_bytes'] for group in groups.values()) == result['baseline_total_requested_heap_bytes'],
                f'{name}: baseline does not reconcile')
        require(result['phase_total_requested_heap_peak_bytes'] - result['baseline_total_requested_heap_bytes'] == result['phase_total_peak_above_baseline_bytes'],
                f'{name}: peak delta does not reconcile')
        owned_count = groups.get('owned_pixel_buffer', {}).get('phase_allocation_calls', 0)
        require(owned_count == (1 if operation == 'owned' else 0), f'{name}: unexpected owned pixel allocation count')
        if operation == 'inspect':
            require(groups.get('algorithm_state', {}).get('phase_allocation_calls', 0) == 0,
                    f'{name}: inspect allocated algorithm state')
        require(result['pure_algorithm_workspace_complete'] is False and result['stack_peak_bytes'] is None
                and result['allocator_overhead_bytes'] is None, f'{name}: unknown total was relabelled')
        for filename in ['allocations.gz', 'commands.json', 'consumer.stdout', 'summary.json']:
            shutil.copy2(case / filename, target / filename)
        operations[operation] += 1
        rows.append(dict(case=name, observation=observation, codec_heap_attribution_complete=True,
            owned_pixel_allocation_calls=owned_count,
            algorithm_state_peak_above_baseline_bytes=groups.get('algorithm_state', {}).get('peak_above_baseline_bytes', 0),
            total_requested_heap_peak_above_baseline_bytes=result['phase_total_peak_above_baseline_bytes'],
            simultaneous_categories_at_phase_peak_bytes=result['simultaneous_categories_at_phase_peak_bytes']))
    require(operations == {'encode': 20, 'owned': 23, 'into': 23, 'inspect': 23}, 'Operation counts differ')
    require(sha(classifier) == classifier_hash, 'Classifier changed during replay')
    summary = dict(source_checkpoint=args.revision, measurement_run=args.run,
        scope='89 marked operations, Swift 6.4 ordinary-release x86_64 Linux; downloaded measurement artifact replay, not CI status verification',
        binary_sha256=binary_hash, classifier_sha256=classifier_hash, profile_count=len(rows),
        all_consumers_verified=True, all_recorded_commands_succeeded=True,
        all_ledgers_reconcile=True, all_codec_heap_attributed=True,
        operation_counts=dict(operations), owned_decode_profiles=23,
        pure_algorithm_workspace_complete=False, stack_peak_bytes=None,
        allocator_overhead_bytes=None, production_peakWorkspaceBytes=None,
        limitations=[
            'Source inventory covers fixed and row-dependent algorithm storage; this finite matrix is not exhaustive input, option, error-path or ABI coverage.',
            'Mapping fixture uses default options; explicit mappingOutputPrecision sample application is source-accounted, not measured by this matrix.',
            'Category attribution measures requested heap. Compiler spills, runtime frames, actual allocator overhead and a universal pure-algorithm peak remain unknown.',
            'Category maxima occur at different instants and must not be added.',
            'Owned pixel counts concern observed attributed allocations; source review and independent correctness/copy-mutation evidence remain necessary.',
            'Physical-device qualification remains pending. CI verification and merge remain with the owner.'],
        rows=rows)
    (partial / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    files = [dict(path=str(path.relative_to(partial)), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(partial.rglob('*')) if path.is_file() and path.name != 'manifest.json']
    (partial / 'manifest.json').write_text(json.dumps(dict(source_checkpoint=args.revision,
        measurement_run=args.run, binary_sha256=binary_hash, files=files), indent=2) + '\n')
    partial.rename(output)
    print(json.dumps(dict(source_checkpoint=args.revision, binary_sha256=binary_hash,
        profile_count=len(rows), all_codec_heap_attributed=True, owned_decode_profiles=23,
        files=len(files), bytes=sum(item['bytes'] for item in files), output=str(output))))


if __name__ == '__main__':
    main()
