#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay requested heap bytes between explicit consumer allocation markers.

Heaptrack 1.5 interpreted format 3. Categories describe allocation stacks, not
allocator usable sizes. Baseline objects remain live during the marked operation.
No estimate is substituted for missing stacks, stack usage or runtime bytes.
"""
import argparse, collections, gzip, hashlib, json, pathlib, re, subprocess


def classify(frames, size=None):
    stack = re.sub(r'\((\w+) in _[0-9A-Fa-f]+\)', r'\1', '\n'.join(frames))
    allocation = '\n'.join(frames[:6])
    if 'swiftjls_workspace_begin' in stack: return 'begin_marker'
    if 'swiftjls_workspace_end' in stack: return 'end_marker'
    # Generic type metadata and protocol-conformance caches belong to the
    # Swift runtime even when a codec method triggered their first use.
    if any(s in '\n'.join(frames[:8]) for s in [
            'swift::ConcurrentReadableHashMap', 'swift::LockingConcurrentMap',
            'swift::MetadataCache', '::GenericMetadataCache', 'swift_getGenericMetadata',
            'swift_getTupleTypeMetadata', 'swift_getExistentialTypeMetadata', 'Swift._swift_getKeyPath',
            'Swift.InstantiateKeyPathBuffer', 'Swift.AnyKeyPath._create']):
        return 'runtime_or_unattributed'
    # On Linux AArch64, ELF '$x' mapping symbols in libswiftCore.so shadow
    # the local GenericMetadataCache::getWithInit symbol in frames[:8].
    # Match only the exact 48-byte 14-frame canonical generic-metadata
    # initialization prefix immediately below either the synthetic-setup
    # OwnedImageStorage.withUnsafeMutableBytes closure or the fixture-setup
    # FoundationEssentials.ProcessInfo.activeProcessorCount / ResourceLimits.init chain.
    canonical_metadata_prefix = [
        'operator new(unsigned long)',
        '$x',
        'swift::threading_impl::once_slow(swift::threading_impl::once_t&, void (*)(void*), void*)',
        '$x',
        '$x',
        'swift::threading_impl::once_slow(swift::threading_impl::once_t&, void (*)(void*), void*)',
        'swift_getCanonicalPrespecializedGenericMetadata',
        '__swift_instantiateCanonicalPrespecializedGenericMetadata',
        '$x',
        '$x',
        'swift_getTypeByMangledNode',
        'swift_getTypeByMangledName',
        '$x',
        '__swift_instantiateConcreteTypeFromMangledName',
    ]
    fixture_canonical_tail = [
        'generic specialization <Swift.String, Any> of Swift._NativeDictionary._copyOrMoveAndResize(capacity: Swift.Int, moveElements: Swift.Bool) -> ()',
        'generic specialization <Swift.String, Any> of Swift._NativeDictionary.setValue(_: __owned B, forKey: A, isUnique: Swift.Bool) -> ()',
        'generic specialization <FoundationEssentials.URL> of FoundationEssentials.readBytesFromFile<A where A: FoundationEssentials.FileSystemRepresentable, A: ~Swift.Copyable>(path: A, reportProgress: Swift.Bool, maxLength: Swift.Int?, options: FoundationEssentials.Data.ReadingOptions, attributesToRead: [Swift.String], attributes: inout [Swift.String : FoundationEssentials.Data]) throws -> FoundationEssentials.ReadBytesResult',
        'merged generic specialization <FoundationEssentials.URL> of FoundationEssentials.readDataFromFile<A where A: FoundationEssentials.FileSystemRepresentable, A: ~Swift.Copyable>(path: A, reportProgress: Swift.Bool, maxLength: Swift.Int?, options: FoundationEssentials.Data.ReadingOptions) throws -> FoundationEssentials.Data',
        'generic specialization <FoundationEssentials.URL> of FoundationEssentials.readDataFromFile<A where A: FoundationEssentials.FileSystemRepresentable, A: ~Swift.Copyable>(path: A, reportProgress: Swift.Bool, maxLength: Swift.Int?, options: FoundationEssentials.Data.ReadingOptions) throws -> FoundationEssentials.Data',
        'function signature specialization <Arg[2] = Dead> of static FoundationEssentials._ProcessInfo.coreCount(quota: FoundationEssentials.URL, period: FoundationEssentials.URL) -> Swift.Int?',
        'FoundationEssentials.ProcessInfo.activeProcessorCount.getter : Swift.Int',
        'SwiftJLS.ResourceLimits.init(watch: Swift.Bool) -> SwiftJLS.ResourceLimits',
    ]
    if size == 48 and len(frames) > 14 and frames[:14] == canonical_metadata_prefix:
        norm_tail = [re.sub(r'\((\w+) in _[0-9A-Fa-f]+\)', r'\1', f) for f in frames[14:22]]
        if norm_tail[0] == 'closure #1 (inout SwiftJLS.OwnedImageStorage.State) throws -> A in SwiftJLS.OwnedImageStorage.withUnsafeMutableBytes<A>(lease: SwiftJLS.StorageWriteLease, _: (Swift.UnsafeMutableRawBufferPointer) throws -> A) throws -> A':
            return 'runtime_or_unattributed'
        if norm_tail == fixture_canonical_tail:
            return 'runtime_or_unattributed'
    # Fixture setup first asks ResourceLimits for the processor count. The
    # observed Foundation singleton and three cached Linux cgroup URLs are
    # process-runtime storage. Require their named initialiser and ProcessInfo
    # frame before the first codec frame, not merely somewhere in a call stack.
    runtime_origin = stack.split('SwiftJLS.', 1)[0]
    if 'FoundationEssentials.ProcessInfo.' in runtime_origin and any(
            'one-time initialization function for ' + name in runtime_origin
            for name in ['processInfo', 'cfsQuotaURL', 'cfsPeriodURL', 'cpuSetURL']):
        return 'runtime_or_unattributed'
    if 'SwiftJLS.OwnedImageStorage.init' in stack and 'Swift.Array.init(repeating:' in stack:
        return 'owned_pixel_buffer'
    owned_factory_pixel_stack = [
        'swift_slowAlloc',
        'swift_allocObject',
        'Swift._ContiguousArrayBuffer.init(_uninitializedCount: Swift.Int, minimumCapacity: Swift.Int) -> Swift._ContiguousArrayBuffer<A>',
        'generic specialization <Swift.UInt8> of static Swift.Array._allocateUninitialized(Swift.Int) -> ([A], Swift.UnsafeMutablePointer<A>)',
        'generic specialization <Swift.UInt8> of Swift.Array.init(repeating: A, count: Swift.Int) -> [A]',
        'static SwiftJLS.OwnedImageStorage.fillAndSealAdmittedOwned(byteCount: Swift.Int, limits: SwiftJLS.ResourceLimits, _: (Swift.UnsafeMutableRawBufferPointer) throws -> ()) throws -> SwiftJLS.ReadOnlyImageStorage',
    ]
    if frames[:6] == owned_factory_pixel_stack:
        return 'owned_pixel_buffer'
    # Candidate004's private reserved-storage initializer constructs exactly
    # one UInt8 pixel array (ImageStorage.swift:65-72). The private symbol's
    # disambiguator changes independently of its semantics. Require the exact
    # allocator/UInt8-array/private-constructor/allocating-constructor prefix;
    # an OwnedImageStorage caller elsewhere in a stack is insufficient.
    reserved_pixel_constructor = (
        r'SwiftJLS\.OwnedImageStorage\.\(in _[0-9A-Fa-f]+\)\.init\('
        r'reservedByteCount: Swift\.Int, allocationID: FoundationEssentials\.UUID, '
        r'lease: SwiftJLS\.StorageWriteLease\) -> SwiftJLS\.OwnedImageStorage')
    if (size is not None and size > 32 and len(frames) >= 7
            and frames[:5] == owned_factory_pixel_stack[:5]
            and re.fullmatch(reserved_pixel_constructor, frames[5])
            and frames[6] == 'SwiftJLS.OwnedImageStorage.__allocating_init(reservedByteCount: Swift.Int, allocationID: FoundationEssentials.UUID, lease: SwiftJLS.StorageWriteLease) -> SwiftJLS.OwnedImageStorage'):
        return 'owned_pixel_buffer'
    # The directly allocated JPEGLSBitstreamReader object in ScalarCodec.decode
    # is six 64-bit words plus the 16-byte object header (64 requested bytes).
    # Classify only requested size 64 with the exact 3-frame immediate
    # constructor prefix as algorithm_state; reject wrong/missing sizes, wrong
    # allocators, changed constructors, or intervening frames before the broad
    # compressed_buffer rule, while retaining real compressed-array stacks
    # allocated deeper under JPEGLSBitstreamReader.init(data:).
    reader_object_prefix = [
        'swift_slowAlloc',
        'swift_allocObject',
        'SwiftJLS.JPEGLSBitstreamReader.__allocating_init(data: FoundationEssentials.Data) -> SwiftJLS.JPEGLSBitstreamReader',
    ]
    if frames[:3] == reader_object_prefix:
        return 'algorithm_state' if size == 64 else 'unattributed_codec'
    if any('SwiftJLS.JPEGLSBitstreamReader.__allocating_init' in f for f in frames) and not any(
            'SwiftJLS.JPEGLSBitstreamReader.init(' in f for f in frames):
        return 'unattributed_codec'
    if re.search(r'SwiftJLS\.JPEGLSBitstream(?:Reader|Writer(?:State)?)\.(?:__allocating_init|init|append|getData|write)', stack):
        return 'compressed_buffer'
    # In these reviewed encode entry closures, the UInt8 array allocation is
    # the inlined writer's initial reserve, not a decoded sample owner.
    if 'generic specialization <Swift.UInt8> of Swift._ContiguousArrayBuffer._consumeAndCreateNew' in allocation and re.search(r'closure #1 \(\) throws -> SwiftJLS.EncodedImage in static SwiftJLS\.(?:Scalar|Component)Codec.encode', allocation):
        return 'compressed_buffer'
    # The sole Data-to-array conversion inside the destination write borrow
    # in ComponentCodec.decode is the compressed scan reader (reviewed source).
    if 'Swift._copyCollectionToContiguousArray' in stack and 'FoundationEssentials.Data>' in stack and 'SwiftJLS.ComponentCodec.decode' in stack and 'SwiftJLS.ImageDestination.write' in stack:
        return 'compressed_buffer'
    if any(s in stack for s in ['JPEGLSContextModel.', 'JPEGLSRegularMode.init', 'JPEGLSRegularModeDecoder.init', 'PredictorRows.init']):
        return 'algorithm_state'
    # At bee49a2, sample decode compactMap grows a native-writer descriptor
    # array through capacities 1/2/4. The observed x86_64 ABI has a 32-byte
    # array header and 48-byte borrowed descriptors: 80/128/224 requested
    # bytes. Require the exact immediate allocation/append/compactMap chain
    # and decoder borrower; other sizes, element types and callers stay unknown.
    native = 'generic specialization <SwiftJLS.NativeUInt16Writer> of Swift.'
    if size in (80, 128, 224) and frames[:3] == [
            'swift_slowAlloc', 'swift_allocObject',
            native + '_ContiguousArrayBuffer._consumeAndCreateNew(bufferIsUnique: Swift.Bool, minimumCapacity: Swift.Int, growForAppend: Swift.Bool) -> Swift._ContiguousArrayBuffer<A>']:
        growth = [native + 'Array._makeUniqueAndReserveCapacityIfNotUnique() -> ()'] if size == 80 else [
            native + 'Array._createNewBuffer(bufferIsUnique: Swift.Bool, minimumCapacity: Swift.Int, growForAppend: Swift.Bool) -> ()',
            native + 'Array._reserveCapacityAssumingUniqueBuffer(oldCount: Swift.Int) -> ()']
        growth += [native + 'Array.append(__owned A) -> ()',
            'generic specialization <[SwiftJLS.ComponentSampleWriter], SwiftJLS.NativeUInt16Writer> of (extension in Swift):Swift.Sequence.compactMap<A>((A.Element) throws -> A1?) throws -> [A1]']
        caller = 3 + len(growth)
        kernel = 'SwiftJLS.JPEGLSScalarKernel.decodeInterleaved(views: [SwiftJLS.ComponentSampleWriter], width: Swift.Int, height: Swift.Int, mode: SwiftJLS.JPEGLSInterleaveMode, near: Swift.Int, parameters: SwiftJLS.JPEGLSPresetParameters, bits: Swift.Int, reader: SwiftJLS.JPEGLSBitstreamReader, verticalSampling: [Swift.Int]?, checkpoint: () throws -> ()) throws -> ()'
        if (frames[3:caller] == growth and len(frames) > caller + 1
                and frames[caller].endswith(kernel)
                and re.match(r'^closure #7 \(Swift.UnsafeMutableRawBufferPointer\) throws -> \(\) in static SwiftJLS.ComponentCodec.decode\(', frames[caller + 1])):
            return 'algorithm_state'
    if any(s in allocation for s in ['<SwiftJLS.ComponentSampleReader>', '<SwiftJLS.ComponentSampleWriter>', '<SwiftJLS.HPComponentReader>', 'SwiftJLS.JPEGLSScalarKernel.PredictorRows', 'SwiftJLS.JPEGLSScalarKernel.Neighbours']):
        return 'algorithm_state'
    # Inlined scalar near-lossless UInt16 arrays are its two predictor rows.
    if '<Swift.UInt16>' in allocation and 'JPEGLSScalarKernel.encodeNearLossless' in allocation:
        return 'algorithm_state'
    # At 940da40, native16 specialization also inlines the UInt16 element and
    # kernel frames. ScalarCodec's source-borrow closure constructs only the
    # two near-lossless row arrays through this immediate allocation shape
    # (JPEGLSScalarKernel:238-239). The measured 17/257/512 widths request
    # 32 + 2*W bytes each. Keep other widths, frames and ABIs unknown rather
    # than treating arbitrary arrays below the encode caller as workspace.
    if size in (66, 546, 1056) and len(frames) > 3 and frames[:3] == [
            'swift_slowAlloc', 'swift_allocObject',
            'Swift._ContiguousArrayBuffer.init(_uninitializedCount: Swift.Int, minimumCapacity: Swift.Int) -> Swift._ContiguousArrayBuffer<A>'] and re.match(
            r'^closure #1 \(Swift.UnsafeRawBufferPointer\) throws -> \(\) in closure #1 \(\) throws -> SwiftJLS.EncodedImage in static SwiftJLS.ScalarCodec.encode\(', frames[3]):
        return 'algorithm_state'
    if '<Swift.Int>' in allocation and any(s in allocation for s in ['JPEGLSScalarKernel.encodeInterleaved', 'JPEGLSScalarKernel.decodeInterleaved']):
        return 'algorithm_state'
    if any(s in stack for s in ['JPEGLSHeader.parse', 'JPEGLSHeader.descriptor', 'JPEGLSHeader.roles.getter', 'JPEGMetadata', 'JPEGLSMapping', 'JPEGLSFrameHeader', 'JPEGLSScanHeader', 'ImageDescriptor.', 'PlaneDescriptor.', '<SwiftJLS.PlaneDescriptor>', 'ImageMetadata.', '<SwiftJLS.ComponentCodec.Location>']):
        return 'metadata_and_descriptors'
    # Reviewed 059d97a source and ordinary-release x86_64 profiles: these
    # literal arrays are fully inlined, leaving only the immediate closure.
    # Require both that exact allocation shape and its observed requested
    # size (32-byte Array header plus payload); do not classify other closure
    # allocations, missing sizes, or different ABIs by this rule.
    if len(frames) > 2 and frames[:2] == ['swift_slowAlloc', 'swift_allocObject']:
        entry = frames[2]
        outer = re.match(r'^closure #1 \(\) throws -> SwiftJLS.EncodedImage in static SwiftJLS\.(Scalar|Component)Codec.encode\(', entry)
        if outer and (size == 72 or (size == 37 and outer[1] == 'Component')):
            # Five Int preset values (ScalarCodec:103, ComponentCodec:127),
            # or five UInt8 HP marker bytes (ComponentCodec:119).
            return 'metadata_and_descriptors'
        if size == 34 and re.match(r'^closure #3 \(Swift.UnsafeRawBufferPointer\) throws -> \(\) in closure #1 \(\) throws -> SwiftJLS.EncodedImage in static SwiftJLS.ComponentCodec.encode\(', entry):
            # One two-byte ScanComponent selector, ComponentCodec:170-172;
            # exactly one allocation per non-interleaved component scan.
            return 'metadata_and_descriptors'
    if any(s in stack for s in ['ImageDestination.__allocating_init', 'OwnedImageStorage.__allocating_init', 'SealedImageStorage.__allocating_init']):
        return 'storage_control_objects'
    # Reviewed destination-borrow closure: the only Int array constructed
    # directly here is the scan's vertical sampling schedule. Header maxima
    # use reductions and do not materialise arrays.
    if size is not None and size <= 64 and '<Swift.Int>' in allocation and 'SwiftJLS.ComponentCodec.decode' in stack and 'SwiftJLS.ImageDestination.write' in stack:
        return 'algorithm_state'
    # The inlined bit-reader object is six machine words plus its object
    # header on this observed ABI. It is allocated once per active scan
    # range (1 interleaved, 3 planar, 129 in the restart control), not once
    # per destination-write closure. Keep its algorithm state separate from
    # its compressed byte array, and leave other immediate sizes unknown.
    if size == 64 and len(frames) > 2 and frames[:2] == ['swift_slowAlloc', 'swift_allocObject'] and re.search(
            r'^closure #\d+ \(Swift.UnsafeMutableRawBufferPointer\) throws -> \(\) in static SwiftJLS.ComponentCodec.decode', frames[2]):
        return 'algorithm_state'
    # Lease-abort error objects are control storage, not prediction buffers.
    if 'swift_allocError' in allocation and 'OwnedImageStorage.' in stack:
        return 'storage_control_objects'
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
    stacks, cache, at_peak = {}, {}, {}
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
            infos.append((size, classify(frames, size), trace))
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
                        if key not in stacks: stacks[key] = dict(category=group, frames=frames_for(trace), allocation_calls=0, allocated_bytes=0, requested_size_counts={})
                        stacks[key]['allocation_calls'] += 1; stacks[key]['allocated_bytes'] += size
                        sizes = stacks[key]['requested_size_counts']
                        sizes[str(size)] = sizes.get(str(size), 0) + 1
            else:
                if counts[index] <= 0: raise ValueError('Free without live allocation')
                counts[index] -= 1; process_live -= size
                if group not in ['begin_marker','end_marker']: live[group] -= size
            process_peak = max(process_peak, process_live)
            if phase == 1:
                if sum(live.values()) > phase_peak:
                    phase_peak = sum(live.values()); at_peak = dict(live)
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
        baseline_total_requested_heap_bytes=sum(baseline.values()),
        phase_total_peak_above_baseline_bytes=phase_peak-sum(baseline.values()),
        simultaneous_categories_at_phase_peak_bytes=at_peak,
        process_requested_heap_peak_bytes=process_peak, allocation_stacks=stacks,
        stack_peak_bytes=None, allocator_overhead_bytes=None,
        codec_heap_attribution_complete=calls['unattributed_codec'] == 0 and baseline['unattributed_codec'] == 0,
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
    outer = 'closure #1 () throws -> SwiftJLS.EncodedImage in static SwiftJLS.{}Codec.encode('
    prefix = ['swift_slowAlloc', 'swift_allocObject']
    for codec in ['Scalar', 'Component']:
        frames = prefix + [outer.format(codec)]
        assert classify(frames, 72) == 'metadata_and_descriptors'
        for size in [None, 34, 71, 73, 1048576]:
            assert classify(frames, size) == 'unattributed_codec'
    assert classify(prefix + [outer.format('Component')], 37) == 'metadata_and_descriptors'
    assert classify(prefix + [outer.format('Scalar')], 37) == 'unattributed_codec'
    selector = 'closure #3 (Swift.UnsafeRawBufferPointer) throws -> () in ' + outer.format('Component')
    assert classify(prefix + [selector], 34) == 'metadata_and_descriptors'
    for size in [None, 33, 35, 1048576]:
        assert classify(prefix + [selector], size) == 'unattributed_codec'
    # Matching an ancestor is insufficient: an unrelated intervening codec
    # allocation must not acquire the ancestor's literal-array category.
    assert classify(prefix + ['SwiftJLS.Other.allocate', selector], 34) == 'unattributed_codec'
    row_array = prefix + [
        'Swift._ContiguousArrayBuffer.init(_uninitializedCount: Swift.Int, minimumCapacity: Swift.Int) -> Swift._ContiguousArrayBuffer<A>',
        'closure #1 (Swift.UnsafeRawBufferPointer) throws -> () in ' + outer.format('Scalar')]
    for size in [66, 546, 1056]:
        assert classify(row_array, size) == 'algorithm_state'
        assert classify(row_array[:3] + ['SwiftJLS.Other.allocate'] + row_array[3:], size) == 'unattributed_codec'
        assert classify(row_array[:3] + [row_array[3].replace('ScalarCodec', 'ComponentCodec')], size) == 'unattributed_codec'
        assert classify(prefix + row_array[3:], size) == 'unattributed_codec'
        assert classify(['malloc'] + row_array[1:], size) == 'unattributed_codec'
    # Include a different array-header ABI and entire 17/512-square UInt16
    # frames: neither may inherit the measured predictor-row category.
    for size in [None, 34, 50, 65, 67, 530, 545, 547, 610, 1040, 1055, 1057, 524320, 1048576]:
        assert classify(row_array, size) == 'unattributed_codec'
    schedule = ['generic specialization <Swift.Int> of Swift.Array.init',
                'SwiftJLS.ComponentCodec.decode', 'SwiftJLS.ImageDestination.write']
    assert classify(schedule, 56) == 'algorithm_state'
    for size in [None, 65, 1048576]:
        assert classify(schedule, size) == 'unattributed_codec'
    reader = prefix + ['closure #7 (Swift.UnsafeMutableRawBufferPointer) throws -> () in static SwiftJLS.ComponentCodec.decode(']
    assert classify(reader, 64) == 'algorithm_state'
    for size in [None, 63, 65, 1048576]:
        assert classify(reader, size) == 'unattributed_codec'
    native = 'generic specialization <SwiftJLS.NativeUInt16Writer> of Swift.'
    native_head = prefix + [native + '_ContiguousArrayBuffer._consumeAndCreateNew(bufferIsUnique: Swift.Bool, minimumCapacity: Swift.Int, growForAppend: Swift.Bool) -> Swift._ContiguousArrayBuffer<A>']
    native_tail = [native + 'Array.append(__owned A) -> ()',
        'generic specialization <[SwiftJLS.ComponentSampleWriter], SwiftJLS.NativeUInt16Writer> of (extension in Swift):Swift.Sequence.compactMap<A>((A.Element) throws -> A1?) throws -> [A1]',
        'SwiftJLS.JPEGLSScalarKernel.decodeInterleaved(views: [SwiftJLS.ComponentSampleWriter], width: Swift.Int, height: Swift.Int, mode: SwiftJLS.JPEGLSInterleaveMode, near: Swift.Int, parameters: SwiftJLS.JPEGLSPresetParameters, bits: Swift.Int, reader: SwiftJLS.JPEGLSBitstreamReader, verticalSampling: [Swift.Int]?, checkpoint: () throws -> ()) throws -> ()',
        'closure #7 (Swift.UnsafeMutableRawBufferPointer) throws -> () in static SwiftJLS.ComponentCodec.decode(']
    native_initial = native_head + [native + 'Array._makeUniqueAndReserveCapacityIfNotUnique() -> ()'] + native_tail
    native_growth = native_head + [
        native + 'Array._createNewBuffer(bufferIsUnique: Swift.Bool, minimumCapacity: Swift.Int, growForAppend: Swift.Bool) -> ()',
        native + 'Array._reserveCapacityAssumingUniqueBuffer(oldCount: Swift.Int) -> ()'] + native_tail
    for frames, sizes in [(native_initial, [80]), (native_growth, [128, 224])]:
        for size in sizes:
            assert classify(frames, size) == 'algorithm_state'
            assert classify(['malloc'] + frames[1:], size) == 'unattributed_codec'
            assert classify(frames[:3] + ['SwiftJLS.Other.allocate'] + frames[3:], size) == 'unattributed_codec'
            assert classify(frames[:-2] + ['SwiftJLS.Other.allocate'] + frames[-2:], size) == 'unattributed_codec'
            assert classify([f.replace('NativeUInt16Writer', 'UInt16') for f in frames], size) == 'unattributed_codec'
            assert classify([f.replace('decodeInterleaved(', 'encodeInterleaved(') for f in frames], size) == 'unattributed_codec'
            assert classify(frames[:-1] + [frames[-1].replace('ComponentCodec', 'ScalarCodec')], size) == 'unattributed_codec'
        # Reject missing sizes, neighbouring sizes/different ABIs, full frames,
        # and allocation sizes belonging only to the other observed stack shape.
        for size in [None, 79, 81, 127, 129, 223, 225, 1048576] + ([128, 224] if sizes == [80] else [80]):
            assert classify(frames, size) == 'unattributed_codec'
    assert classify(['operator new(unsigned long)', 'swift_getTupleTypeMetadata',
        'SwiftJLS.JPEGLSBitstreamReader.init(data:)'], 40) == 'runtime_or_unattributed'
    assert classify(['operator new(unsigned long)',
        'swift::Lazy<(anonymous namespace)::GenericMetadataCache>::getWithInit',
        'SwiftJLS.OwnedImageStorage.withUnsafeMutableBytes'], 40) == 'runtime_or_unattributed'
    canonical_metadata_stack = [
        'operator new(unsigned long)',
        '$x',
        'swift::threading_impl::once_slow(swift::threading_impl::once_t&, void (*)(void*), void*)',
        '$x',
        '$x',
        'swift::threading_impl::once_slow(swift::threading_impl::once_t&, void (*)(void*), void*)',
        'swift_getCanonicalPrespecializedGenericMetadata',
        '__swift_instantiateCanonicalPrespecializedGenericMetadata',
        '$x',
        '$x',
        'swift_getTypeByMangledNode',
        'swift_getTypeByMangledName',
        '$x',
        '__swift_instantiateConcreteTypeFromMangledName',
        'closure #1 (inout SwiftJLS.OwnedImageStorage.(State in _E3A3FF9B1E0185F10C196E0592093825)) throws -> A in SwiftJLS.OwnedImageStorage.withUnsafeMutableBytes<A>(lease: SwiftJLS.StorageWriteLease, _: (Swift.UnsafeMutableRawBufferPointer) throws -> A) throws -> A',
    ]
    assert classify(canonical_metadata_stack, 48) == 'runtime_or_unattributed'
    assert classify(canonical_metadata_stack[:-1] + [canonical_metadata_stack[-1].replace('_E3A3FF9B1E0185F10C196E0592093825', '_0123456789ABCDEF')], 48) == 'runtime_or_unattributed'
    for size in [None, 40, 47, 49, 64, 1048576]:
        assert classify(canonical_metadata_stack, size) == 'unattributed_codec'
    assert classify(['malloc'] + canonical_metadata_stack[1:], 48) == 'unattributed_codec'
    assert classify(['swift_slowAlloc'] + canonical_metadata_stack[1:], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:6] + canonical_metadata_stack[7:], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:6] + ['$x'] + canonical_metadata_stack[7:], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:7] + ['$x'] + canonical_metadata_stack[8:], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:6] + ['SwiftJLS.Other.allocate'] + canonical_metadata_stack[6:], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:13] + ['SwiftJLS.Other.allocate'] + canonical_metadata_stack[13:], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:14] + [outer.format('Scalar')], 48) == 'unattributed_codec'
    assert classify(canonical_metadata_stack[:6] + [canonical_metadata_stack[-1]], 48) == 'unattributed_codec'
    fixture_canonical_stack = canonical_metadata_stack[:14] + [
        'generic specialization <Swift.String, Any> of Swift._NativeDictionary._copyOrMoveAndResize(capacity: Swift.Int, moveElements: Swift.Bool) -> ()',
        'generic specialization <Swift.String, Any> of Swift._NativeDictionary.setValue(_: __owned B, forKey: A, isUnique: Swift.Bool) -> ()',
        'generic specialization <FoundationEssentials.URL> of FoundationEssentials.readBytesFromFile<A where A: FoundationEssentials.FileSystemRepresentable, A: ~Swift.Copyable>(path: A, reportProgress: Swift.Bool, maxLength: Swift.Int?, options: FoundationEssentials.Data.ReadingOptions, attributesToRead: [Swift.String], attributes: inout [Swift.String : FoundationEssentials.Data]) throws -> FoundationEssentials.ReadBytesResult',
        'merged generic specialization <FoundationEssentials.URL> of FoundationEssentials.readDataFromFile<A where A: FoundationEssentials.FileSystemRepresentable, A: ~Swift.Copyable>(path: A, reportProgress: Swift.Bool, maxLength: Swift.Int?, options: FoundationEssentials.Data.ReadingOptions) throws -> FoundationEssentials.Data',
        'generic specialization <FoundationEssentials.URL> of FoundationEssentials.readDataFromFile<A where A: FoundationEssentials.FileSystemRepresentable, A: ~Swift.Copyable>(path: A, reportProgress: Swift.Bool, maxLength: Swift.Int?, options: FoundationEssentials.Data.ReadingOptions) throws -> FoundationEssentials.Data',
        'function signature specialization <Arg[2] = Dead> of static FoundationEssentials._ProcessInfo.(coreCount in _5E3BF990DD92C0080D372AA0CF8A3C95)(quota: FoundationEssentials.URL, period: FoundationEssentials.URL) -> Swift.Int?',
        'FoundationEssentials.ProcessInfo.activeProcessorCount.getter : Swift.Int',
        'SwiftJLS.ResourceLimits.init(watch: Swift.Bool) -> SwiftJLS.ResourceLimits',
    ]
    assert classify(fixture_canonical_stack, 48) == 'runtime_or_unattributed'
    for size in [None, 40, 47, 49, 64, 1048576]:
        assert classify(fixture_canonical_stack, size) == 'unattributed_codec'
    assert classify(['malloc'] + fixture_canonical_stack[1:], 48) == 'unattributed_codec'
    assert classify(fixture_canonical_stack[:6] + fixture_canonical_stack[7:], 48) == 'unattributed_codec'
    assert classify(fixture_canonical_stack[:14] + ['SwiftJLS.Other.allocate'] + fixture_canonical_stack[14:], 48) == 'unattributed_codec'
    assert classify(fixture_canonical_stack[:-1] + [outer.format('Scalar')], 48) == 'unattributed_codec'
    assert classify(['swift_getExistentialTypeMetadata',
        'SwiftJLS.OwnedImageStorage.locked'], 16) == 'runtime_or_unattributed'
    foundation_cache = prefix + ['one-time initialization function for (cfsQuotaURL in _ABC123)',
        'FoundationEssentials.ProcessInfo.activeProcessorCount.getter', 'SwiftJLS.ResourceLimits.init']
    assert classify(foundation_cache, 176) == 'runtime_or_unattributed'
    assert classify(prefix + ['SwiftJLS.Other.allocate'] + foundation_cache[2:], 176) == 'unattributed_codec'
    owned_factory_stack = prefix + [
        'Swift._ContiguousArrayBuffer.init(_uninitializedCount: Swift.Int, minimumCapacity: Swift.Int) -> Swift._ContiguousArrayBuffer<A>',
        'generic specialization <Swift.UInt8> of static Swift.Array._allocateUninitialized(Swift.Int) -> ([A], Swift.UnsafeMutablePointer<A>)',
        'generic specialization <Swift.UInt8> of Swift.Array.init(repeating: A, count: Swift.Int) -> [A]',
        'static SwiftJLS.OwnedImageStorage.fillAndSealAdmittedOwned(byteCount: Swift.Int, limits: SwiftJLS.ResourceLimits, _: (Swift.UnsafeMutableRawBufferPointer) throws -> ()) throws -> SwiftJLS.ReadOnlyImageStorage',
    ]
    assert classify(owned_factory_stack, 610) == 'owned_pixel_buffer'
    assert classify(['malloc'] + owned_factory_stack[1:], 610) == 'unattributed_codec'
    assert classify(owned_factory_stack[:5] + ['SwiftJLS.Other.allocate'] + owned_factory_stack[5:], 610) == 'unattributed_codec'
    assert classify([f.replace('<Swift.UInt8>', '<Swift.Int>') for f in owned_factory_stack], 610) == 'unattributed_codec'
    assert classify(owned_factory_stack[:5] + ['closure #1 (Swift.UnsafeMutableRawBufferPointer) throws -> () in ' + owned_factory_stack[5]], 610) == 'unattributed_codec'
    reserved_pixel_stack = owned_factory_stack[:5] + [
        'SwiftJLS.OwnedImageStorage.(in _E3A3FF9B1E0185F10C196E0592093825).init(reservedByteCount: Swift.Int, allocationID: FoundationEssentials.UUID, lease: SwiftJLS.StorageWriteLease) -> SwiftJLS.OwnedImageStorage',
        'SwiftJLS.OwnedImageStorage.__allocating_init(reservedByteCount: Swift.Int, allocationID: FoundationEssentials.UUID, lease: SwiftJLS.StorageWriteLease) -> SwiftJLS.OwnedImageStorage',
    ]
    for requested in [33, 1766, 1572896]:
        assert classify(reserved_pixel_stack, requested) == 'owned_pixel_buffer'
    assert classify([f.replace('_E3A3FF9B1E0185F10C196E0592093825', '_ABC123') for f in reserved_pixel_stack], 1766) == 'owned_pixel_buffer'
    for requested in [None, 0, 16, 32]:
        assert classify(reserved_pixel_stack, requested) != 'owned_pixel_buffer'
    for invalid in [
        ['malloc'] + reserved_pixel_stack[1:],
        [reserved_pixel_stack[0], 'malloc'] + reserved_pixel_stack[2:],
        [f.replace('<Swift.UInt8>', '<Swift.Int>') for f in reserved_pixel_stack],
        reserved_pixel_stack[:3] + ['SwiftJLS.Other.allocate'] + reserved_pixel_stack[3:],
        reserved_pixel_stack[:5] + ['SwiftJLS.Other.allocate'] + reserved_pixel_stack[5:],
        reserved_pixel_stack[:6] + ['SwiftJLS.Other.allocate'] + reserved_pixel_stack[6:],
        [f.replace('reservedByteCount:', 'capacity:') for f in reserved_pixel_stack],
        reserved_pixel_stack[:5] + [reserved_pixel_stack[5].replace('lease:', 'unrelated:')] + reserved_pixel_stack[6:],
        reserved_pixel_stack[:6] + [reserved_pixel_stack[6].replace('allocationID:', 'otherID:')],
        reserved_pixel_stack[:6],
    ]:
        assert classify(invalid, 1766) != 'owned_pixel_buffer'
    reader_object_stack = prefix + [
        'SwiftJLS.JPEGLSBitstreamReader.__allocating_init(data: FoundationEssentials.Data) -> SwiftJLS.JPEGLSBitstreamReader',
    ]
    reader_object_full_stack = reader_object_stack + [
        'fill #1 (Swift.UnsafeMutableRawBufferPointer) throws -> () in closure #1 () throws -> SwiftJLS.DecodedImage in static SwiftJLS.ScalarCodec.decode(_: FoundationEssentials.Data, into: SwiftJLS.ImageDestination?, options: SwiftJLS.DecodeOptions, codecOptions: SwiftJLS.CodecOptions) throws -> SwiftJLS.DecodedImage',
    ]
    assert classify(reader_object_stack, 64) == 'algorithm_state'
    assert classify(reader_object_full_stack, 64) == 'algorithm_state'
    for bad_size in [None, 0, 32, 63, 65, 404, 1048576]:
        assert classify(reader_object_stack, bad_size) == 'unattributed_codec'
        assert classify(reader_object_full_stack, bad_size) == 'unattributed_codec'
    assert classify(['malloc'] + reader_object_stack[1:], 64) == 'unattributed_codec'
    assert classify(['operator new(unsigned long)'] + reader_object_stack[1:], 64) == 'unattributed_codec'
    assert classify(['swift_slowAlloc', 'malloc'] + reader_object_stack[2:], 64) == 'unattributed_codec'
    assert classify(prefix + ['SwiftJLS.JPEGLSBitstreamReader.__allocating_init(bytes: [Swift.UInt8]) -> SwiftJLS.JPEGLSBitstreamReader'], 64) == 'unattributed_codec'
    assert classify(prefix + ['SwiftJLS.JPEGLSBitstreamReader.__allocating_init() -> SwiftJLS.JPEGLSBitstreamReader'], 64) == 'unattributed_codec'
    assert classify(prefix + ['SwiftJLS.Other.allocate'] + reader_object_stack[2:], 64) == 'unattributed_codec'
    assert classify(['SwiftJLS.Other.allocate'] + reader_object_stack, 64) == 'unattributed_codec'
    assert classify(prefix + ['Swift._ContiguousArrayBuffer.init(_uninitializedCount: Swift.Int, minimumCapacity: Swift.Int) -> Swift._ContiguousArrayBuffer<A>'] + reader_object_stack[2:], 64) == 'unattributed_codec'
    assert classify(prefix + ['generic specialization <Swift.UInt8, FoundationEssentials.Data> of Swift.Array.init<A where A == A1.Element, A1: Swift.Sequence>(A1) -> [A]'] + reader_object_stack[2:], 64) == 'unattributed_codec'
    compressed_reader_array_stack = prefix + [
        'generic specialization <serialized, FoundationEssentials.Data> of Swift._copyCollectionToContiguousArray<A where A: Swift.Collection>(A) -> Swift.ContiguousArray<A.Element>',
        'protocol witness for Swift.Sequence._copyToContiguousArray() -> Swift.ContiguousArray<A.Element> in conformance FoundationEssentials.Data : Swift.Sequence in FoundationEssentials',
        'generic specialization <Swift.UInt8, FoundationEssentials.Data> of Swift.Array.init<A where A == A1.Element, A1: Swift.Sequence>(A1) -> [A]',
        'SwiftJLS.JPEGLSBitstreamReader.init(data: FoundationEssentials.Data) -> SwiftJLS.JPEGLSBitstreamReader',
        'SwiftJLS.JPEGLSBitstreamReader.__allocating_init(data: FoundationEssentials.Data) -> SwiftJLS.JPEGLSBitstreamReader',
    ]
    assert classify(compressed_reader_array_stack, 404) == 'compressed_buffer'
    assert classify(compressed_reader_array_stack, 64) == 'compressed_buffer'
    r = replay(lines)
    assert r['phase_total_requested_heap_peak_bytes'] == 120
    assert r['baseline_total_requested_heap_bytes'] == 100
    assert r['phase_total_peak_above_baseline_bytes'] == 20
    assert sum(r['simultaneous_categories_at_phase_peak_bytes'].values()) == 120
    assert r['groups']['owned_pixel_buffer']['peak_above_baseline_bytes'] == 0
    assert r['groups']['algorithm_state']['peak_above_baseline_bytes'] == 20
    assert r['groups']['algorithm_state']['phase_allocation_calls'] == 1
    # A codec allocation already live at the begin marker is still unknown;
    # zero new unknown calls alone must not claim complete heap attribution.
    unknown = 'SwiftJLS.UnknownOwner.init'
    baseline_unknown = [f's {len(unknown):x} {unknown}\n'
        if line.startswith('s ') and line.rstrip().endswith('SwiftJLS.OwnedImageStorage.init') else line
        for line in lines]
    unknown_result = replay(baseline_unknown)
    assert unknown_result['groups']['unattributed_codec']['baseline_live_bytes'] == 100
    assert unknown_result['groups']['unattributed_codec']['phase_allocation_calls'] == 0
    assert not unknown_result['codec_heap_attribution_complete']
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
