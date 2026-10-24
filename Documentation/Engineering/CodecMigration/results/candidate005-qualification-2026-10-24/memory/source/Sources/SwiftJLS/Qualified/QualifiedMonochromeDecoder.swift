// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/JPEGLSMonochromeDecoder.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.

/// Advanced synchronous caller-workspace JPEG-LS monochrome decoder.
///
/// This is separate from the common owning `Decoder` API. All spans are unsafe
/// synchronous borrows: keep them alive and disjoint throughout the call, provide
/// exclusive output/scratch access, and keep the input immutable (including during
/// cancellation callbacks). Callbacks must not access mutable output/scratch.
/// Discard output after any failure. No
/// pointer is retained, no task is created, and no pointer may cross `await`.
/// The implementation constructs no owned input, pixel or variable parser/context
/// backing. Stack/runtime/caller-callback costs are outside the payload size.
///
/// The required compatibility profile is not a general JPEG-LS conformance or
/// fidelity promise. Ancillary payloads are scanned in place and not returned.
public struct QualifiedMonochromeDecoder: Sendable {
    public enum Profile: Sendable {
        /// JLSwift 0.10.1 at d175452: legacy implicit defaults (including
        /// low MAXVAL and high NEAR), final LSE preset
        /// selection, extended dimensions before SOF, and omitted continuation Wt.
        /// Selected palette entries replace indices. Missing tables/entries and
        /// malformed entropy are rejected (stricter than the predecessor).
        /// Point transform is metadata-only and DOES NOT shift samples.
        /// HP colour transformations are rejected. Prefer the common Decoder
        /// for standard interpretation and automatic ownership/lifecycle handling.
        case jlswift0101
    }
    /// Scalar independent admission ceilings, checked by each operation.
    /// Memory counts the complete borrowed encoded/output/scratch capacities.
    /// Metadata is neither retained nor expanded beyond the fixed palette scratch.
    public struct Limits: Sendable, Equatable {
        public let maximumEncodedBytes: Int
        public let maximumPixels: Int
        public let maximumDecodedBytes: Int
        public let maximumDimension: Int
        public let maximumWorkspaceBytes: Int
        public let maximumMemoryBytes: Int
        public let deadlineSeconds: Double
        public init(maximumEncodedBytes: Int = 16 << 20,
                    maximumPixels: Int = 16 << 20,
                    maximumDecodedBytes: Int = 32 << 20,
                    maximumDimension: Int = 1_000_000,
                    maximumWorkspaceBytes: Int = 1 << 20,
                    maximumMemoryBytes: Int = 64 << 20,
                    deadlineSeconds: Double = 30) {
            self.maximumEncodedBytes = maximumEncodedBytes
            self.maximumPixels = maximumPixels
            self.maximumDecodedBytes = maximumDecodedBytes
            self.maximumDimension = maximumDimension
            self.maximumWorkspaceBytes = maximumWorkspaceBytes
            self.maximumMemoryBytes = maximumMemoryBytes
            self.deadlineSeconds = deadlineSeconds
        }
    }
    private let limits: Limits
    public init(profile: Profile, limits: Limits = .init()) { self.limits = limits }
    public static var workspaceAlignment: Int { MemoryLayout<Int>.alignment }
}

extension QualifiedMonochromeDecoder {
    /// Scalar metadata; samples use host-endian unsigned UInt16 storage.
    /// The point-transform value is reported, not applied by this profile.
    public struct MonochromeInfo: Sendable, Equatable {
        public let width: Int
        public let height: Int
        public let bitsPerSample: Int
        public let near: Int
        public let pointTransform: Int
        public let mappingTableID: UInt8
        public let hasMappingTables: Bool
        public let colorTransformation: UInt8
        public var sampleCount: Int { width * height }
    }

    /// Exact caller payload, excluding fixed stack controls/runtime work. Scratch
    /// must be raw trivial storage whose binding may change, aligned as specified.
    public static var workspaceByteCount: Int {
        256 * MemoryLayout<Int>.stride + 65_536 * MemoryLayout<UInt16>.stride +
        QualifiedContextModel.workspaceByteCount
    }

