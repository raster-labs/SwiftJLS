#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay requested heap bytes between explicit consumer allocation markers.

Heaptrack 1.5 interpreted format 3. Categories describe allocation stacks, not
allocator usable sizes. Baseline objects remain live during the marked operation.
No estimate is substituted for missing stacks, stack usage or runtime bytes.
"""
import argparse, collections, gzip, hashlib, json, pathlib, re, subprocess


def classify(frames):
    stack = re.sub(r'\((\w+) in _[0-9A-Fa-f]+\)', r'\1', '\n'.join(frames))
    if 'swiftjls_workspace_begin' in stack: return 'begin_marker'
    if 'swiftjls_workspace_end' in stack: return 'end_marker'
    if 'SwiftJLS.OwnedImageStorage.init' in stack and 'Swift.Array.init(repeating:' in stack:
        return 'owned_pixel_buffer'
    if re.search(r'SwiftJLS\.JPEGLSBitstream(?:Reader|Writer(?:State)?)\.(?:__allocating_init|init|append|getData|write)', stack):
        return 'compressed_buffer'
    if any(s in stack for s in ['JPEGLSContextModel.', 'JPEGLSRegularMode.init', 'JPEGLSRegularModeDecoder.init', 'PredictorRows.init']):
        return 'algorithm_state'
    if any(s in '\n'.join(frames[:3]) for s in ['<SwiftJLS.ComponentSampleReader>', '<SwiftJLS.ComponentSampleWriter>', 'SwiftJLS.JPEGLSScalarKernel.PredictorRows', 'SwiftJLS.JPEGLSScalarKernel.Neighbours']):
        return 'algorithm_state'
    if any(s in stack for s in ['JPEGLSHeader.parse', 'JPEGMetadata', 'JPEGLSMapping', 'JPEGLSFrameHeader', 'JPEGLSScanHeader', 'ImageDescriptor.', 'PlaneDescriptor.', 'ImageMetadata.', '<SwiftJLS.ComponentCodec.Location>']):
        return 'metadata_and_descriptors'
    if 'SwiftJLS.' in stack: return 'unattributed_codec'
    return 'runtime_or_unattributed'


def replay(lines):
    if not lines or lines[0].split() != ['v', '10500', '3']:
        raise ValueError('Expected Heaptrack 1.5 interpreted format 3')
    strings = ['']
    for line in lines:
        if line.startswith('s '):
            _, length, value = line.rstrip('\n').split(' ', 2)
            if len(value.encode()) != int(length, 16): raise ValueError('Invalid string')
            strings.append(value)
    names = subprocess.run(['swift', 'demangle', '--compact'], input='\n'.join(strings),
        capture_output=True, text=True, check=True).stdout.splitlines()
    if len(names) != len(strings): raise ValueError('Demangler changed string count')
    ips, traces, infos = [[]], [None], []
    counts, live, baseline, peaks, calls, allocated = [collections.Counter() for _ in range(6)]
    phase, begins, ends, process_live, process_peak, phase_peak = 0, 0, 0, 0, 0, 0
    stacks, cache = {}, {}
    def frames_for(index):
        if index not in cache:
            frames, cursor = [], index
            while cursor:
                ip, parent = traces[cursor]
                if parent >= cursor: raise ValueError('Invalid trace ancestry')
                frames.extend(ips[ip]); cursor = parent
            cache[index] = frames
        return cache[index]
    for line in lines:
        tag = line[:1]
        if tag not in ['i','t','a','+','-']: continue
        v = [int(x,16) for x in line.split()[1:]]
        if tag == 'i': ips.append([names[v[i]] for i in range(2,len(v),3)])
        elif tag == 't': traces.append(tuple(v))
        elif tag == 'a':
            size, trace = v; frames = frames_for(trace)
            infos.append((size, classify(frames), trace))
        else:
            index, = v; size, group, trace = infos[index]
            if tag == '+':
                counts[index] += 1; process_live += size
                if group == 'begin_marker':
                    begins += 1
                    if phase != 0: raise ValueError('Repeated begin marker')
                    baseline = live.copy(); peaks = live.copy(); phase = 1
                elif group == 'end_marker':
                    ends += 1
                    if phase != 1: raise ValueError('End without begin')
                    phase = 2
                else:
                    live[group] += size
                    if phase == 1:
                        calls[group] += 1; allocated[group] += size
                        key = str(trace)
                        if key not in stacks: stacks[key] = dict(category=group, frames=frames_for(trace), allocation_calls=0, allocated_bytes=0)
                        stacks[key]['allocation_calls'] += 1; stacks[key]['allocated_bytes'] += size
            else:
                if counts[index] <= 0: raise ValueError('Free without live allocation')
                counts[index] -= 1; process_live -= size
                if group not in ['begin_marker','end_marker']: live[group] -= size
            process_peak = max(process_peak, process_live)
            if phase == 1:
                phase_peak = max(phase_peak, sum(live.values()))
                for group, value in live.items(): peaks[group] = max(peaks[group], value)
            elif phase == 2 and ends == 1:
                # Capture once; later post-verification allocation events are excluded.
                end_live = live.copy(); ends = 2
    if begins != 1 or ends != 2: raise ValueError('Missing unique operation markers')
    groups = {g: dict(baseline_live_bytes=baseline[g], peak_live_bytes=peaks[g],
        peak_above_baseline_bytes=peaks[g]-baseline[g], end_live_bytes=end_live[g],
        phase_allocation_calls=calls[g], phase_allocated_bytes=allocated[g])
        for g in sorted(set(baseline)|set(calls))}
    return dict(groups=groups, phase_total_requested_heap_peak_bytes=phase_peak,
        process_requested_heap_peak_bytes=process_peak, allocation_stacks=stacks,
        stack_peak_bytes=None, allocator_overhead_bytes=None,
        pure_algorithm_workspace_complete=False,
        limitations=[
            'Requested heap bytes exclude allocator usable-size overhead, stack, VM mappings and RSS.',
            'Categories are stack attribution. Unattributed codec and runtime allocations remain explicit.',
            'Per-category peak deltas are relative to live pre-operation setup; they peak at different instants and must not be added.',
            'Allocation-info indices aggregate identical size/stack pairs, so individual pre-existing runtime object lifetimes cannot be separated.',
            'One operation and one synthetic profile per process; this does not establish all-profile or concurrent workspace bounds.',
            'Production peakWorkspaceBytes remains unknown; this profile does not supply a complete runtime counter.'])


def self_test():
    symbols = ['swiftjls_workspace_begin','swiftjls_workspace_end','SwiftJLS.JPEGLSContextModel.init','SwiftJLS.OwnedImageStorage.init','Swift.Array.init(repeating:']
    lines = ['v 10500 3\n']+[f's {len(s):x} {s}\n' for s in symbols]
    lines += [f'i {i:x} 0 {i:x} 0 0\n' for i in range(1,6)]
    lines += ['t 1 0\n','t 2 0\n','t 3 0\n','t 4 0\n','t 5 4\n',
        'a 1 1\n','a 2 2\n','a 14 3\n','a 64 5\n',
        '+ 3\n','+ 0\n','+ 2\n','- 2\n','+ 1\n','+ 2\n']
    assert classify(['SwiftJLS.JPEGLSBitstreamWriter.(append in _ABC123)(Swift.UInt8)']) == 'compressed_buffer'
    assert classify(['SwiftJLS.JPEGLSScalarKernel.encode(writer: SwiftJLS.JPEGLSBitstreamWriter)']) == 'unattributed_codec'
    r = replay(lines)
    assert r['phase_total_requested_heap_peak_bytes'] == 120
    assert r['groups']['owned_pixel_buffer']['peak_above_baseline_bytes'] == 0
    assert r['groups']['algorithm_state']['peak_above_baseline_bytes'] == 20
    assert r['groups']['algorithm_state']['phase_allocation_calls'] == 1
    for bad in [lines[:-2], lines+['+ 0\n'], lines+['- 0\n','- 0\n']]:
        try: replay(bad)
        except ValueError: pass
        else: raise AssertionError('Malformed profile accepted')
    print('Marked operation replay controls passed')

if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('--profile',type=pathlib.Path); p.add_argument('--output',type=pathlib.Path)
    p.add_argument('--revision'); p.add_argument('--self-test',action='store_true'); a=p.parse_args()
    if a.self_test: self_test()
    else:
        if not all([a.profile,a.output,a.revision]): p.error('profile, output, revision required')
        with gzip.open(a.profile,'rt') as f: result=replay(f.readlines())
        result.update(revision=a.revision,profile_sha256=hashlib.sha256(a.profile.read_bytes()).hexdigest())
        a.output.write_text(json.dumps(result,indent=2)+'\n')
