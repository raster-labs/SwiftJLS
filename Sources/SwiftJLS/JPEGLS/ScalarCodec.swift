// SPDX-License-Identifier: MIT
// Copyright 2026 Raster Images Private Limited
import Foundation

internal struct SendableRawBorrow: @unchecked Sendable {
    let buffer: UnsafeRawBufferPointer
}

internal struct SendableMutableRawBorrow: @unchecked Sendable {
    let buffer: UnsafeMutableRawBufferPointer
}

/// The common API boundary owns admission, lifetime, errors and publication.
/// Kernels operate only on synchronous views of the retained image owners.
enum ScalarCodec {
    static let contextBytes = CodecWorkspace.fixedControlBytes
    static func tableBytes(_ parameters: JPEGLSPresetParameters) throws -> Int {
        try CodecWorkspace.tableConstructionBytes(threshold3: parameters.threshold3)
    }
    static let capabilities = CodecCapabilities(formats: ["JPEG-LS"], compressionModes: [.lossless] + (1...255).map { .nearLossless(maximumAbsoluteError: $0) },
        sampleTypes: [.unsignedInteger], meaningfulPrecision: 2...16,
        layouts: ["greyscale8", "greyscale16", "components8", "components16"], availableBackends: [.scalarCPU, .accelerated],
        canInspect: true, canEncode: true, canDecode: true)