    /// Inspect the entire structure/restart envelope, without decoding entropy.
    /// Input and scratch must be disjoint, valid and alive for this unsafe borrow.
    public func inspect(_ encoded: UnsafeRawBufferPointer,
                                  workspace: UnsafeMutableRawBufferPointer,
                                  cancellation: QualifiedCancellation = .init()) -> QualifiedOutcome<MonochromeInfo> {
        let budget: QualifiedCancellation
        switch cancellation.startingDeadline(seconds: limits.deadlineSeconds) {
        case .success(let value): budget = value
        case .failure(let failure): return .failure(failure)
        }
        let cancellation = budget
        if let failure = validateMonochromeSpans(encoded, workspace: workspace, cancellation: cancellation) { return .failure(failure) }
        var storage = monochromeStorage(workspace)
        var parser = QualifiedParserCore(reader: QualifiedBitstreamCursor(borrowing: encoded, cancellation: cancellation))
        let parsed: QualifiedParseState
        switch parser.parse(storage: &storage) {
        case .success(let value): parsed = value
        case .failure(let failure): return .failure(failure)
        }
        if let failure = storage.validateRestarts(parsed) { return .failure(failure) }
        if let failure = storage.validateMappingSelection(parsed) { return .failure(failure) }
        switch monochromePlan(parsed, hasMappingTables: storage.hasMappingTables) {
        case .success(let value): return .success(value.info)
        case .failure(let failure): return .failure(failure)
        }
    }

    /// Reconstruct into initialised caller UInt16 storage. Structure/restarts and
    /// destination capacity are admitted before sample writes. Entropy, palette or
    /// cancellation failures can leave partial writes: discard the output then.
    /// Excess destination capacity remains untouched. All three spans are disjoint.
    public func decode(_ encoded: UnsafeRawBufferPointer,
                                 into output: UnsafeMutableBufferPointer<UInt16>,
                                 workspace: UnsafeMutableRawBufferPointer,
                                  cancellation: QualifiedCancellation = .init()) -> QualifiedOutcome<MonochromeInfo> {
        let budget: QualifiedCancellation
        switch cancellation.startingDeadline(seconds: limits.deadlineSeconds) {
        case .success(let value): budget = value
        case .failure(let failure): return .failure(failure)
        }
        let cancellation = budget
        if let failure = validateMonochromeSpans(encoded, workspace: workspace, cancellation: cancellation) { return .failure(failure) }
        guard output.count <= Int.max / MemoryLayout<UInt16>.stride else {
            return .failure(QualifiedFailure(.destinationOverflow))
        }
        let outputRaw = UnsafeRawBufferPointer(output)
        let baseBytes = encoded.count.addingReportingOverflow(workspace.count)
        let totalBytes = baseBytes.partialValue.addingReportingOverflow(outputRaw.count)
        guard !baseBytes.overflow, !totalBytes.overflow,
              outputRaw.count <= limits.maximumDecodedBytes,
              totalBytes.partialValue <= limits.maximumMemoryBytes else {
            return .failure(QualifiedFailure(.decodedLimit))
        }
        guard !Self.overlaps(encoded, outputRaw),
              !Self.overlaps(UnsafeRawBufferPointer(workspace), outputRaw),
              outputRaw.baseAddress.map({ UInt(bitPattern: $0) % UInt(MemoryLayout<UInt16>.alignment) == 0 }) ?? true else {
            return .failure(QualifiedFailure(.overlappingBuffers))
        }
        var firstStorage = monochromeStorage(workspace)
        var firstParser = QualifiedParserCore(reader: QualifiedBitstreamCursor(borrowing: encoded, cancellation: cancellation))
        let inspection: QualifiedParseState
        switch firstParser.parse(storage: &firstStorage) {
        case .success(let value): inspection = value
        case .failure(let failure): return .failure(failure)
        }
        if let failure = firstStorage.validateRestarts(inspection) { return .failure(failure) }
        if let failure = firstStorage.validateMappingSelection(inspection) { return .failure(failure) }
        let plan: MonochromePlan
        switch monochromePlan(inspection, hasMappingTables: firstStorage.hasMappingTables) {
        case .success(let value): plan = value
        case .failure(let failure): return .failure(failure)
        }
        let info = plan.info
        guard output.count >= info.sampleCount else {
            return .failure(QualifiedFailure(.destinationTooSmall))
        }
        let scan = inspection.firstScan
        let selector = scan.components[0]
        let interval = inspection.scanRestartInterval
        let restartActive = interval > 0 && interval < info.height
        let expectedRegions = restartActive ? 1 + (info.height - 1) / interval : 1
        let contextOffset = 256 * MemoryLayout<Int>.stride + 65_536 * MemoryLayout<UInt16>.stride
        let contextWorkspace = UnsafeMutableRawBufferPointer(rebasing: workspace[contextOffset..<Self.workspaceByteCount])
        let (limit, qbppBits) = computeGolombLimit(parameters: plan.parameters, near: info.near,
                                                  bitsPerSample: info.bitsPerSample)
        let consumer = QualifiedRegionConsumer(decoder: self, encoded: encoded, output: output,
            contextWorkspace: contextWorkspace, cancellation: cancellation, info: info,
            parameters: plan.parameters, interval: interval, expectedRegions: expectedRegions,
            restartActive: restartActive, limit: limit, qbppBits: qbppBits)
        var storage = monochromeStorage(workspace, selectedTable: selector.mappingTableID, consumer: consumer)
        var parser = QualifiedParserCore(reader: QualifiedBitstreamCursor(borrowing: encoded, cancellation: cancellation))
        // The same grammar emits regions into a concrete value sink. There is no
        // escaping callback, capture box, or retained region list.
        if case .failure(let failure) = parser.parse(storage: &storage) { return .failure(failure) }
        guard storage.consumer?.region == expectedRegions,
              storage.consumer?.decodedRows == info.height else {
            return .failure(QualifiedFailure(.incompleteReconstruction))
        }
        let sampleCap = (1 << info.bitsPerSample) - 1
        for index in 0..<info.sampleCount {
            if index & 0xFFFF == 0, let failure = cancellation.checkpoint() { return .failure(failure) }
            guard let value = storage.mapped(output[index]) else { return .failure(QualifiedFailure(.mappingIndex, Int(output[index]))) }
            guard Int(value) <= sampleCap else {
                return .failure(QualifiedFailure(.mappedPrecision))
            }
            output[index] = value
        }
        return .success(info)
    }

