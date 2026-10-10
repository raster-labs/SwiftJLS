// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

/// The common API boundary owns admission, lifetime, errors and publication.
/// Kernels operate only on synchronous views of the retained image owners.
enum ScalarCodec {
    static let contextBytes = 64 * 1024 // conservative fixed context/state allowance
    static func tableBytes(_ parameters: JPEGLSPresetParameters) throws -> Int {
        // One gradient table is live per direction; allow another during construction.
        try checkedMultiply(checkedAdd(checkedMultiply(parameters.threshold3, 2), 1), MemoryLayout<Int>.stride * 2)
    }
    static let capabilities = CodecCapabilities(formats: ["JPEG-LS"], compressionModes: [.lossless] + (1...255).map { .nearLossless(maximumAbsoluteError: $0) },
        sampleTypes: [.unsignedInteger], meaningfulPrecision: 2...16,
        layouts: ["greyscale8", "greyscale16", "components8", "components16"], availableBackends: [.scalarCPU],
        canInspect: true, canEncode: true, canDecode: true)

    static func layout(_ descriptor: ImageDescriptor, limits: ResourceLimits) throws -> PlaneDescriptor {
        try descriptor.validate(limits: limits)
        guard descriptor.sampleType == .unsignedInteger, (descriptor.storageBits == 8 || descriptor.storageBits == 16),
              (2...16).contains(descriptor.meaningfulBits), descriptor.planes.count == 1,
              descriptor.components == [.grey], descriptor.colour == .greyscale,
              descriptor.alpha == .absent, descriptor.iccProfile == nil,
              descriptor.width <= Int(UInt32.max), descriptor.height <= Int(UInt32.max) else {
            throw CodecError(.unsupportedFeature, "The migrated scalar profile requires unsigned greyscale without ICC metadata.")
        }
        let plane = descriptor.planes[0]
        guard plane.pixelStride == descriptor.storageBits / 8, plane.sampleStride == descriptor.storageBits / 8 else {
            throw CodecError(.incompatibleImageLayout, "Scalar sample and pixel strides must match their storage width.")
        }
        return plane
    }
    static func fallback(_ policy: ExecutionPolicy) -> String? {
        if case .preferred(.accelerated) = policy { return "Acceleration unavailable; scalar CPU selected." }
        return nil
    }
    static func mapped<R>(_ body: () throws -> R) throws -> R {
        do { return try body() }
        catch is JPEGLSError { throw CodecError(.malformedInput, "Invalid JPEG-LS coding data.") }
    }
    static func inspect(_ data: Data, options: DecodeOptions, codecOptions: CodecOptions = .init()) throws -> ImageInfo {
        let budget = CodecBudget(limits: options.resourceLimits)
        return try mapped {
            let header = try JPEGLSHeader.parse(data, budget: budget, codecOptions: codecOptions)
            let descriptor = try header.descriptor(limits: options.resourceLimits)
            try budget.check()
            return ImageInfo(format: "JPEG-LS", descriptor: descriptor, frameCount: 1, metadata: header.retainedMetadata(options.metadataPolicy))
        }
    }
    static func encode(_ image: Image, configuration: EncoderConfiguration, options: EncodeOptions) throws -> EncodedImage {
        let budget = CodecBudget(limits: options.resourceLimits)
        return try mapped {
            let descriptor = image.descriptor
            let plane = try layout(descriptor, limits: budget.limits)
            guard configuration.codecOptions.interleaveMode == .none, configuration.codecOptions.colourTransform == .none else {
                throw CodecError(.unsupportedFeature, "Greyscale requires non-interleaved coding.")
            }
            let metadata = try JPEGMetadataEncoding(image, options: options)
            let near: Int
            if case .nearLossless(let bound) = configuration.mode { near = bound } else { near = 0 }
            guard near <= min(255, ((1 << descriptor.meaningfulBits) - 1) / 2) else {
                throw CodecError(.invalidArgument, "NEAR exceeds the maximum for this sample precision.")
            }
            let parameters: JPEGLSPresetParameters
            if let preset = configuration.codecOptions.preset {
                guard preset.maximumSampleValue <= (1 << descriptor.meaningfulBits) - 1,
                      near <= min(255, preset.maximumSampleValue / 2), preset.threshold1 > near else {
                    throw CodecError(.invalidArgument, "Preset parameters are incompatible with precision or NEAR.")
                }
                parameters = try JPEGLSPresetParameters(maxValue: preset.maximumSampleValue,
                    threshold1: preset.threshold1, threshold2: preset.threshold2,
                    threshold3: preset.threshold3, reset: preset.reset)
            } else {
                parameters = try JPEGLSPresetParameters.defaultParameters(bitsPerSample: descriptor.meaningfulBits, near: near)
            }
            try metadata.mapping?.validate(components: 1, maximum: parameters.maxValue)
            let samples = try checkedMultiply(descriptor.width, descriptor.height)
            // Limited Golomb words are at most 64 bits per sample, with stuffing
            // and marker allowance. Account for both the writer and final Data.
            let interval = configuration.codecOptions.restartIntervalLines
            let chunks = interval > 0 ? (descriptor.height + interval - 1) / interval : 1
            let worstOutput = try checkedAdd(checkedAdd(checkedMultiply(samples, 10), checkedAdd(64, metadata.byteCount)), checkedMultiply(chunks, 4))
            let outputLimit = min(worstOutput, budget.limits.maximumCompressedBytes)
            let workspace = try checkedAdd(checkedAdd(contextBytes, tableBytes(parameters)), checkedAdd(checkedMultiply(outputLimit, 2), near > 0 ? checkedMultiply(descriptor.width, 4) : 0))
            try budget.admit(pixelBytes: image.storage.byteCount, workspaceBytes: checkedAdd(workspace, checkedMultiply(metadata.byteCount, 32)), compressedBytes: outputLimit)
            options.progress?(try ProgressUpdate(phase: .processing, completedUnits: 0, totalUnits: samples))
            try budget.check()
            let writer = JPEGLSBitstreamWriter(capacity: min(outputLimit, 4096), maximumBytes: outputLimit)
            let kernel = JPEGLSScalarKernel()
            let frame = try JPEGLSFrameHeader(bitsPerSample: descriptor.meaningfulBits,
                height: descriptor.height, width: descriptor.width, componentCount: 1,
                components: [.init(id: 1)])
            let scan = try JPEGLSScanHeader(componentCount: 1, components: [.init(id: 1, mappingTableID: metadata.mapping?.componentTableIDs[0] ?? 0)],
                near: near, interleaveMode: .none, pointTransform: 0)
            writer.writeMarker(.startOfImage)
            try metadata.writeSPIFF(to: writer)
            try metadata.ancillary.write(to: writer)
            try kernel.writeFrameHeaderInternal(frame, to: writer)
            if configuration.codecOptions.preset != nil {
                writer.writeMarker(.jpegLSExtension)
                writer.writeUInt16(13)
                writer.writeByte(1)
                for value in [parameters.maxValue, parameters.threshold1, parameters.threshold2, parameters.threshold3, parameters.reset] {
                    writer.writeUInt16(UInt16(value))
                }
            }
            if interval > 0 {
                writer.writeMarker(.defineRestartInterval)
                writer.writeUInt16(4)
                writer.writeUInt16(UInt16(interval))
            }
            try metadata.mapping?.write(to: writer, budget: budget)
            try kernel.writeScanHeaderInternal(scan, to: writer)
            try image.storage.withUnsafeBytes { bytes in
                guard bytes.count == image.storage.byteCount, bytes.count >= descriptor.requiredByteCount else {
                    throw CodecError(.storageUnavailable, "Input provider changed its capacity.")
                }
                let view = ScalarSampleReader(bytes: .init(rebasing: bytes[plane.offset..<descriptor.requiredByteCount]),
                    littleEndian: descriptor.byteOrder == .littleEndian, sampleBytes: descriptor.storageBits / 8)
                try view.validate(width: descriptor.width, height: descriptor.height,
                    rowStride: plane.rowBytes / view.sampleBytes, maximum: parameters.maxValue,
                    checkpoint: { try budget.check() })
                let regular = try JPEGLSRegularMode(parameters: parameters)
                let run = try JPEGLSRunMode(parameters: parameters)
                let coding = kernel.computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: descriptor.meaningfulBits)
                for chunk in 0..<chunks {
                    let first = interval > 0 ? chunk * interval : 0
                    let last = interval > 0 ? min(first + interval, descriptor.height) : descriptor.height
                    if near > 0 {
                        let rowView = ScalarSampleReader(bytes: .init(rebasing: view.bytes[(first * plane.rowBytes)...]),
                            littleEndian: view.littleEndian, sampleBytes: view.sampleBytes)
                        try kernel.encodeNearLossless(buf: rowView, rowStride: plane.rowBytes / view.sampleBytes,
                            width: descriptor.width, height: last - first, near: near,
                            parameters: parameters, writer: writer, bits: descriptor.meaningfulBits,
                            checkpoint: { try budget.check(); try writer.checkLimit() })
                    } else {
                        var context = try JPEGLSContextModel(parameters: parameters)
                        try kernel.encodeFlatRowsLossless(buf: view, rowStride: plane.rowBytes / view.sampleBytes,
                            rowRange: first..<last, width: descriptor.width, regularMode: regular,
                            runMode: run, context: &context, writer: writer, limit: coding.limit,
                            qbppBits: coding.qbppBits, checkpoint: { try budget.check(); try writer.checkLimit() })
                    }
                    if chunk + 1 < chunks {
                        writer.flush()
                        guard let marker = JPEGLSMarker(rawValue: 0xd0 + UInt8(chunk % 8)) else {
                            throw CodecError(.internalFailure, "Restart marker unavailable.")
                        }
                        writer.writeMarker(marker)
                    }
                }
            }
            writer.flush(); writer.writeMarker(.endOfImage)
            let data = try writer.getData()
            try budget.check()
            let result = EncodedImage(data: data, encoding: .init(format: "JPEG-LS", mode: configuration.mode),
                report: OperationReport(backend: .scalarCPU, fallbackReason: fallback(options.executionPolicy),
                    fidelity: near == 0 ? .exactSamples : .boundedError(near), pixelAllocationCount: 0, peakPixelBytes: 0,
                    peakWorkspaceBytes: nil, elapsedSeconds: ProcessInfo.processInfo.systemUptime - budget.started))
            options.progress?(try ProgressUpdate(phase: .completed, completedUnits: samples, totalUnits: samples))
            try budget.check()
            return result
        }
    }
    static func decode(_ data: Data, into supplied: ImageDestination?, options: DecodeOptions,
                       codecOptions: CodecOptions = .init()) throws -> DecodedImage {
        let budget = CodecBudget(limits: options.resourceLimits)
        return try mapped {
            let header = try JPEGLSHeader.parse(data, budget: budget, codecOptions: codecOptions)
            if !header.grey {
                return try ComponentCodec.decode(data, header: header, into: supplied, options: options, budget: budget, hpInterpretation: codecOptions.hpInterpretation)
            }
            let descriptor = try supplied?.descriptor ?? header.descriptor(limits: budget.limits)
            let plane = try layout(descriptor, limits: budget.limits)
            guard descriptor.width == header.width, descriptor.height == header.height,
                  descriptor.meaningfulBits == header.outputBits, descriptor.storageBits >= header.bits else {
                throw CodecError(.incompatibleImageLayout, "Destination geometry or precision does not match the codestream.")
            }
            let workspace = try checkedAdd(checkedAdd(contextBytes, tableBytes(header.parameters)), checkedAdd(checkedMultiply(data.count, 2), checkedMultiply(header.scans.count, MemoryLayout<Range<Int>>.stride * 2)))
            let pixelBytes = supplied?.storage.byteCount ?? descriptor.requiredByteCount
            try budget.admit(pixelBytes: pixelBytes, workspaceBytes: checkedAdd(workspace, checkedMultiply(header.metadataBytes, 32)), compressedBytes: data.count)
            let samples = try checkedMultiply(header.width, header.height)
            options.progress?(try ProgressUpdate(phase: .processing, completedUnits: 0, totalUnits: samples))
            try budget.check()
            let destination = try supplied ?? ImageDestination.allocate(descriptor: descriptor, limits: budget.limits)
            let kernel = JPEGLSScalarKernel()
            let coding = kernel.computeGolombLimitInternal(parameters: header.parameters, near: header.near, bitsPerSample: header.bits)
            let fidelity = try header.fidelity(budget: budget)
            let image = try destination.write(metadata: header.retainedMetadata(options.metadataPolicy)) { bytes in
                for (chunk, scan) in header.scans.enumerated() {
                    let firstRow = header.restartInterval > 0 ? chunk * header.restartInterval : 0
                    let rows = header.restartInterval > 0 ? min(header.restartInterval, header.height - firstRow) : header.height
                    let offset = plane.offset + firstRow * plane.rowBytes
                    let view = ScalarSampleWriter(bytes: .init(rebasing: bytes[offset..<descriptor.requiredByteCount]),
                        littleEndian: descriptor.byteOrder == .littleEndian, sampleBytes: descriptor.storageBits / 8)
                    let start = data.index(data.startIndex, offsetBy: scan.lowerBound)
                    let end = data.index(data.startIndex, offsetBy: scan.upperBound)
                    let reader = JPEGLSBitstreamReader(data: data[start..<end])
                    try kernel.decodeFlatRegion(into: view, rowStride: plane.rowBytes / (descriptor.storageBits / 8), reader: reader,
                        rows: rows, width: header.width, parameters: header.parameters, near: header.near,
                        limit: coding.limit, qbppBits: coding.qbppBits, checkpoint: { try budget.check() })
                    try reader.validateEndOfScan()
                }
                try header.mapSamples(in: bytes, descriptor: descriptor, budget: budget)
                try budget.check()
            }
            let result = DecodedImage(image: image, report: OperationReport(backend: .scalarCPU,
                fallbackReason: fallback(options.executionPolicy), fidelity: fidelity,
                pixelAllocationCount: supplied == nil ? 1 : 0, peakPixelBytes: supplied == nil ? pixelBytes : 0,
                peakWorkspaceBytes: nil, elapsedSeconds: ProcessInfo.processInfo.systemUptime - budget.started))
            options.progress?(try ProgressUpdate(phase: .completed, completedUnits: samples, totalUnits: samples))
            try budget.check()
            return result
        }
    }
}
