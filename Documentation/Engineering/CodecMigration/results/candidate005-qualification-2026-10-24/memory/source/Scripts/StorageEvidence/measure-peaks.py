#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay Heaptrack allocation/free events, retaining attribution limitations.

Format reference (not copied implementation): KDE Heaptrack v1.5.0,
src/analyze/accumulatedtracedata.cpp. Only interpreted format 3 is accepted.
The allocator measures requested heap bytes, not RSS, stack bytes or copy bytes.
"""
import argparse
import collections
import gzip
import hashlib
import json
import pathlib
import subprocess


def replay(lines):
    if not lines or lines[0].split() != ['v', '10500', '3']:
        raise ValueError('Expected Heaptrack 1.5.0 interpreted format 3')
    strings = ['']
    for line in lines:
        if line.startswith('s '):
            _, length, value = line.rstrip('\n').split(' ', 2)
            if len(value.encode()) != int(length, 16):
                raise ValueError('Invalid sized string')
            strings.append(value)
    demangled = subprocess.run(['swift', 'demangle', '--compact'],
        input='\n'.join(strings), text=True, capture_output=True, check=True).stdout.splitlines()
    if len(demangled) != len(strings):
        raise ValueError('Demangler changed the number of strings')
    ips, traces, infos = [[]], [None], []
    groups = collections.defaultdict(lambda: dict(live_bytes=0, peak_bytes=0, allocation_calls=0, allocated_bytes=0))
    live_counts = collections.Counter()
    cache = {}
    total = peak = count = 0

    def classify(trace):
        if trace in cache:
            return cache[trace]
        frames = []
        cursor = trace
        while cursor:
            ip, parent = traces[cursor]
            if parent >= cursor:
                raise ValueError('Invalid trace ancestry')
            frames.extend(ips[ip])
            cursor = parent
        text = '\n'.join(frames)
        codec = any('SwiftJLS.' + c + '.' + op in text
                    for c in ['ScalarCodec', 'ComponentCodec'] for op in ['encode', 'decode'])
        pixel = 'SwiftJLS.OwnedImageStorage.init' in text and 'Swift.Array.init(repeating:' in text
        if pixel:
            group = 'codec_pixel_heap' if codec else 'caller_pixel_heap'
        elif codec or 'SwiftJLS.JPEGLSHeader.parse' in text:
            group = 'codec_nonpixel_heap'
        elif 'SwiftJLS.' in text:
            group = 'other_swiftjls_heap'
        else:
            group = 'caller_runtime_unattributed_heap'
        cache[trace] = group
        return group

    for line in lines:
        tag = line[:1]
        if tag not in ['i', 't', 'a', '+', '-']:
            continue
        values = [int(x, 16) for x in line.split()[1:]]
        if tag == 'i':
            if len(values) < 2:
                raise ValueError('Invalid instruction pointer')
            ips.append([demangled[values[i]] for i in range(2, len(values), 3)])
        elif tag == 't':
            if len(values) != 2:
                raise ValueError('Invalid trace')
            traces.append(tuple(values))
        elif tag == 'a':
            size, trace = values
            infos.append((size, classify(trace)))
        else:
            index, = values
            size, group = infos[index]
            metrics = groups[group]
            if tag == '+':
                live_counts[index] += 1
                total += size
                count += 1
                peak = max(peak, total)
                metrics['live_bytes'] += size
                metrics['peak_bytes'] = max(metrics['peak_bytes'], metrics['live_bytes'])
                metrics['allocation_calls'] += 1
                metrics['allocated_bytes'] += size
            else:
                if live_counts[index] <= 0:
                    raise ValueError('Free without a live allocation')
                live_counts[index] -= 1
                total -= size
                metrics['live_bytes'] -= size
    if not count or not groups:
        raise ValueError('No allocation events')
    return dict(process_requested_heap_peak_bytes=peak,
                process_requested_heap_live_at_exit_bytes=total,
                process_allocation_calls=count, groups=dict(groups))


def self_test():
    symbols = ['SwiftJLS.OwnedImageStorage.init', 'Swift.Array.init(repeating:', 'SwiftJLS.ScalarCodec.encode']
    lines = ['v 10500 3\n'] + [f's {len(s):x} {s}\n' for s in symbols]
    lines += ['i 1 0 1 0 0\n', 'i 2 0 2 0 0\n', 'i 3 0 3 0 0\n',
              't 1 0\n', 't 2 1\n', 't 3 0\n', 'a 64 2\n', 'a 14 3\n', 'a 1e 3\n',
              '+ 0\n', '+ 1\n', '- 0\n', '+ 2\n', '- 1\n', '- 2\n']
    result = replay(lines)
    assert result['process_requested_heap_peak_bytes'] == 120
    assert result['process_requested_heap_live_at_exit_bytes'] == 0
    assert result['groups']['caller_pixel_heap']['peak_bytes'] == 100
    assert result['groups']['codec_nonpixel_heap']['peak_bytes'] == 50
    assert result['process_allocation_calls'] == 3
    try:
        replay(lines + ['- 2\n'])
    except ValueError:
        pass
    else:
        raise AssertionError('Invalid free was accepted')
    print('Peak replay controls passed')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--profile', type=pathlib.Path)
    p.add_argument('--output', type=pathlib.Path)
    p.add_argument('--revision')
    p.add_argument('--self-test', action='store_true')
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        if not all([args.profile, args.output, args.revision]):
            p.error('--profile, --output and --revision are required')
        with gzip.open(args.profile, 'rt') as f:
            result = replay(f.readlines())
        result.update(revision=args.revision, profile_sha256=hashlib.sha256(args.profile.read_bytes()).hexdigest(),
            scope='Peak simultaneously live requested heap bytes by allocation stack over the entire recorded workload.',
            limitations=[
                'Groups peak at different instants; do not sum their individual peaks.',
                'codec_nonpixel_heap includes compressed output, metadata, closures and allocator object headers; it is not pure algorithm workspace.',
                'Caller/runtime/unattributed allocations and stack storage remain separate; incomplete stacks can prevent codec attribution.',
                'Pixel heap includes array headers/capacity; it is not only sample payload.',
                'This does not measure copy bytes, RSS, per-operation workspace or concurrent admission ceilings. Production unknown workspace reports remain unknown.'])
        args.output.write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, indent=2))