    private typealias MonochromePlan = (info: MonochromeInfo, parameters: QualifiedPresetParameters)

    private func monochromePlan(_ parsed: QualifiedParseState, hasMappingTables: Bool) -> QualifiedOutcome<MonochromePlan> {
        let frame = parsed.frameHeader
        let scan = parsed.firstScan
        guard frame.componentCount == 1, parsed.scanCount == 1, scan.interleaveMode == .none else {
            return .failure(QualifiedFailure(.monochromeProfile))
        }
        let component = frame.components[0]
        guard component.horizontalSamplingFactor > 0, component.verticalSamplingFactor > 0 else {
            return .failure(QualifiedFailure(.samplingFactors))
        }
        let (count, overflow) = frame.width.multipliedReportingOverflow(by: frame.height)
        let (bytes, byteOverflow) = count.multipliedReportingOverflow(by: MemoryLayout<UInt16>.stride)
        guard !overflow, !byteOverflow, count > 0,
              count <= limits.maximumPixels, bytes <= limits.maximumDecodedBytes,
              frame.width <= limits.maximumDimension, frame.height <= limits.maximumDimension else {
            return .failure(QualifiedFailure(.decodedLimit))
        }
        let parameters: QualifiedPresetParameters
        if let preset = parsed.presetParameters { parameters = preset }
        else {
            switch QualifiedPresetParameters.qualifiedDefaultParameters(bitsPerSample: frame.bitsPerSample, near: scan.near) {
            case .success(let value): parameters = value
            case .failure(let failure): return .failure(failure)
            }
        }
        guard parameters.maxValue <= (1 << frame.bitsPerSample) - 1 else {
            return .failure(QualifiedFailure(.maxValuePrecision))
        }
        return .success((MonochromeInfo(width: frame.width, height: frame.height,
            bitsPerSample: frame.bitsPerSample, near: scan.near, pointTransform: scan.pointTransform,
            mappingTableID: scan.components[0].mappingTableID,
            hasMappingTables: hasMappingTables, colorTransformation: parsed.colorTransformation.rawValue), parameters))
    }