    static func layout(_ descriptor: ImageDescriptor, limits: ResourceLimits,
                       discardICC: Bool = false) throws -> PlaneDescriptor {
        try descriptor.validate(limits: limits)
        guard descriptor.sampleType == .unsignedInteger, (descriptor.storageBits == 8 || descriptor.storageBits == 16),
              (2...16).contains(descriptor.meaningfulBits), descriptor.planes.count == 1,
              descriptor.components == [.grey], descriptor.colour == .greyscale,
              descriptor.alpha == .absent, descriptor.iccProfile == nil || discardICC,
              descriptor.width <= Int(clamping: UInt32.max), descriptor.height <= Int(clamping: UInt32.max) else {
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
            try budget.check()
            return ImageInfo(format: "JPEG-LS", descriptor: header.admittedDescriptor, frameCount: 1, metadata: header.retainedMetadata(options.metadataPolicy))
        }
    }
    static func encode(_ image: Image, configuration: EncoderConfiguration, options: EncodeOptions) throws -> EncodedImage {
        let (resolvedBackend, fallbackReason) = try AccelerationRuntime.resolve(policy: options.executionPolicy)
        let budget = CodecBudget(limits: options.resourceLimits)
        return try mapped {
            let descriptor = image.descriptor
            let plane = try layout(descriptor, limits: budget.limits,
                                   discardICC: options.metadataPolicy == .discardAncillary)
            guard configuration.codecOptions.interleaveMode == .none, configuration.codecOptions.colourTransform == .none else {
                throw CodecError(.unsupportedFeature, "Greyscale requires non-interleaved coding.")
            }
            let discardedICCBytes = descriptor.iccProfile?.count ?? 0
            if discardedICCBytes > 0 {
                _ = try image.metadata.validate(limits: budget.limits, additionalBytes: discardedICCBytes)
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
            let interval = configuration.codecOptions.restartIntervalLines
            let chunks = interval > 0 ? 1 + (descriptor.height - 1) / interval : 1
            let worstOutput = try checkedAdd(checkedAdd(checkedMultiply(samples, 10), checkedAdd(64, metadata.byteCount)), checkedMultiply(chunks, 4))
            let outputLimit = min(worstOutput, budget.limits.maximumCompressedBytes)
            let perWorkerPredictor = near > 0 ? try checkedMultiply(descriptor.width, 4) : 0
            let baseWorkspace = try checkedAdd(checkedAdd(contextBytes, tableBytes(parameters)), checkedAdd(checkedMultiply(outputLimit, 2), perWorkerPredictor))
            let baseTotalWorkspace = try checkedAdd(checkedAdd(baseWorkspace, checkedMultiply(metadata.byteCount, 32)), discardedICCBytes)

            var effectiveWorkers = (resolvedBackend == .accelerated && chunks > 1)
                ? min(chunks, BoundedParallelPool.workerCount(requested: budget.limits.maximumWorkers))
                : 1
            let perExtraWorker = contextBytes + perWorkerPredictor
            while effectiveWorkers > 1 {
                let extra = (effectiveWorkers - 1) * perExtraWorker
                let candidateWs = baseTotalWorkspace + extra
                if candidateWs <= budget.limits.maximumWorkspaceBytes,
                   image.storage.byteCount + candidateWs + outputLimit <= budget.limits.maximumMemoryBytes {
                    break
                }
                effectiveWorkers -= 1
            }
            let admittedWorkspace = baseTotalWorkspace + (effectiveWorkers - 1) * perExtraWorker
            try budget.admit(pixelBytes: image.storage.byteCount,
                workspaceBytes: admittedWorkspace,
                compressedBytes: outputLimit)
            options.progress?(try ProgressUpdate(phase: .processing, completedUnits: 0, totalUnits: samples))
            try budget.check()
            var writer = JPEGLSBitstreamWriter(capacity: min(outputLimit, 4096), maximumBytes: outputLimit)
            let kernel = JPEGLSScalarKernel()
            let frame = try JPEGLSFrameHeader(bitsPerSample: descriptor.meaningfulBits,
                height: descriptor.height, width: descriptor.width, componentCount: 1,
                components: [.init(id: 1)])
            let scan = try JPEGLSScanHeader.singleComponent(mappingTableID: metadata.mapping?.componentTableIDs[0] ?? 0,
                near: near)
            writer.writeMarker(.startOfImage)
            try metadata.writeSPIFF(to: &writer)
            try metadata.ancillary.write(to: &writer)
            try kernel.writeFrameHeaderInternal(frame, to: &writer)
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
            try metadata.mapping?.write(to: &writer, budget: budget)
            try kernel.writeScanHeaderInternal(scan, to: &writer)
            try image.storage.withUnsafeBytes { bytes in
                guard bytes.count == image.storage.byteCount, bytes.count >= descriptor.requiredByteCount else {
                    throw CodecError(.storageUnavailable, "Input provider changed its capacity.")
                }
                let sampleBytes = descriptor.storageBits / 8
                let littleEndian = descriptor.byteOrder == .littleEndian
                let view = ScalarSampleReader(bytes: .init(rebasing: bytes[plane.offset..<descriptor.requiredByteCount]),
                    littleEndian: littleEndian, sampleBytes: sampleBytes)
                if near > 0 {
                    try view.validate(width: descriptor.width, height: descriptor.height,
                        rowStride: plane.rowBytes / view.sampleBytes, maximum: parameters.maxValue,
                        checkpoint: { try budget.check() })
                }
                let regular = near == 0 ? try JPEGLSRegularMode(parameters: parameters) : nil
                let run = near == 0 ? try JPEGLSRunMode(parameters: parameters) : nil
                let coding = kernel.computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: descriptor.meaningfulBits)
                let maximum = parameters.maxValue < (sampleBytes == 1 ? 255 : 65535) ? parameters.maxValue : nil

                if effectiveWorkers > 1 {
                    let sharedInput = SendableRawBorrow(buffer: bytes)
                    let chunkStorage = ChunkOutputCollector(count: chunks)
                    let chunkCap = max(256, min(outputLimit, (descriptor.width * interval * sampleBytes) / 2))
                    let reqByteCount = descriptor.requiredByteCount
                    let width = descriptor.width
                    let height = descriptor.height
                    let meaningfulBits = descriptor.meaningfulBits
                    try BoundedParallelPool.forEach(count: chunks, workers: effectiveWorkers) { chunk in
                        let localKernel = JPEGLSScalarKernel()
                        let first = chunk * interval
                        let last = first + min(interval, height - first)
                        var localWriter = JPEGLSBitstreamWriter(capacity: chunkCap, maximumBytes: outputLimit)
                        let localView = ScalarSampleReader(
                            bytes: .init(rebasing: sharedInput.buffer[plane.offset..<reqByteCount]),
                            littleEndian: littleEndian, sampleBytes: sampleBytes
                        )
                        if near > 0 {
                            let rowView = ScalarSampleReader(
                                bytes: .init(rebasing: localView.bytes[(first * plane.rowBytes)...]),
                                littleEndian: littleEndian, sampleBytes: sampleBytes
                            )
                            try localKernel.encodeNearLossless(
                                buf: rowView, rowStride: plane.rowBytes / sampleBytes,
                                width: width, height: last - first, near: near,
                                parameters: parameters, writer: &localWriter, bits: meaningfulBits,
                                checkpoint: { try budget.check() }
                            )
                        } else {
                            guard let regular, let run else {
                                throw CodecError(.internalFailure, "Lossless coding state is unavailable.")
                            }
                            var context = try JPEGLSContextModel(parameters: parameters)
                            try localKernel.encodeFlatRowsLossless(
                                buf: localView, rowStride: plane.rowBytes / sampleBytes,
                                rowRange: first..<last, sampleMaximum: maximum, width: width,
                                regularMode: regular, runMode: run, context: &context,
                                writer: &localWriter, limit: coding.limit, qbppBits: coding.qbppBits,
                                checkpoint: { try budget.check() }
                            )
                        }
                        localWriter.flush()
                        chunkStorage.store(index: chunk, bytes: try localWriter.consumeRawBytes())
                    }
                    let encodedChunks = chunkStorage.takeAll()
                    for chunk in 0..<chunks {
                        writer.appendRawBytes(encodedChunks[chunk])
                        try writer.checkLimit()
                        if chunk + 1 < chunks {
                            guard let marker = JPEGLSMarker(rawValue: 0xd0 + UInt8(chunk % 8)) else {
                                throw CodecError(.internalFailure, "Restart marker unavailable.")
                            }
                            writer.writeMarker(marker)
                        }
                    }
                } else {
                    for chunk in 0..<chunks {
                        let first = interval > 0 ? chunk * interval : 0
                        let last = interval > 0 ? first + min(interval, descriptor.height - first) : descriptor.height
                        if near > 0 {
                            let rowView = ScalarSampleReader(bytes: .init(rebasing: view.bytes[(first * plane.rowBytes)...]),
                                littleEndian: view.littleEndian, sampleBytes: view.sampleBytes)
                            try kernel.encodeNearLossless(buf: rowView, rowStride: plane.rowBytes / view.sampleBytes,
                                width: descriptor.width, height: last - first, near: near,
                                parameters: parameters, writer: &writer, bits: descriptor.meaningfulBits,
                                checkpoint: { try budget.check() })
                        } else {
                            guard let regular, let run else {
                                throw CodecError(.internalFailure, "Lossless coding state is unavailable.")
                            }
                            var context = try JPEGLSContextModel(parameters: parameters)
                            try kernel.encodeFlatRowsLossless(buf: view, rowStride: plane.rowBytes / view.sampleBytes,
                                rowRange: first..<last, sampleMaximum: maximum, width: descriptor.width, regularMode: regular,
                                runMode: run, context: &context, writer: &writer, limit: coding.limit,
                                qbppBits: coding.qbppBits, checkpoint: { try budget.check() })
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
            }
            writer.flush(); writer.writeMarker(.endOfImage)
            let data = try writer.getData()
            try budget.check()
            let result = EncodedImage(data: data, encoding: .init(format: "JPEG-LS", mode: configuration.mode),
                report: OperationReport(backend: resolvedBackend, fallbackReason: fallbackReason,
                    fidelity: near == 0 ? .exactSamples : .boundedError(near), pixelAllocationCount: 0, peakPixelBytes: 0,
                    peakWorkspaceBytes: nil, elapsedSeconds: budget.elapsedSeconds))
            options.progress?(try ProgressUpdate(phase: .completed, completedUnits: samples, totalUnits: samples))
            try budget.check()
            return result
        }
    }
    static func decode(_ data: Data, into supplied: ImageDestination?, options: DecodeOptions,
                       codecOptions: CodecOptions = .init()) throws -> DecodedImage {
        let (resolvedBackend, fallbackReason) = try AccelerationRuntime.resolve(policy: options.executionPolicy)
        let budget = CodecBudget(limits: options.resourceLimits)
        return try mapped {
            let header = try JPEGLSHeader.parse(data, budget: budget, codecOptions: codecOptions)
            if !header.grey {
                return try ComponentCodec.decode(data, header: header, into: supplied, options: options, budget: budget, hpInterpretation: codecOptions.hpInterpretation, resolvedBackend: resolvedBackend, fallbackReason: fallbackReason)
            }
            let descriptor: ImageDescriptor
            let plane: PlaneDescriptor
            if let supplied {
                descriptor = supplied.descriptor
                plane = try layout(descriptor, limits: budget.limits)
                guard descriptor.width == header.width, descriptor.height == header.height,
                      descriptor.meaningfulBits == header.outputBits, descriptor.storageBits >= header.bits else {
                    throw CodecError(.incompatibleImageLayout, "Destination geometry or precision does not match the codestream.")
                }
            } else {
                descriptor = header.admittedDescriptor
                guard (2...16).contains(descriptor.meaningfulBits) && descriptor.storageBits >= header.bits else {
                    throw CodecError(.unsupportedFeature, "The migrated scalar profile requires unsigned greyscale without ICC metadata.")
                }
                plane = descriptor.planes[0]
            }
            let baseWorkspace = try checkedAdd(checkedAdd(contextBytes, tableBytes(header.parameters)), checkedAdd(checkedMultiply(data.count, 2), checkedMultiply(header.scans.count, MemoryLayout<Range<Int>>.stride * 2)))
            let baseTotalWorkspace = try checkedAdd(baseWorkspace, checkedMultiply(header.metadataBytes, 32))
            let pixelBytes = supplied?.storage.byteCount ?? descriptor.requiredByteCount

            var effectiveWorkers = (resolvedBackend == .accelerated && header.scans.count > 1)
                ? min(header.scans.count, BoundedParallelPool.workerCount(requested: budget.limits.maximumWorkers))
                : 1
            while effectiveWorkers > 1 {
                let extra = (effectiveWorkers - 1) * contextBytes
                let candidateWs = baseTotalWorkspace + extra
                if candidateWs <= budget.limits.maximumWorkspaceBytes,
                   pixelBytes + candidateWs + data.count <= budget.limits.maximumMemoryBytes {
                    break
                }
                effectiveWorkers -= 1
            }
            try budget.admit(pixelBytes: pixelBytes, workspaceBytes: baseTotalWorkspace + (effectiveWorkers - 1) * contextBytes, compressedBytes: data.count)
            let samples = try checkedMultiply(header.width, header.height)
            options.progress?(try ProgressUpdate(phase: .processing, completedUnits: 0, totalUnits: samples))
            try budget.check()
            let kernel = JPEGLSScalarKernel()
            let coding = kernel.computeGolombLimitInternal(parameters: header.parameters, near: header.near, bitsPerSample: header.bits)
            let sharedDecoder = try JPEGLSRegularModeDecoder(parameters: header.parameters, near: header.near)
            let sharedRunDecoder = try JPEGLSRunModeDecoder(parameters: header.parameters, near: header.near)
            let fidelity = try header.fidelity(budget: budget)
            let metadata = header.retainedMetadata(options.metadataPolicy)
            func fill(_ bytes: UnsafeMutableRawBufferPointer) throws {
                try data.withUnsafeBytes { compressedRaw in
                    let sampleBytes = descriptor.storageBits / 8
                    let littleEndian = descriptor.byteOrder == .littleEndian
                    let reqBytes = descriptor.requiredByteCount
                    let scans = header.scans
                    if effectiveWorkers > 1 {
                        let sharedCompressed = SendableRawBorrow(buffer: compressedRaw)
                        let sharedOutput = SendableMutableRawBorrow(buffer: bytes)
                        let restartInt = header.restartInterval
                        let width = header.width
                        let height = header.height
                        let params = header.parameters
                        let near = header.near
                        try BoundedParallelPool.forEach(count: scans.count, workers: effectiveWorkers) { chunk in
                            let scan = scans[chunk]
                            let firstRow = restartInt > 0 ? chunk * restartInt : 0
                            let rows = restartInt > 0 ? min(restartInt, height - firstRow) : height
                            let offset = plane.offset + firstRow * plane.rowBytes
                            let view = ScalarSampleWriter(
                                bytes: .init(rebasing: sharedOutput.buffer[offset..<reqBytes]),
                                littleEndian: littleEndian, sampleBytes: sampleBytes
                            )
                            var reader = JPEGLSFastBitReader(borrowing: .init(rebasing: sharedCompressed.buffer[scan]))
                            let localKernel = JPEGLSScalarKernel()
                            try localKernel.decodeFlatRegion(
                                into: view, rowStride: plane.rowBytes / sampleBytes, reader: &reader,
                                rows: rows, width: width, parameters: params, near: near,
                                limit: coding.limit, qbppBits: coding.qbppBits,
                                sharedDecoder: sharedDecoder, sharedRunDecoder: sharedRunDecoder,
                                checkpoint: { try budget.check() }
                            )
                            try reader.validateEndOfScan()
                        }
                    } else {
                        for (chunk, scan) in scans.enumerated() {
                            let firstRow = header.restartInterval > 0 ? chunk * header.restartInterval : 0
                            let rows = header.restartInterval > 0 ? min(header.restartInterval, header.height - firstRow) : header.height
                            let offset = plane.offset + firstRow * plane.rowBytes
                            let view = ScalarSampleWriter(bytes: .init(rebasing: bytes[offset..<reqBytes]),
                                littleEndian: littleEndian, sampleBytes: sampleBytes)
                            var reader = JPEGLSFastBitReader(borrowing: .init(rebasing: compressedRaw[scan]))
                            try kernel.decodeFlatRegion(
                                into: view, rowStride: plane.rowBytes / sampleBytes, reader: &reader,
                                rows: rows, width: header.width, parameters: header.parameters, near: header.near,
                                limit: coding.limit, qbppBits: coding.qbppBits,
                                sharedDecoder: sharedDecoder, sharedRunDecoder: sharedRunDecoder,
                                checkpoint: { try budget.check() }
                            )
                            try reader.validateEndOfScan()
                        }
                    }
                }
                try header.mapSamples(in: bytes, descriptor: descriptor, budget: budget)
                try budget.check()
            }
            let image = try supplied?.write(metadata: metadata, fill)
                ?? Image.writeAdmittedOwned(descriptor: descriptor, metadata: metadata, limits: budget.limits, fill)
            let result = DecodedImage(image: image, report: OperationReport(backend: resolvedBackend,
                fallbackReason: fallbackReason, fidelity: fidelity,
                pixelAllocationCount: supplied == nil ? 1 : 0, peakPixelBytes: supplied == nil ? pixelBytes : 0,
                peakWorkspaceBytes: nil, elapsedSeconds: budget.elapsedSeconds))
            options.progress?(try ProgressUpdate(phase: .completed, completedUnits: samples, totalUnits: samples))
            try budget.check()
            return result
        }
    }
}
