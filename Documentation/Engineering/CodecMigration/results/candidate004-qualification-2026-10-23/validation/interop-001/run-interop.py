#!/usr/bin/env python3
"""Execute the prepared independent 990-case gate only after timing release.

Never overwrites an output directory or regenerates fixtures. All subprocess
logs, failures and fresh successor outputs remain in the selected run directory.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--timing-complete', action='store_true', required=True,
                        help='Operator confirms the explicit root timing release was received.')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to(ROOT) or output == ROOT:
        raise ValueError('Output must be a fresh child directory of this recipe.')
    output.mkdir(exist_ok=False)
    plan_path = ROOT / 'plan.json'
    plan = json.loads(plan_path.read_text())
    source = Path(plan['source_root'])
    fixtures = source / 'Tests/SwiftJLSTests/Fixtures'
    consumer = ROOT / 'Consumer'
    env = os.environ.copy()
    env['DEVELOPER_DIR'] = plan['developer_dir']
    env.pop('SDKROOT', None)
    state = {'started_utc': now(), 'status': 'running', 'plan_sha256': sha(plan_path),
             'runner_sha256': sha(__file__), 'source_receipt_sha256': plan['source_receipt_sha256'],
             'developer_dir': env['DEVELOPER_DIR'], 'commands': [], 'reports': {}}

    def save():
        (output / 'summary.json').write_text(json.dumps(state, indent=2) + '\n')

    def check_map(root, mapping):
        for relative, expected in mapping.items():
            actual = sha(root / relative)
            if actual != expected:
                raise RuntimeError(f'Identity mismatch: {root / relative}: {actual} != {expected}')

    def guard():
        if sha(plan_path) != state['plan_sha256'] or sha(__file__) != state['runner_sha256']:
            raise RuntimeError('Recipe changed during execution.')
        if sha(plan['source_receipt']) != plan['source_receipt_sha256']:
            raise RuntimeError('Frozen candidate receipt changed.')
        if sha(plan['previous_fixture_proof']) != plan['previous_fixture_proof_sha256']:
            raise RuntimeError('Historical fixture proof changed.')
        for root in [source, Path(plan['live_repo'])]:
            for category, directory in [('production_sha256', 'Sources/SwiftJLS'),
                                        ('tests_sha256', 'Tests/SwiftJLSTests')]:
                actual_paths = {str(p.relative_to(root)) for p in (root / directory).rglob('*.swift')}
                if actual_paths != set(plan[category]):
                    raise RuntimeError(f'Swift source inventory changed in {root / directory}')
                check_map(root, plan[category])
            check_map(root, plan['package_version_sha256'])
        fixture_paths = {str(p.relative_to(source)) for p in fixtures.rglob('*') if p.is_file()}
        if fixture_paths != set(plan['fixtures_sha256']):
            raise RuntimeError('Frozen fixture inventory changed.')
        check_map(source, plan['fixtures_sha256'])
        check_map(ROOT / 'scripts', plan['scripts_sha256'])
        check_map(consumer, plan['consumer_sha256'])
        for oracle in plan['oracles'].values():
            if sha(oracle['path']) != oracle['sha256']:
                raise RuntimeError('Independent oracle binary identity changed.')
        return {'checked_utc': now(), 'library_files': len(plan['production_sha256']),
                'test_swift_files': len(plan['tests_sha256']),
                'fixture_files': len(plan['fixtures_sha256']), 'passed': True}

    def run(name, argv):
        entry = {'name': name, 'command': [str(x) for x in argv], 'cwd': str(ROOT),
                 'started_utc': now(), 'stdout': name + '.stdout', 'stderr': name + '.stderr'}
        state['commands'].append(entry)
        save()
        with (output / entry['stdout']).open('wb') as stdout, (output / entry['stderr']).open('wb') as stderr:
            completed = subprocess.run(entry['command'], cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
        entry.update(completed_utc=now(), exit_code=completed.returncode,
                     stdout_sha256=sha(output / entry['stdout']), stderr_sha256=sha(output / entry['stderr']))
        save()
        if completed.returncode:
            raise RuntimeError(f'{name} exited {completed.returncode}; retained logs in {output}')
        return (output / entry['stdout']).read_text()

    save()
    failure = None
    try:
        state['preflight'] = guard()
        run('toolchain', ['/usr/bin/xcrun', 'swift', '--version'])
        build_args = ['/usr/bin/xcrun', 'swift', 'build', '--build-system', 'swiftbuild',
                      '-c', 'release', '--jobs', '4', '--package-path', consumer,
                      '--scratch-path', output / 'build']
        run('consumer-build', build_args + ['--product', 'Consumer'])
        bin_directory = Path(run('consumer-bin-path', build_args + ['--show-bin-path']).strip())
        binary = bin_directory / 'Consumer'
        if not binary.is_file() or not binary.resolve().is_relative_to(output):
            raise RuntimeError(f'Unexpected fresh consumer binary path: {binary}')
        state['consumer_binary'] = {'path': str(binary), 'sha256': sha(binary)}
        encoded = output / 'encoded'
        encoded.mkdir(exist_ok=False)
        run('fresh-successor-export', [binary, fixtures, encoded])
        actual_names = {p.name for p in encoded.iterdir() if p.is_file()}
        expected_names = {name + '.jls' for name in plan['expected_cases']['export']}
        if actual_names != expected_names or len(actual_names) != 1026:
            raise RuntimeError(f'Fresh export set mismatch; missing={expected_names-actual_names}, extra={actual_names-expected_names}')
        outputs = {p.name: {'sha256': sha(p), 'bytes': p.stat().st_size} for p in sorted(encoded.iterdir())}
        (output / 'encoded-inventory.json').write_text(json.dumps(outputs, indent=2) + '\n')
        for category, script, oracle in [('scalar', 'verify.py', 'charls-driver'),
                                         ('component', 'verify-components.py', 'charls-driver'),
                                         ('mapping', 'verify-mapping.py', 'mapping-driver')]:
            report = output / (category + '-report.json')
            cmd = [sys.executable, ROOT / 'scripts' / script, '--oracle', plan['oracles'][oracle]['path'],
                   '--fixtures', fixtures, '--encoded', encoded, '--report', report]
            if category == 'scalar':
                cmd.append('--exclude-presets')
            run(category + '-oracle', cmd)
            data = json.loads(report.read_text())
            cases = data['cases'] if isinstance(data, dict) else data
            names = [case['name'] for case in cases]
            expected = plan['expected_cases'][category]
            if len(names) != len(expected) or set(names) != set(expected) or not all(c['passed'] is True for c in cases):
                raise RuntimeError(f'{category} independent result set does not match the predeclared cases.')
            if category == 'mapping' and (data['passed'] != 136 or data['oracle_revision'] != plan['oracles'][oracle]['upstream_revision']):
                raise RuntimeError('Mapping oracle report provenance mismatch.')
            state['reports'][category] = {'path': str(report), 'sha256': sha(report), 'passed': len(cases)}
        state['verified_total'] = sum(x['passed'] for x in state['reports'].values())
        if state['verified_total'] != 990:
            raise RuntimeError('Independent verification total is not990.')
        if sha(binary) != state['consumer_binary']['sha256']:
            raise RuntimeError('Consumer binary changed after export.')
        state['status'] = 'passed'
    except BaseException as exc:
        state['status'] = 'failed'
        state['failure'] = repr(exc)
        state['traceback'] = traceback.format_exc()
        failure = exc
    finally:
        try:
            state['postflight'] = guard()
        except BaseException as exc:
            state['status'] = 'failed'
            state['postflight_failure'] = repr(exc)
            failure = failure or exc
        state['finished_utc'] = now()
        save()
    print(json.dumps({'status': state['status'], 'summary': str(output / 'summary.json'),
                      'verified_total': state.get('verified_total')}, indent=2))
    if failure:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