    private func validateMonochromeSpans(_ encoded: UnsafeRawBufferPointer,
                                        workspace: UnsafeMutableRawBufferPointer, cancellation: QualifiedCancellation) -> QualifiedFailure? {
        guard limits.maximumEncodedBytes > 0, limits.maximumPixels > 0,
              limits.maximumDecodedBytes > 0, limits.maximumDimension > 0,
              limits.maximumWorkspaceBytes > 0, limits.maximumMemoryBytes > 0 else {
            return QualifiedFailure(.invalidLimits)
        }
        let total = encoded.count.addingReportingOverflow(workspace.count)
        guard !total.overflow, total.partialValue <= limits.maximumMemoryBytes,
              workspace.count <= limits.maximumWorkspaceBytes,
              encoded.count <= limits.maximumEncodedBytes, encoded.count <= Int.max / 8,
              workspace.count >= Self.workspaceByteCount,
              let address = workspace.baseAddress,
              UInt(bitPattern: address) % UInt(MemoryLayout<Int>.alignment) == 0,
              !Self.overlaps(encoded, UnsafeRawBufferPointer(workspace)) else {
            return QualifiedFailure(.invalidCallerSpans)
        }
        return cancellation.checkpoint()
    }

    private func monochromeStorage(_ workspace: UnsafeMutableRawBufferPointer,
                                   selectedTable: UInt8? = nil,
                                   consumer: QualifiedRegionConsumer? = nil) -> QualifiedParseStorage {
        // validateMonochromeSpans establishes a nonnil, aligned backing first.
        let tableOffset = 256 * MemoryLayout<Int>.stride
        let widths = UnsafeMutableRawBufferPointer(rebasing: workspace[..<tableOffset]).bindMemory(to: Int.self)
        let values = UnsafeMutableRawBufferPointer(rebasing: workspace[tableOffset..<(tableOffset + 65_536 * 2)])
            .bindMemory(to: UInt16.self)
        return QualifiedParseStorage(widths: UnsafeMutableBufferPointer(rebasing: widths[..<256]),
            values: values, selectedTable: selectedTable, consumer: consumer)
    }

    private static func overlaps(_ left: UnsafeRawBufferPointer, _ right: UnsafeRawBufferPointer) -> Bool {
        guard !left.isEmpty, !right.isEmpty, let l = left.baseAddress, let r = right.baseAddress else { return false }
        let a = UInt(bitPattern: l), b = UInt(bitPattern: r)
        let (endA, overA) = a.addingReportingOverflow(UInt(left.count))
        let (endB, overB) = b.addingReportingOverflow(UInt(right.count))
        return overA || overB || (a < endB && b < endA)
    }
}

internal struct QualifiedRegionConsumer {
    let decoder: QualifiedMonochromeDecoder
    let encoded: UnsafeRawBufferPointer
    let output: UnsafeMutableBufferPointer<UInt16>
    let contextWorkspace: UnsafeMutableRawBufferPointer
    let cancellation: QualifiedCancellation
    let info: QualifiedMonochromeDecoder.MonochromeInfo
    let parameters: QualifiedPresetParameters
    let interval: Int, expectedRegions: Int
    let restartActive: Bool
    let limit: Int, qbppBits: Int
    private(set) var region = 0
    private(set) var decodedRows = 0

    mutating func consume(_ range: Range<Int>, marker: UInt8?) -> QualifiedFailure? {
        if let failure = cancellation.checkpoint() { return failure }
        guard region < expectedRegions else { return QualifiedFailure(.tooManyRegions) }
        if let marker {
            guard restartActive, region < expectedRegions - 1,
                  marker == QualifiedMarker.restart0.rawValue + UInt8(region % 8) else {
                return QualifiedFailure(.restartMarker)
            }
        } else if region != expectedRegions - 1 { return QualifiedFailure(.missingRegions) }
        let rows = restartActive ? min(interval, info.height - decodedRows) : info.height
        let start = decodedRows * info.width
        let destination = UnsafeMutableBufferPointer(rebasing: output[start..<(start + rows * info.width)])
        var reader = QualifiedBitstreamCursor(borrowing: UnsafeRawBufferPointer(rebasing: encoded[range]),
            cancellation: cancellation)
        if let failure = decoder.decodeFlatRegionQualified(reader: &reader, rows: rows, width: info.width, rowStride: info.width,
            parameters: parameters, near: info.near, limit: limit, qbppBits: qbppBits,
            into: destination, workspace: contextWorkspace) { return failure }
        if let failure = reader.validateEndOfScan() { return failure }
        decodedRows += rows
        region += 1
        return nil
    }
}
