// SPDX-License-Identifier: MIT
// Copyright 2026 Raster Images Private Limited
import Foundation

/// Non-interleaved component scans share the scalar entropy kernels and borrow
/// each component directly through its descriptor. No planarisation is needed.
enum ComponentCodec {
    struct Location: Sendable {
        let offset: Int, rowBytes: Int, pixelStride: Int
        let width: Int, height: Int, horizontal: Int, vertical: Int
    }
    static func locations(_ descriptor: ImageDescriptor, limits: ResourceLimits,
                          discardICC: Bool = false) throws -> [Location] {
        try descriptor.validate(limits: limits)
        guard descriptor.sampleType == .unsignedInteger, [8, 16].contains(descriptor.storageBits),
              (2...16).contains(descriptor.meaningfulBits), (1...4).contains(descriptor.components.count),
              descriptor.alpha == .absent, descriptor.iccProfile == nil || discardICC,
              descriptor.width <= Int(clamping: UInt32.max), descriptor.height <= Int(clamping: UInt32.max) else {
            throw CodecError(.unsupportedFeature, "Component coding requires one to four unsigned components without alpha or ICC.")
        }
        return try descriptor.components.indices.map { component in
            for plane in descriptor.planes {
                if let index = plane.components.firstIndex(of: component) {
                    return Location(offset: plane.offset + index * plane.sampleStride,
                        rowBytes: plane.rowBytes, pixelStride: plane.pixelStride, width: plane.width, height: plane.height,
                        horizontal: plane.horizontalSamplingFactor, vertical: plane.verticalSamplingFactor)
                }
            }
            throw CodecError(.incompatibleImageLayout, "Component has no plane.")
        }
    }
    static func ids(_ descriptor: ImageDescriptor) throws -> [UInt8] {
        if descriptor.colour == .rgb, descriptor.components == [.red, .green, .blue] { return [1, 2, 3] }
        guard descriptor.colour == .unknown else {
            throw CodecError(.unsupportedFeature, "Only RGB or explicitly uninterpreted components are supported.")
        }
        let ids = try descriptor.components.map { role -> UInt8 in
            guard case .uninterpreted(let name) = role, name.hasPrefix("JPEG-LS:"),
                  let id = UInt8(name.dropFirst(8)), name == "JPEG-LS:\(id)" else {
                throw CodecError(.unsupportedFeature, "Uninterpreted roles must use the durable JPEG-LS:<component-id> mapping.")
            }
            return id
        }
        guard Set(ids).count == ids.count else { throw CodecError(.invalidArgument, "Duplicate component IDs.") }
        return ids
    }
    static func writeRGBHeader(width: Int, height: Int, bits: Int, writer: inout JPEGLSBitstreamWriter) {
        func long(_ value: Int) {
            writer.writeUInt16(UInt16(value >> 16)); writer.writeUInt16(UInt16(value & 65535))
        }
        // SPIFF v2, profile 0, RGB, JPEG-LS, unitless 1:1 aspect ratio. An
        // empty directory embeds the inner SOI in its end-of-directory entry.
        writer.writeByte(255); writer.writeByte(0xe8); writer.writeUInt16(32)
        for byte: UInt8 in [83, 80, 73, 70, 70, 0, 2, 0, 0, 3] { writer.writeByte(byte) }
        long(height); long(width)
        for byte in [UInt8(10), UInt8(bits), UInt8(6), UInt8(0)] { writer.writeByte(byte) }
        long(1); long(1)
        writer.writeByte(255); writer.writeByte(0xe8); writer.writeUInt16(8)
        for byte: UInt8 in [0, 0, 0, 1, 255, 216] { writer.writeByte(byte) }
    }
    static func encode(_ image: Image, configuration: EncoderConfiguration, options: EncodeOptions) throws -> EncodedImage {
        let (resolvedBackend, fallbackReason) = try AccelerationRuntime.resolve(policy: options.executionPolicy)
        let budget = CodecBudget(limits: options.resourceLimits)
        return try ScalarCodec.mapped {
            let d = image.descriptor
            let locations = try locations(d, limits: budget.limits,
                                          discardICC: options.metadataPolicy == .discardAncillary)
            guard locations.allSatisfy({ $0.width == d.width && $0.height == d.height }) else {
                throw CodecError(.unsupportedFeature, "Subsampled encoding was not implemented by the predecessor and is not advertised.")
            }
            let componentIDs = try ids(d)
            guard componentIDs.count > 1 || configuration.codecOptions.interleaveMode == .none else {
                throw CodecError(.unsupportedFeature, "A single component requires non-interleaved coding.")
            }
            let transform = configuration.codecOptions.colourTransform
            guard transform == .none || (d.colour == .rgb && [8, 16].contains(d.meaningfulBits)) else {
                throw CodecError(.unsupportedFeature, "HP transforms require RGB with 8 or 16 meaningful bits.")
            }
            let interpretationBytes = (d.colour == .rgb ? 30 : 0) + (transform == .none ? 0 : 5)
            let discardedICCBytes = d.iccProfile?.count ?? 0
            if discardedICCBytes > 0 {
                // Charge the retained profile together with image metadata and
                // required interpretation markers before borrowing any samples.
                _ = try image.metadata.validate(limits: budget.limits,
                    additionalBytes: checkedAdd(discardedICCBytes, interpretationBytes))
            }
            let metadata = try JPEGMetadataEncoding(image, options: options, additionalBytes: interpretationBytes)
            guard metadata.mapping == nil || transform == .none else {
                throw CodecError(.unsupportedFeature, "Mapping tables and HP transforms cannot be combined.")
            }
            let near: Int
            if case .nearLossless(let value) = configuration.mode { near = value } else { near = 0 }
            guard near <= min(255, ((1 << d.meaningfulBits) - 1) / 2) else {
                throw CodecError(.invalidArgument, "NEAR exceeds the maximum for this sample precision.")
            }
            let parameters: JPEGLSPresetParameters
            if let p = configuration.codecOptions.preset {
                guard p.maximumSampleValue <= (1 << d.meaningfulBits) - 1,
                      near <= min(255, p.maximumSampleValue / 2), p.threshold1 > near else {
                    throw CodecError(.invalidArgument, "Preset is incompatible with precision or NEAR.")
                }
                parameters = try JPEGLSPresetParameters(maxValue: p.maximumSampleValue,
                    threshold1: p.threshold1, threshold2: p.threshold2, threshold3: p.threshold3, reset: p.reset)
            } else { parameters = try .defaultParameters(bitsPerSample: d.meaningfulBits, near: near) }
            try metadata.mapping?.validate(components: componentIDs.count, maximum: parameters.maxValue)
            let interval = configuration.codecOptions.restartIntervalLines
            let chunks = interval > 0 ? 1 + (d.height - 1) / interval : 1
            let samples = try checkedMultiply(checkedMultiply(d.width, d.height), componentIDs.count)
            let worstOutput = try checkedAdd(checkedMultiply(samples, 10), checkedAdd(checkedAdd(256, metadata.byteCount), checkedMultiply(chunks, componentIDs.count * 4)))
            let outputLimit = min(worstOutput, budget.limits.maximumCompressedBytes)
            let predictorBytes = configuration.codecOptions.interleaveMode == .none
                ? (near > 0 ? try checkedMultiply(d.width, 4) : 0)
                : try checkedMultiply(d.width, componentIDs.count * 4)
            let baseWorkspace = try checkedAdd(checkedAdd(ScalarCodec.contextBytes, ScalarCodec.tableBytes(parameters)),
                checkedAdd(checkedMultiply(outputLimit, 2), predictorBytes))
            let baseTotalWorkspace = try checkedAdd(checkedAdd(baseWorkspace, checkedMultiply(metadata.byteCount, 32)), discardedICCBytes)

            let totalUnits = configuration.codecOptions.interleaveMode == .none ? componentIDs.count * chunks : 1
            var effectiveWorkers = (resolvedBackend == .accelerated && totalUnits > 1)
                ? min(totalUnits, BoundedParallelPool.workerCount(requested: budget.limits.maximumWorkers))
                : 1
            let perExtraWorker = ScalarCodec.contextBytes + predictorBytes
            while effectiveWorkers > 1 {
                let extra = (effectiveWorkers - 1) * perExtraWorker
                let candidateWs = baseTotalWorkspace + extra
                if candidateWs <= budget.limits.maximumWorkspaceBytes,
                   image.storage.byteCount + candidateWs + outputLimit <= budget.limits.maximumMemoryBytes {
                    break
                }
                effectiveWorkers -= 1
            }
            try budget.admit(pixelBytes: image.storage.byteCount,
                workspaceBytes: baseTotalWorkspace + (effectiveWorkers - 1) * perExtraWorker,
                compressedBytes: outputLimit)
            if budget.limits.maximumMetadataBytes < (d.colour == .rgb ? 30 : 0) + (transform == .none ? 0 : 5) {
                throw CodecError(.resourceLimitExceeded, "SPIFF header exceeds the metadata budget.")
            }
            options.progress?(try .init(phase: .processing, completedUnits: 0, totalUnits: samples))
            try budget.check()
            var writer = JPEGLSBitstreamWriter(capacity: min(outputLimit, 4096), maximumBytes: outputLimit)
            let kernel = JPEGLSScalarKernel()
            writer.writeMarker(.startOfImage)
            try metadata.writeSPIFF(to: &writer)
            if d.colour == .rgb && metadata.spiff == nil { writeRGBHeader(width: d.width, height: d.height, bits: d.meaningfulBits, writer: &writer) }
            if transform != .none {
                writer.writeByte(255); writer.writeByte(0xe8); writer.writeUInt16(7)
                for byte: UInt8 in [109, 114, 102, 120, transform.rawValue] { writer.writeByte(byte) }
            }
            try metadata.ancillary.write(to: &writer)
            let frame = try JPEGLSFrameHeader(bitsPerSample: d.meaningfulBits, height: d.height,
                width: d.width, componentCount: componentIDs.count, components: componentIDs.map { .init(id: $0) })
            try kernel.writeFrameHeaderInternal(frame, to: &writer)
            if configuration.codecOptions.preset != nil {
                writer.writeMarker(.jpegLSExtension); writer.writeUInt16(13); writer.writeByte(1)
                for value in [parameters.maxValue, parameters.threshold1, parameters.threshold2, parameters.threshold3, parameters.reset] {
                    writer.writeUInt16(UInt16(value))
                }
            }
            if interval > 0 {
                writer.writeMarker(.defineRestartInterval); writer.writeUInt16(4); writer.writeUInt16(UInt16(interval))
            }
            try metadata.mapping?.write(to: &writer, budget: budget)
            try image.storage.withUnsafeBytes { bytes in
                guard bytes.count == image.storage.byteCount, bytes.count >= d.requiredByteCount else {
                    throw CodecError(.storageUnavailable, "Provider returned inconsistent storage.")
                }
                let views = locations.map { location in
                    ComponentSampleReader(bytes: bytes, width: d.width, height: d.height,
                        offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                        sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                }
                if near > 0 || transform != .none {
                    // Approximate runs and HP's modular arithmetic cannot
                    // prove the range of every original sample while coding.
                    for view in views {
                        try view.validate(maximum: parameters.maxValue, checkpoint: { try budget.check() })
                    }
                }
                let sampleMaximum = near == 0 && transform == .none &&
                    parameters.maxValue < (d.storageBits == 8 ? 255 : 65535) ? parameters.maxValue : nil
                if configuration.codecOptions.interleaveMode != .none {
                    guard let mode = JPEGLSInterleaveMode(rawValue: configuration.codecOptions.interleaveMode.rawValue) else {
                        throw CodecError(.internalFailure, "Interleave mapping failed.")
                    }
                    let scan = try JPEGLSScanHeader(componentCount: componentIDs.count,
                        components: componentIDs.enumerated().map { .init(id: $0.element, mappingTableID: metadata.mapping?.componentTableIDs[$0.offset] ?? 0) },
                        near: near, interleaveMode: mode, pointTransform: 0)
                    try kernel.writeScanHeaderInternal(scan, to: &writer)
                    if transform == .none {
                        try kernel.encodeInterleaved(views: views, width: d.width, height: d.height,
                        mode: configuration.codecOptions.interleaveMode, near: near, parameters: parameters,
                        bits: d.meaningfulBits, sampleMaximum: sampleMaximum,
                        writer: &writer, checkpoint: { try budget.check() })
                    } else {
                        let transformed = (0..<3).map { component in
                            HPComponentReader(views: views, component: component, transform: transform, bits: d.meaningfulBits)
                        }
                        try kernel.encodeInterleaved(views: transformed, width: d.width, height: d.height,
                            mode: configuration.codecOptions.interleaveMode, near: 0, parameters: parameters,
                            bits: d.meaningfulBits, writer: &writer, checkpoint: { try budget.check() })
                    }
                    writer.flush()
                    return
                }
                let regular = near == 0 ? try JPEGLSRegularMode(parameters: parameters) : nil
                let run = near == 0 ? try JPEGLSRunMode(parameters: parameters) : nil
                let coding = kernel.computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: d.meaningfulBits)

                if effectiveWorkers > 1 {
                    let sharedInput = SendableRawBorrow(buffer: bytes)
                    let chunkStorage = ChunkOutputCollector(count: totalUnits)
                    let sampleBytes = d.storageBits / 8
                    let littleEndian = d.byteOrder == .littleEndian
                    let width = d.width
                    let height = d.height
                    let meaningfulBits = d.meaningfulBits
                    let chunkRows = interval > 0 ? interval : height
                    let chunkCap = max(256, min(outputLimit, (width * chunkRows * sampleBytes) / 2))
                    try BoundedParallelPool.forEach(count: totalUnits, workers: effectiveWorkers) { unit in
                        let component = unit / chunks
                        let chunk = unit % chunks
                        let location = locations[component]
                        let localView = ComponentSampleReader(
                            bytes: sharedInput.buffer, width: width, height: height,
                            offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                            sampleBytes: sampleBytes, littleEndian: littleEndian
                        )
                        let first = interval > 0 ? chunk * interval : 0
                        let last = interval > 0 ? first + min(interval, height - first) : height
                        let localKernel = JPEGLSScalarKernel()
                        var localWriter = JPEGLSBitstreamWriter(capacity: chunkCap, maximumBytes: outputLimit)
                        if near > 0 {
                            try localKernel.encodeNearLossless(
                                buf: localView.rows(first..<last), rowStride: width,
                                width: width, height: last - first, near: near, parameters: parameters,
                                writer: &localWriter, bits: meaningfulBits, checkpoint: { try budget.check() }
                            )
                        } else {
                            guard let regular, let run else {
                                throw CodecError(.internalFailure, "Lossless coding state is unavailable.")
                            }
                            var context = try JPEGLSContextModel(parameters: parameters)
                            try localKernel.encodeFlatRowsLossless(
                                buf: localView, rowStride: width, rowRange: first..<last,
                                sampleMaximum: sampleMaximum, width: width,
                                regularMode: regular, runMode: run, context: &context, writer: &localWriter,
                                limit: coding.limit, qbppBits: coding.qbppBits, checkpoint: { try budget.check() }
                            )
                        }
                        localWriter.flush()
                        chunkStorage.store(index: unit, bytes: try localWriter.consumeRawBytes())
                    }
                    let encodedChunks = chunkStorage.takeAll()
                    for component in 0..<views.count {
                        let scan = try JPEGLSScanHeader(componentCount: 1,
                            components: [.init(id: componentIDs[component], mappingTableID: metadata.mapping?.componentTableIDs[component] ?? 0)],
                            near: near, interleaveMode: .none, pointTransform: 0)
                        try kernel.writeScanHeaderInternal(scan, to: &writer)
                        for chunk in 0..<chunks {
                            writer.appendRawBytes(encodedChunks[component * chunks + chunk])
                            try writer.checkLimit()
                            if chunk + 1 < chunks { writer.writeByte(255); writer.writeByte(0xd0 + UInt8(chunk % 8)) }
                        }
                    }
                } else {
                    for (component, view) in views.enumerated() {
                        let scan = try JPEGLSScanHeader(componentCount: 1,
                            components: [.init(id: componentIDs[component], mappingTableID: metadata.mapping?.componentTableIDs[component] ?? 0)],
                            near: near, interleaveMode: .none, pointTransform: 0)
                        try kernel.writeScanHeaderInternal(scan, to: &writer)
                        for chunk in 0..<chunks {
                            let first = interval > 0 ? chunk * interval : 0
                            let last = interval > 0 ? first + min(interval, d.height - first) : d.height
                            if near > 0 {
                                try kernel.encodeNearLossless(buf: view.rows(first..<last), rowStride: d.width,
                                    width: d.width, height: last - first, near: near, parameters: parameters,
                                    writer: &writer, bits: d.meaningfulBits, checkpoint: { try budget.check() })
                            } else {
                                guard let regular, let run else {
                                    throw CodecError(.internalFailure, "Lossless coding state is unavailable.")
                                }
                                var context = try JPEGLSContextModel(parameters: parameters)
                                try kernel.encodeFlatRowsLossless(buf: view, rowStride: d.width, rowRange: first..<last,
                                    sampleMaximum: sampleMaximum, width: d.width,
                                    regularMode: regular, runMode: run, context: &context, writer: &writer,
                                    limit: coding.limit, qbppBits: coding.qbppBits, checkpoint: { try budget.check() })
                            }
                            writer.flush()
                            if chunk + 1 < chunks { writer.writeByte(255); writer.writeByte(0xd0 + UInt8(chunk % 8)) }
                        }
                    }
                }
            }
            writer.writeMarker(.endOfImage)
            let data = try writer.getData()
            options.progress?(try .init(phase: .completed, completedUnits: samples, totalUnits: samples))
            try budget.check()
            return EncodedImage(data: data, encoding: .init(format: "JPEG-LS", mode: configuration.mode),
                report: OperationReport(backend: resolvedBackend, fallbackReason: fallbackReason,
                    fidelity: near == 0 ? .exactSamples : .boundedError(near), pixelAllocationCount: 0,
                    peakPixelBytes: 0, peakWorkspaceBytes: nil, elapsedSeconds: budget.elapsedSeconds))
        }
    }
    static func decode(_ data: Data, header: JPEGLSHeader, into supplied: ImageDestination?, options: DecodeOptions,
                       budget: CodecBudget, hpInterpretation: CodecOptions.HPInterpretation,
                       resolvedBackend: Backend = .scalarCPU, fallbackReason: String? = nil) throws -> DecodedImage {
        let d = try supplied?.descriptor ?? header.descriptor(limits: budget.limits)
        let locations = try locations(d, limits: budget.limits)
        guard d.width == header.width, d.height == header.height, d.meaningfulBits == header.outputBits, d.storageBits >= header.bits,
              d.components == header.roles, d.colour == (header.rgb ? .rgb : .unknown) else {
            throw CodecError(.incompatibleImageLayout, "Destination geometry, precision or interpretation does not match the codestream.")
        }
        let hMax = header.sampling.reduce(1) { max($0, Int($1 >> 4)) }
        let vMax = header.sampling.reduce(1) { max($0, Int($1 & 15)) }
        let destinationHMax = locations.reduce(1) { max($0, $1.horizontal) }
        let destinationVMax = locations.reduce(1) { max($0, $1.vertical) }
        for (i, location) in locations.enumerated() {
            guard location.horizontal * hMax == Int(header.sampling[i] >> 4) * destinationHMax,
                  location.vertical * vMax == Int(header.sampling[i] & 15) * destinationVMax,
                  location.width == (header.width * Int(header.sampling[i] >> 4) + hMax - 1) / hMax,
                  location.height == (header.height * Int(header.sampling[i] & 15) + vMax - 1) / vMax else {
                throw CodecError(.incompatibleImageLayout, "Destination component sampling does not match the codestream.")
            }
        }
        let table = try header.records.reduce(0) { try max($0, ScalarCodec.tableBytes($1.parameters)) }
        let ranges = header.records.reduce(0) { $0 + $1.ranges.count }
        let baseWorkspace = try checkedAdd(checkedAdd(ScalarCodec.contextBytes, table),
            checkedAdd(checkedMultiply(data.count, 2), checkedMultiply(ranges, MemoryLayout<Range<Int>>.stride * 2)))
        let baseTotalWorkspace = try checkedAdd(baseWorkspace, checkedMultiply(header.metadataBytes, 32))
        let pixelBytes = supplied?.storage.byteCount ?? d.requiredByteCount

        let allNonInterleaved = header.records.allSatisfy { $0.interleave == .none && $0.components.count == 1 }
        let totalNonInterleavedUnits = allNonInterleaved ? ranges : 1
        var effectiveWorkers = (resolvedBackend == .accelerated && totalNonInterleavedUnits > 1)
            ? min(totalNonInterleavedUnits, BoundedParallelPool.workerCount(requested: budget.limits.maximumWorkers))
            : 1
        while effectiveWorkers > 1 {
            let extra = (effectiveWorkers - 1) * ScalarCodec.contextBytes
            let candidateWs = baseTotalWorkspace + extra
            if candidateWs <= budget.limits.maximumWorkspaceBytes,
               pixelBytes + candidateWs + data.count <= budget.limits.maximumMemoryBytes {
                break
            }
            effectiveWorkers -= 1
        }
        try budget.admit(pixelBytes: pixelBytes, workspaceBytes: baseTotalWorkspace + (effectiveWorkers - 1) * ScalarCodec.contextBytes, compressedBytes: data.count)
        let samples = try checkedMultiply(checkedMultiply(d.width, d.height), d.components.count)
        options.progress?(try .init(phase: .processing, completedUnits: 0, totalUnits: samples))
        try budget.check()
        let destination = try supplied ?? ImageDestination.allocate(descriptor: d, limits: budget.limits)
        let kernel = JPEGLSScalarKernel()
        let fidelity = try header.fidelity(budget: budget)
        let image = try destination.write(metadata: header.retainedMetadata(options.metadataPolicy)) { bytes in
            try data.withUnsafeBytes { compressedRaw in
                if allNonInterleaved && effectiveWorkers > 1 {
                    struct DecodeUnit: Sendable {
                        let scanIndex: Int
                        let chunkIndex: Int
                        let range: Range<Int>
                    }
                    var units: [DecodeUnit] = []
                    units.reserveCapacity(totalNonInterleavedUnits)
                    var scanDecoders: [(regular: JPEGLSRegularModeDecoder, run: JPEGLSRunModeDecoder, limit: Int, qbppBits: Int)] = []
                    scanDecoders.reserveCapacity(header.records.count)
                    for (sIdx, scan) in header.records.enumerated() {
                        let regDec = try JPEGLSRegularModeDecoder(parameters: scan.parameters, near: scan.near)
                        let runDec = try JPEGLSRunModeDecoder(parameters: scan.parameters, near: scan.near)
                        let coding = kernel.computeGolombLimitInternal(parameters: scan.parameters, near: scan.near, bitsPerSample: header.bits)
                        scanDecoders.append((regDec, runDec, coding.limit, coding.qbppBits))
                        for (cIdx, r) in scan.ranges.enumerated() {
                            units.append(DecodeUnit(scanIndex: sIdx, chunkIndex: cIdx, range: r))
                        }
                    }
                    let immutableUnits = units
                    let immutableDecoders = scanDecoders
                    let records = header.records
                    let sharedCompressed = SendableRawBorrow(buffer: compressedRaw)
                    let sharedOutput = SendableMutableRawBorrow(buffer: bytes)
                    let sampleBytes = d.storageBits / 8
                    let littleEndian = d.byteOrder == .littleEndian
                    let width = d.width
                    let height = d.height
                    try BoundedParallelPool.forEach(count: immutableUnits.count, workers: effectiveWorkers) { uIdx in
                        let unit = immutableUnits[uIdx]
                        let scan = records[unit.scanIndex]
                        let dec = immutableDecoders[unit.scanIndex]
                        let location = locations[scan.components[0]]
                        let whole = ComponentSampleWriter(
                            bytes: sharedOutput.buffer, width: width, height: height,
                            offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                            sampleBytes: sampleBytes, littleEndian: littleEndian
                        )
                        let first = scan.restartInterval > 0 ? unit.chunkIndex * scan.restartInterval : 0
                        let last = scan.restartInterval > 0 ? first + min(scan.restartInterval, height - first) : height
                        var reader = JPEGLSFastBitReader(borrowing: .init(rebasing: sharedCompressed.buffer[unit.range]))
                        let region = whole.rows(first..<last)
                        let localKernel = JPEGLSScalarKernel()
                        if region.pixelStride == region.sampleBytes && region.rowBytes % region.sampleBytes == 0 {
                            let scalar = ScalarSampleWriter(
                                bytes: .init(rebasing: region.bytes[region.offset...]),
                                littleEndian: region.littleEndian, sampleBytes: region.sampleBytes
                            )
                            try localKernel.decodeFlatRegion(
                                into: scalar, rowStride: region.rowBytes / region.sampleBytes, reader: &reader,
                                rows: last - first, width: width, parameters: scan.parameters, near: scan.near,
                                limit: dec.limit, qbppBits: dec.qbppBits,
                                sharedDecoder: dec.regular, sharedRunDecoder: dec.run,
                                checkpoint: { try budget.check() }
                            )
                        } else {
                            try localKernel.decodeFlatRegion(
                                into: region, rowStride: width, reader: &reader,
                                rows: last - first, width: width, parameters: scan.parameters, near: scan.near,
                                limit: dec.limit, qbppBits: dec.qbppBits,
                                sharedDecoder: dec.regular, sharedRunDecoder: dec.run,
                                checkpoint: { try budget.check() }
                            )
                        }
                        try reader.validateEndOfScan()
                    }
                } else {
                    for scan in header.records {
                        if scan.interleave != .none {
                            let views = scan.components.map { c in
                                let location = locations[c]
                                return ComponentSampleWriter(bytes: bytes, width: location.width, height: location.height,
                                    offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                                    sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                            }
                            let range = scan.ranges[0]
                            var reader = JPEGLSFastBitReader(borrowing: .init(rebasing: compressedRaw[range]))
                            try kernel.decodeInterleaved(views: views, width: d.width, height: d.height,
                                mode: scan.interleave, near: scan.near, parameters: scan.parameters,
                                bits: header.bits, reader: &reader, verticalSampling: scan.components.map { Int(header.sampling[$0] & 15) }, checkpoint: { try budget.check() })
                            try reader.validateEndOfScan()
                            continue
                        }
                        let location = locations[scan.components[0]]
                        let whole = ComponentSampleWriter(bytes: bytes, width: d.width, height: d.height,
                            offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                            sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                        let coding = kernel.computeGolombLimitInternal(parameters: scan.parameters, near: scan.near, bitsPerSample: header.bits)
                        let sharedDecoder = try JPEGLSRegularModeDecoder(parameters: scan.parameters, near: scan.near)
                        let sharedRunDecoder = try JPEGLSRunModeDecoder(parameters: scan.parameters, near: scan.near)
                        for (chunk, range) in scan.ranges.enumerated() {
                            let first = scan.restartInterval > 0 ? chunk * scan.restartInterval : 0
                            let last = scan.restartInterval > 0 ? first + min(scan.restartInterval, d.height - first) : d.height
                            var reader = JPEGLSFastBitReader(borrowing: .init(rebasing: compressedRaw[range]))
                            let region = whole.rows(first..<last)
                            if region.pixelStride == region.sampleBytes && region.rowBytes % region.sampleBytes == 0 {
                                let scalar = ScalarSampleWriter(bytes: .init(rebasing: region.bytes[region.offset...]),
                                    littleEndian: region.littleEndian, sampleBytes: region.sampleBytes)
                                try kernel.decodeFlatRegion(into: scalar, rowStride: region.rowBytes / region.sampleBytes, reader: &reader,
                                    rows: last - first, width: d.width, parameters: scan.parameters, near: scan.near,
                                    limit: coding.limit, qbppBits: coding.qbppBits,
                                    sharedDecoder: sharedDecoder, sharedRunDecoder: sharedRunDecoder,
                                    checkpoint: { try budget.check() })
                            } else {
                                try kernel.decodeFlatRegion(into: region, rowStride: d.width, reader: &reader,
                                    rows: last - first, width: d.width, parameters: scan.parameters, near: scan.near,
                                    limit: coding.limit, qbppBits: coding.qbppBits,
                                    sharedDecoder: sharedDecoder, sharedRunDecoder: sharedRunDecoder,
                                    checkpoint: { try budget.check() })
                            }
                            try reader.validateEndOfScan()
                        }
                    }
                }
            }
            if header.colourTransform != .none {
                let views = locations.map { location in
                    ComponentSampleWriter(bytes: bytes, width: d.width, height: d.height,
                        offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                        sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                }
                let mappingTables: [JPEGLSMappingTable?] = (0..<3).map { component in
                    guard header.mapsSamples, let mapping = header.mapping else { return nil }
                    return mapping.tables.first { $0.id == mapping.componentTableIDs[component] }
                }
                // Prediction is complete. Invert in the final caller allocation,
                // before sealing; no transformed frame or repack is allocated.
                for i in 0..<(d.width * d.height) {
                    if i & 63 == 0 { try budget.check() }
                    func value(_ component: Int) -> Int {
                        let sample = Int(views[component][i])
                        return mappingTables[component].map { Int($0.sample(sample)) } ?? sample
                    }
                    let rgb = HPTransform.inverse(value(0), value(1), value(2),
                        transform: header.colourTransform, bits: header.bits, interpretation: hpInterpretation)
                    views[0][i] = UInt16(rgb.0); views[1][i] = UInt16(rgb.1); views[2][i] = UInt16(rgb.2)
                }
            }
            if header.colourTransform == .none { try header.mapSamples(in: bytes, descriptor: d, budget: budget) }
            try budget.check()
        }
        options.progress?(try .init(phase: .completed, completedUnits: samples, totalUnits: samples))
        try budget.check()
        return DecodedImage(image: image, report: OperationReport(backend: resolvedBackend,
            fallbackReason: fallbackReason, fidelity: fidelity,
            pixelAllocationCount: supplied == nil ? 1 : 0, peakPixelBytes: supplied == nil ? pixelBytes : 0,
            peakWorkspaceBytes: nil, elapsedSeconds: budget.elapsedSeconds))
    }
}
