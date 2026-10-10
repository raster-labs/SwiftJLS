#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Linux campaign supervisor: retain logs, peak RSS and enforce a heartbeat."""
import argparse, json, os, pathlib, selectors, signal, subprocess, time
p = argparse.ArgumentParser()
p.add_argument('--seconds', type=int, required=True)
p.add_argument('--entry', choices=['owned', 'into', 'inspect'], required=True)
a = p.parse_args()
assert 1 <= a.seconds <= 3900
command = ['Examples/FuzzConsumer/.build/release/FuzzConsumer', 'Tests/SwiftJLSTests/Fixtures', a.entry, str(a.seconds), 'last-input.jls']
start = heartbeat = time.monotonic()
peak = 0
failure = None
with open('campaign.jsonl', 'wb') as log, open('campaign-stderr.log', 'wb') as errors:
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, start_new_session=True)
    selector = selectors.DefaultSelector()
    selector.register(process.stdout, selectors.EVENT_READ)
    while process.poll() is None:
        now = time.monotonic()
        if now - heartbeat > 30 or now - start > a.seconds + 45:
            failure = 'Campaign heartbeat or total deadline exceeded'
            os.killpg(process.pid, signal.SIGKILL)
            break
        try:
            for line in pathlib.Path(f'/proc/{process.pid}/status').read_text().splitlines():
                if line.startswith(('VmRSS:', 'VmHWM:')):
                    peak = max(peak, int(line.split()[1]) * 1024)
        except FileNotFoundError:
            pass
        for key, _ in selector.select(timeout=1):
            chunk = os.read(key.fileobj.fileno(), 65536)
            if chunk:
                log.write(chunk)
                log.flush()
                heartbeat = time.monotonic()
    remaining = process.stdout.read()
    if remaining:
        log.write(remaining)
    code = process.wait()
report = dict(command=command, exit_code=code, failure=failure,
              wall_seconds=time.monotonic() - start, peak_process_rss_bytes=peak,
              build='release with AddressSanitizer; RSS includes sanitizer overhead')
pathlib.Path('campaign-result.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
assert code == 0 and failure is None
records = [json.loads(line) for line in pathlib.Path('campaign.jsonl').read_text().splitlines()]
assert records[-1]['complete'] and records[-1]['seconds'] >= a.seconds
