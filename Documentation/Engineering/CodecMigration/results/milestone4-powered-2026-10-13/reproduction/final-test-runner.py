#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Negative controls: invalid measurements must never become benchmark evidence."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile

runner = pathlib.Path(__file__).with_name('compare.py').resolve()
with tempfile.TemporaryDirectory() as temporary:
    root = pathlib.Path(temporary)
    binary = root / 'consumer'
    binary.write_text('''#!/usr/bin/env python3
import json, os, sys
width,height,bits,pattern,warmups,iterations,label=sys.argv[1:8]
fault=os.environ.get('BENCHMARK_TEST_FAULT')
if fault=='exit': sys.exit(17)
record=dict(label=label,width=int(width),height=int(height),bits=int(bits),pattern=pattern,
    resource_profile='successor-workspace-1GiB-memory-2GiB-v1',
    warmups=int(warmups),iterations=int(iterations),components=1,near=0,interleave=0,
    end_to_end=os.environ['SWIFTJLS_BENCHMARK_END_TO_END']=='1',encoded_bytes=100,
    peak_process_rss_bytes=1024,encode_seconds=[.02]*5,decode_seconds=[.01]*5,
    prepare_seconds=[.005]*5,prepare_encode_seconds=[.025]*5)
if fault=='old': record.pop('end_to_end')
if fault=='resource': record.pop('resource_profile')
if fault=='empty': record['prepare_seconds']=[]
if fault=='nonfinite': record['encode_seconds']=[float('nan')]*5
if fault=='profile': record['width']=99
if fault=='boundary': record['prepare_encode_seconds']=[.001]*5
print(json.dumps(record))
''')
    binary.chmod(0o755)
    env = {k: v for k, v in os.environ.items() if not k.startswith('SWIFTJLS_BENCHMARK_')}
    def run(name, extra_env=None, mode=True, arguments=()):
        command = [sys.executable, str(runner), '--predecessor', str(binary),
                   '--successor', str(binary), '--output', str(root / name), '--smoke']
        if mode:
            command += ['--end-to-end']
        command += list(arguments)
        return subprocess.run(command, env=dict(env, **(extra_env or {})), capture_output=True)
    checks = []
    for mode in [False, True]:
        name = 'valid-' + str(mode)
        result = run(name, mode=mode)
        assert result.returncode == 0, result.stderr.decode()
        report = json.loads((root / name / 'summary.json').read_text())
        assert len(report) == 6 and all(not r['performance_qualified'] for r in report)
        if mode:
            assert all(r['successor']['prepare_encode']['samples'] == 20 for r in report)
        checks.append(name)
    for fault in ['exit', 'old', 'resource', 'empty', 'nonfinite', 'profile', 'boundary']:
        result = run(fault, {'BENCHMARK_TEST_FAULT': fault})
        assert result.returncode != 0 and not (root / fault / 'summary.json').exists(), fault
        checks.append('reject-' + fault)
    for variable in ['SWIFTJLS_BENCHMARK_EXPORT', 'SWIFTJLS_BENCHMARK_DECODE']:
        assert run(variable, {variable: '/unused'}).returncode != 0
        checks.append('reject-' + variable)
    previous = (root / 'valid-True' / 'summary.json').read_bytes()
    assert run('valid-True').returncode != 0
    assert (root / 'valid-True' / 'summary.json').read_bytes() == previous
    checks.append('preserve-existing-evidence')
    selection = root / 'cases.json'
    case = [37, 23, 12, 'noise', 1, 0, 0]
    selection.write_text(json.dumps([case]))
    assert run('selected', arguments=['--cases', str(selection)]).returncode == 0
    selected_report = json.loads((root / 'selected' / 'summary.json').read_text())
    assert len(selected_report) == 1 and selected_report[0]['pattern'] == 'noise'
    selected_environment = json.loads((root / 'selected' / 'environment.json').read_text())
    assert selected_environment['selected_cases'] == [case] and selected_environment['case_selection_sha256']
    checks.append('selected-case-retains-twenty-observations')
    assert selected_report[0]['successor']['encode']['samples'] == 20
    for name, content in [('empty-selection', []), ('duplicate-selection', [case, case]),
                          ('unknown-selection', [[38, 23, 12, 'noise', 1, 0, 0]]),
                          ('invalid-selection-type', [[True, 23, 12, 'noise', 1, 0, 0]])]:
        selection.write_text(json.dumps(content))
        assert run(name, arguments=['--cases', str(selection)]).returncode != 0
        assert not (root / name).exists()
        checks.append('reject-' + name)
    print(json.dumps(dict(passed=len(checks), checks=checks), indent=2))
