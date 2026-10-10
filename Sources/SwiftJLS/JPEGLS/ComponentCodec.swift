// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

/// Non-interleaved component scans share the scalar entropy kernels and borrow
/// each component directly through its descriptor. No planarisation is needed.
enum ComponentCodec {
    struct Location {
        let offset: Int, rowBytes: Int, pixelStride: Int
    }
    static func locations(_ descriptor: ImageDescriptor, limits: ResourceLimits) throws -> [Location] {
        try descriptor.validate(limits: limits)
        guard descriptor.sampleType == .unsignedInteger, [8, 16].contains(descriptor.storageBits),
              (2...16).contains(descriptor.meaningfulBits), (2...4).contains(descriptor.components.count),
              descriptor.alpha == .absent, descriptor.iccProfile == nil,
              descriptor.width <= 65535, descriptor.height <= 65535 else {
            throw CodecError(.unsupportedFeature, "Component coding requires two to four unsigned, unsubsampled components without alpha or ICC.")
        }
        return try descriptor.components.indices.map { component in
            for plane in descriptor.planes {
                if let index = plane.components.firstIndex(of: component) {
                    return Location(offset: plane.offset + index * plane.sampleStride,
                        rowBytes: plane.rowBytes, pixelStride: plane.pixelStride)
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
    static func writeRGBHeader(width: Int, height: Int, bits: Int, writer: JPEGLSBitstreamWriter) {
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
        let budget = CodecBudget(limits: options.resourceLimits)
        return try ScalarCodec.mapped {
            let d = image.descriptor
            let locations = try locations(d, limits: budget.limits)
            let componentIDs = try ids(d)
            let transform = configuration.codecOptions.colourTransform
            guard transform == .none || (d.colour == .rgb && [8, 16].contains(d.meaningfulBits)) else {
                throw CodecError(.unsupportedFeature, "HP transforms require RGB with 8 or 16 meaningful bits.")
            }
            guard image.metadata.requiredKeys.isEmpty,
                  image.metadata.entries.isEmpty || options.metadataPolicy == .discardAncillary else {
                throw CodecError(.unsupportedFeature, "Component metadata preservation is not implemented.")
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
            let interval = configuration.codecOptions.restartIntervalLines
            let chunks = interval > 0 ? (d.height + interval - 1) / interval : 1
            let samples = try checkedMultiply(checkedMultiply(d.width, d.height), componentIDs.count)
            let worstOutput = try checkedAdd(checkedMultiply(samples, 10), checkedAdd(256, checkedMultiply(chunks, componentIDs.count * 4)))
            let outputLimit = min(worstOutput, budget.limits.maximumCompressedBytes)
            let predictorBytes = configuration.codecOptions.interleaveMode == .none
                ? (near > 0 ? try checkedMultiply(d.width, 4) : 0)
                : try checkedMultiply(d.width, componentIDs.count * 4)
            let workspace = try checkedAdd(checkedAdd(ScalarCodec.contextBytes, ScalarCodec.tableBytes(parameters)),
                checkedAdd(checkedMultiply(outputLimit, 2), predictorBytes))
            try budget.admit(pixelBytes: image.storage.byteCount, workspaceBytes: workspace, compressedBytes: outputLimit)
            if budget.limits.maximumMetadataBytes < (d.colour == .rgb ? 30 : 0) + (transform == .none ? 0 : 5) {
                throw CodecError(.resourceLimitExceeded, "SPIFF header exceeds the metadata budget.")
            }
            options.progress?(try .init(phase: .processing, completedUnits: 0, totalUnits: samples))
            try budget.check()
            let writer = JPEGLSBitstreamWriter(capacity: min(outputLimit, 4096), maximumBytes: outputLimit)
            let kernel = JPEGLSScalarKernel()
            writer.writeMarker(.startOfImage)
            if d.colour == .rgb { writeRGBHeader(width: d.width, height: d.height, bits: d.meaningfulBits, writer: writer) }
            if transform != .none {
                writer.writeByte(255); writer.writeByte(0xe8); writer.writeUInt16(7)
                for byte: UInt8 in [109, 114, 102, 120, transform.rawValue] { writer.writeByte(byte) }
            }
            let frame = try JPEGLSFrameHeader(bitsPerSample: d.meaningfulBits, height: d.height,
                width: d.width, componentCount: componentIDs.count, components: componentIDs.map { .init(id: $0) })
            try kernel.writeFrameHeaderInternal(frame, to: writer)
            if configuration.codecOptions.preset != nil {
                writer.writeMarker(.jpegLSExtension); writer.writeUInt16(13); writer.writeByte(1)
                for value in [parameters.maxValue, parameters.threshold1, parameters.threshold2, parameters.threshold3, parameters.reset] {
                    writer.writeUInt16(UInt16(value))
                }
            }
            if interval > 0 {
                writer.writeMarker(.defineRestartInterval); writer.writeUInt16(4); writer.writeUInt16(UInt16(interval))
            }
            try image.storage.withUnsafeBytes { bytes in
                guard bytes.count == image.storage.byteCount, bytes.count >= d.requiredByteCount else {
                    throw CodecError(.storageUnavailable, "Provider returned inconsistent storage.")
                }
                let views = locations.map { location in
                    ComponentSampleReader(bytes: bytes, width: d.width, height: d.height,
                        offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                        sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                }
                for view in views {
                    for index in 0..<view.count {
                        if index & 255 == 0 { try budget.check() }
                        guard view[index] <= parameters.maxValue else { throw CodecError(.invalidArgument, "Sample exceeds declared precision.") }
                    }
                }
                if configuration.codecOptions.interleaveMode != .none {
                    guard let mode = JPEGLSInterleaveMode(rawValue: configuration.codecOptions.interleaveMode.rawValue) else {
                        throw CodecError(.internalFailure, "Interleave mapping failed.")
                    }
                    let scan = try JPEGLSScanHeader(componentCount: componentIDs.count,
                        components: componentIDs.map { .init(id: $0, mappingTableID: 0) },
                        near: near, interleaveMode: mode, pointTransform: 0)
                    try kernel.writeScanHeaderInternal(scan, to: writer)
                    if transform == .none {
                        try kernel.encodeInterleaved(views: views, width: d.width, height: d.height,
                        mode: configuration.codecOptions.interleaveMode, near: near, parameters: parameters,
                        bits: d.meaningfulBits, writer: writer, checkpoint: { try budget.check(); try writer.checkLimit() })
                    } else {
                        let transformed = (0..<3).map { component in
                            HPComponentReader(views: views, component: component, transform: transform, bits: d.meaningfulBits)
                        }
                        try kernel.encodeInterleaved(views: transformed, width: d.width, height: d.height,
                            mode: configuration.codecOptions.interleaveMode, near: 0, parameters: parameters,
                            bits: d.meaningfulBits, writer: writer, checkpoint: { try budget.check(); try writer.checkLimit() })
                    }
                    writer.flush()
                    return
                }
                for (component, view) in views.enumerated() {
                    let scan = try JPEGLSScanHeader(componentCount: 1,
                        components: [.init(id: componentIDs[component], mappingTableID: 0)],
                        near: near, interleaveMode: .none, pointTransform: 0)
                    try kernel.writeScanHeaderInternal(scan, to: writer)
                    let coding = kernel.computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: d.meaningfulBits)
                    for chunk in 0..<chunks {
                        let first = interval > 0 ? chunk * interval : 0
                        let last = interval > 0 ? min(first + interval, d.height) : d.height
                        if near > 0 {
                            try kernel.encodeNearLossless(buf: view.rows(first..<last), rowStride: d.width,
                                width: d.width, height: last - first, near: near, parameters: parameters,
                                writer: writer, bits: d.meaningfulBits, checkpoint: { try budget.check(); try writer.checkLimit() })
                        } else {
                            let regular = try JPEGLSRegularMode(parameters: parameters)
                            let run = try JPEGLSRunMode(parameters: parameters)
                            var context = try JPEGLSContextModel(parameters: parameters)
                            try kernel.encodeFlatRowsLossless(buf: view, rowStride: d.width, rowRange: first..<last,
                                width: d.width, regularMode: regular, runMode: run, context: &context, writer: writer,
                                limit: coding.limit, qbppBits: coding.qbppBits, checkpoint: { try budget.check(); try writer.checkLimit() })
                        }
                        writer.flush()
                        if chunk + 1 < chunks { writer.writeByte(255); writer.writeByte(0xd0 + UInt8(chunk % 8)) }
                    }
                }
            }
            writer.writeMarker(.endOfImage)
            let data = try writer.getData()
            options.progress?(try .init(phase: .completed, completedUnits: samples, totalUnits: samples))
            try budget.check()
            return EncodedImage(data: data, encoding: .init(format: "JPEG-LS", mode: configuration.mode),
                report: OperationReport(backend: .scalarCPU, fallbackReason: ScalarCodec.fallback(options.executionPolicy),
                    fidelity: near == 0 ? .exactSamples : .boundedError(near), pixelAllocationCount: 0,
                    peakPixelBytes: 0, peakWorkspaceBytes: nil, elapsedSeconds: ProcessInfo.processInfo.systemUptime - budget.started))
        }
    }
    static func decode(_ data: Data, header: JPEGLSHeader, into supplied: ImageDestination?, options: DecodeOptions,
                       budget: CodecBudget) throws -> DecodedImage {
        let d = try supplied?.descriptor ?? header.descriptor(limits: budget.limits)
        let locations = try locations(d, limits: budget.limits)
        guard d.width == header.width, d.height == header.height, d.meaningfulBits == header.bits,
              d.components == header.roles, d.colour == (header.rgb ? .rgb : .unknown) else {
            throw CodecError(.incompatibleImageLayout, "Destination geometry, precision or interpretation does not match the codestream.")
        }
        let table = try header.records.map { try ScalarCodec.tableBytes($0.parameters) }.max() ?? 0
        let ranges = header.records.reduce(0) { $0 + $1.ranges.count }
        let workspace = try checkedAdd(checkedAdd(ScalarCodec.contextBytes, table),
            checkedAdd(checkedMultiply(data.count, 2), checkedMultiply(ranges, MemoryLayout<Range<Int>>.stride * 2)))
        let pixelBytes = supplied?.storage.byteCount ?? d.requiredByteCount
        try budget.admit(pixelBytes: pixelBytes, workspaceBytes: workspace, compressedBytes: data.count)
        let samples = try checkedMultiply(checkedMultiply(d.width, d.height), d.components.count)
        options.progress?(try .init(phase: .processing, completedUnits: 0, totalUnits: samples))
        try budget.check()
        let destination = try supplied ?? ImageDestination.allocate(descriptor: d, limits: budget.limits)
        let kernel = JPEGLSScalarKernel()
        let image = try destination.write { bytes in
            for scan in header.records {
                if scan.interleave != .none {
                    let views = scan.components.map { c in
                        let location = locations[c]
                        return ComponentSampleWriter(bytes: bytes, width: d.width, height: d.height,
                            offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                            sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                    }
                    let range = scan.ranges[0]
                    let start = data.index(data.startIndex, offsetBy: range.lowerBound)
                    let end = data.index(data.startIndex, offsetBy: range.upperBound)
                    let reader = JPEGLSBitstreamReader(data: data[start..<end])
                    try kernel.decodeInterleaved(views: views, width: d.width, height: d.height,
                        mode: scan.interleave, near: scan.near, parameters: scan.parameters,
                        bits: d.meaningfulBits, reader: reader, checkpoint: { try budget.check() })
                    try reader.validateEndOfScan()
                    continue
                }
                let location = locations[scan.components[0]]
                let whole = ComponentSampleWriter(bytes: bytes, width: d.width, height: d.height,
                    offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                    sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                let coding = kernel.computeGolombLimitInternal(parameters: scan.parameters, near: scan.near, bitsPerSample: d.meaningfulBits)
                for (chunk, range) in scan.ranges.enumerated() {
                    let first = scan.restartInterval > 0 ? chunk * scan.restartInterval : 0
                    let last = scan.restartInterval > 0 ? min(first + scan.restartInterval, d.height) : d.height
                    let start = data.index(data.startIndex, offsetBy: range.lowerBound)
                    let end = data.index(data.startIndex, offsetBy: range.upperBound)
                    let reader = JPEGLSBitstreamReader(data: data[start..<end])
                    try kernel.decodeFlatRegion(into: whole.rows(first..<last), rowStride: d.width, reader: reader,
                        rows: last - first, width: d.width, parameters: scan.parameters, near: scan.near,
                        limit: coding.limit, qbppBits: coding.qbppBits, checkpoint: { try budget.check() })
                    try reader.validateEndOfScan()
                }
            }
            if header.colourTransform != .none {
                let views = locations.map { location in
                    ComponentSampleWriter(bytes: bytes, width: d.width, height: d.height,
                        offset: location.offset, rowBytes: location.rowBytes, pixelStride: location.pixelStride,
                        sampleBytes: d.storageBits / 8, littleEndian: d.byteOrder == .littleEndian)
                }
                // Prediction is complete. Invert in the final caller allocation,
                // before sealing; no transformed frame or repack is allocated.
                for i in 0..<(d.width * d.height) {
                    if i & 63 == 0 { try budget.check() }
                    let rgb = HPTransform.inverse(Int(views[0][i]), Int(views[1][i]), Int(views[2][i]),
                        transform: header.colourTransform, bits: d.meaningfulBits)
                    views[0][i] = UInt16(rgb.0); views[1][i] = UInt16(rgb.1); views[2][i] = UInt16(rgb.2)
                }
            }
            try budget.check()
        }
        options.progress?(try .init(phase: .completed, completedUnits: samples, totalUnits: samples))
        try budget.check()
        return DecodedImage(image: image, report: OperationReport(backend: .scalarCPU,
            fallbackReason: ScalarCodec.fallback(options.executionPolicy), fidelity: header.near == 0 ? .exactSamples : .boundedError(header.near),
            pixelAllocationCount: supplied == nil ? 1 : 0, peakPixelBytes: supplied == nil ? pixelBytes : 0,
            peakWorkspaceBytes: nil, elapsedSeconds: ProcessInfo.processInfo.systemUptime - budget.started))
    }
}
