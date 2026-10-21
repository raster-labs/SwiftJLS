#!/usr/bin/env python3
"""Run only in an authorised exclusive timing window after final builds finish.

This driver never builds. A frozen benchmark-build.json supplies source and
binary identity; source guards and the sampled AC guard fail closed. All output
directories must be fresh. Historical measurements are never overwritten.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CLT = '/Library/Developer/CommandLineTools'
PREDECESSOR = '15aa75164145414f3d5ffb801401c52d40cc5bcc'
ENV = dict(os.environ, DEVELOPER_DIR=CLT, PYTHONDONTWRITEBYTECODE='1')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def command(args, cwd=ROOT):
    result = subprocess.run(args, cwd=cwd, env=ENV, capture_output=True, text=True, timeout=15)
    return dict(command=list(args), exit_code=result.returncode, stdout=result.stdout, stderr=result.stderr)


def git(*args, cwd=ROOT):
    result = command(['git', *args], cwd=cwd)
    assert result['exit_code'] == 0, result
    return result['stdout'].strip()


def validate_identity(record):
    assert record['developer_dir'] == CLT
    assert record['predecessor_commit'] == PREDECESSOR
    assert record['source_commit'] == git('rev-parse', 'HEAD'), 'HEAD differs from frozen build source'
    assert not git('diff', 'HEAD', '--', 'Sources', 'Package.swift'), 'Dirty source/package'
    assert not git('ls-files', '--others', '--exclude-standard', '--', 'Sources'), 'Untracked production source'
    files = sorted(p for p in (ROOT / 'Sources').rglob('*') if p.is_file()) + [ROOT / 'Package.swift']
    actual = {str(p.relative_to(ROOT)): sha(p) for p in files}
    assert actual == record['source_files'], 'Built-source file hash inventory differs'
    for path, digest in actual.items():
        committed = subprocess.check_output(['git', 'show', record['source_commit'] + ':' + path], cwd=ROOT)
        assert hashlib.sha256(committed).hexdigest() == digest, 'Source file not identical to frozen commit'
    assert git('rev-parse', 'HEAD', cwd=ROOT.parent / 'JLSwift') == PREDECESSOR
    assert not git('diff', 'HEAD', '--', 'Sources', 'Package.swift', cwd=ROOT.parent / 'JLSwift')
    assert sha(HERE / 'Consumer.swift') == record['consumer_sha256']
    assert sha(ROOT / 'Scripts/Benchmark/Consumer.swift') == record['consumer_sha256']
    binaries = {label: Path(path).resolve() for label, path in record['binaries'].items()}
    assert set(binaries) == {'predecessor', 'successor'}
    for label, path in binaries.items():
        assert sha(path) == record['binary_sha256'][label], f'{label} binary differs from build record'
        consumer = ROOT / 'work/m4-benchmark' / label / 'Sources/Benchmark/main.swift'
        assert sha(consumer) == record['consumer_sha256'], f'{label} consumer source differs'
    assert record['builds_verified'] is True, 'Build provenance has not been checked'
    return binaries


class PowerGuard:
    """Record power every two seconds; loss/unknown aborts the child group.

    This sampled guard does not establish continuous electrical/thermal isolation.
    It does prevent knowingly retaining a campaign after a detected interruption.
    """
    def __init__(self, output):
        self.output = output
        self.stop = threading.Event()
        self.failed = threading.Event()
        self.failure = None
        self.thread = None

    def sample(self, telemetry=False):
        result = dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            power=command(['pmset', '-g', 'batt']))
        if telemetry:
            result.update(thermal=command(['pmset', '-g', 'therm']),
                load=command(['sysctl', '-n', 'vm.loadavg']), memory=command(['memory_pressure', '-Q']))
        if result['power']['exit_code'] != 0 or 'AC Power' not in result['power']['stdout']:
            self.failure = dict(reason='AC power lost or unavailable', observation=result)
            self.failed.set()
        return result

    def monitor(self):
        try:
            with (self.output / 'conditions.jsonl').open('x') as log:
                index = 0
                while not self.stop.is_set():
                    log.write(json.dumps(self.sample(telemetry=index % 15 == 0)) + '\n'); log.flush()
                    if self.failed.is_set() or self.stop.wait(2):
                        break
                    index += 1
                log.write(json.dumps(self.sample(telemetry=True)) + '\n'); log.flush()
        except Exception as error:
            self.failure = dict(reason='Condition monitor failed', error=repr(error))
            self.failed.set()

    def start(self):
        initial = self.sample(telemetry=True)
        (self.output / 'conditions-initial.json').write_text(json.dumps(initial, indent=2) + '\n')
        assert not self.failed.is_set(), 'Controlled timing requires AC power'
        self.thread = threading.Thread(target=self.monitor, daemon=True)
        self.thread.start()

    def finish(self):
        self.stop.set()
        if self.thread:
            self.thread.join()
        if self.failure:
            (self.output / 'power-failure.json').write_text(json.dumps(self.failure, indent=2) + '\n')


def stop_group(process):
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=['full', 'tiny'], required=True)
    parser.add_argument('--build-record', type=Path, default=HERE / 'benchmark-build.json')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    record = json.loads(args.build_record.read_text())
    binaries = validate_identity(record)
    if args.check_only:
        print(json.dumps(dict(identity_verified=True, phase=args.phase, source=record['source_commit'],
            binary_sha256=record['binary_sha256'], timing_run=False), indent=2))
        return
    assert not any(os.environ.get(k) for k in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE'])
    output = (args.output or (HERE / 'powered' if args.phase == 'full' else HERE / 'diagnostics/final-tiny-deep-warm')).resolve()
    output.mkdir(parents=True, exist_ok=False)
    (output / 'build-identity.json').write_text(json.dumps(record, indent=2) + '\n')
    (output / 'driver.json').write_text(json.dumps(dict(driver_sha256=sha(Path(__file__)),
        developer_dir=CLT, phase=args.phase, power_guard_interval_seconds=2,
        condition_telemetry_interval_seconds=30, performance_acceptance='Not automatically determined'), indent=2) + '\n')
    phases = [('scalar', HERE / 'compare-full.py', []),
        ('colour', HERE / 'compare-full.py', ['--colour', '--cases', str(HERE / 'colour-cases.json')])] if args.phase == 'full' else [
        ('tiny', HERE / 'compare-small-deep-warm.py', ['--cases', str(HERE / 'small-cases.json')])]
    guard = PowerGuard(output)
    commands = []
    process = None
    success = False
    try:
        guard.start()
        for label, runner, extra in phases:
            assert not guard.failed.is_set(), 'Power guard failed'
            cmd = ['python3', str(runner), '--predecessor', str(binaries['predecessor']),
                '--successor', str(binaries['successor']), '--output', str(output / label), '--end-to-end', *extra]
            started = time.monotonic()
            with (output / (label + '.log')).open('x') as log:
                process = subprocess.Popen(cmd, cwd=ROOT, env=ENV, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                while process.poll() is None:
                    if guard.failed.wait(.25):
                        stop_group(process)
                        break
                exit_code = process.wait()
            commands.append(dict(label=label, command=cmd, exit_code=exit_code,
                seconds=time.monotonic() - started, power_guard_failed=guard.failed.is_set()))
            (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
            assert exit_code == 0 and not guard.failed.is_set(), f'{label} comparison failed or lost AC power'
            print(label + ' comparison completed', flush=True)
        validate_identity(record)
        guard.finish()
        assert not guard.failed.is_set(), 'Final power observation failed'
        success = True
    finally:
        if process and process.poll() is None:
            stop_group(process)
        guard.finish()
        (output / 'status.json').write_text(json.dumps(dict(completed=success,
            source_commit=record['source_commit'], phase=args.phase,
            power_guard_failed=guard.failed.is_set(), qualification='Requires independent analysis and disposition; no automatic waiver'), indent=2) + '\n')


if __name__ == '__main__':
    main()
