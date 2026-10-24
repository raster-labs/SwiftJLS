// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Core/JPEGLSManagedFailure.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
/// Nonthrowing result with scalar failure facts, no Error existential or formatting.
public enum QualifiedOutcome<Value> {
    case success(Value)
    case failure(QualifiedFailure)

}

/// Scalar facts to inspect or format after the operation. Deliberately not Error.
public struct QualifiedFailure: Sendable, Equatable {
    public enum Code: UInt8, Sendable {
        case prematureEndOfStream
        case invalidBitsPerSample
        case invalidDimensions
        case invalidComponentCount
        case invalidNearParameter
        case invalidMarker
        case expectedPrefix
        case unknownMarkerLength
        case expectedMarker
        case markerLength
        case sofLength
        case sosLength
        case interleaveMode
        case lseLength
        case presetLength
        case mappingLength
        case mappingWidth
        case mappingRemainder
        case continuationLength
        case continuationRemainder
        case extendedLength
        case driLength
        case frameComponentMismatch
        case scanComponentMismatch
        case scanInterleave
        case pointTransform
        case unknownScanComponent
        case noninterleavedCount
        case interleavedCount
        case maxValue
        case threshold1
        case threshold2
        case threshold3
        case reset
        case bitCount
        case seekPosition
        case trailingBytes
        case missingFrame
        case missingScan
        case multipleFrames
        case scanBeforeFrame
        case monochromeScanCount
        case unexpectedSOI
        case missingEOI
        case monochromeComponentCount
        case destinationOverflow
        case overlappingBuffers
        case destinationTooSmall
        case missingMonochromeScan
        case tooManyRegions
        case restartMarker
        case missingRegions
        case incompleteReconstruction
        case mappedPrecision
        case monochromeProfile
        case samplingFactors
        case decodedLimit
        case maxValuePrecision
        case invalidCallerSpans
        case restartCycle
        case mappingID
        case mappingContinuation
        case cancelled
        case invalidLimits
        case unsupportedProfile
        case missingMappingTable
        case mappingIndex
        case invalidEntropy
        case deadlineExceeded
        case clockUnavailable
    }
    public let code: Code
    public let operand0: Int
    public let operand1: Int
    internal init(_ code: Code, _ operand0: Int = 0, _ operand1: Int = 0) {
        self.code = code; self.operand0 = operand0; self.operand1 = operand1
    }

}

/// Unsafe synchronous callback/context borrow. Neither escapes the codec call.
/// The caller owns their lifetime and cross-thread synchronisation. A nil callback
/// never cancels. Callback allocations are caller work; Task state is not queried.
public struct QualifiedCancellation {
    private let check: (@convention(c) (UnsafeMutableRawPointer?) -> Bool)?
    private let context: UnsafeMutableRawPointer?
    private var deadline: UInt64 = 0
    public init(check: (@convention(c) (UnsafeMutableRawPointer?) -> Bool)? = nil,
                context: UnsafeMutableRawPointer? = nil) {
        self.check = check; self.context = context
    }
    internal func startingDeadline(seconds: Double) -> QualifiedOutcome<Self> {
        guard seconds.isFinite, seconds > 0 else { return .failure(QualifiedFailure(.invalidLimits)) }
        guard let now = qualifiedMonotonicNanoseconds() else { return .failure(QualifiedFailure(.clockUnavailable)) }
        // Avoid conversion traps for huge finite deadlines; saturation retains a
        // finite representable monotonic bound, as in the common deadline policy.
        let scaled = seconds * 1_000_000_000
        let nanos: UInt64 = scaled >= Double(UInt64.max)
            ? UInt64.max : max(1, UInt64(scaled))
        let end = now.addingReportingOverflow(nanos)
        var result = self
        result.deadline = end.overflow ? UInt64.max : end.partialValue
        return .success(result)
    }
    internal func checkpoint() -> QualifiedFailure? {
        if check?(context) == true { return QualifiedFailure(.cancelled) }
        if deadline != 0 {
            guard let now = qualifiedMonotonicNanoseconds() else { return QualifiedFailure(.clockUnavailable) }
            if now >= deadline { return QualifiedFailure(.deadlineExceeded) }
        }
        return nil
    }

}

#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif

private func qualifiedMonotonicNanoseconds() -> UInt64? {
    var instant = timespec()
    guard clock_gettime(CLOCK_MONOTONIC, &instant) == 0,
          instant.tv_sec >= 0, instant.tv_nsec >= 0 else { return nil }
    let seconds = UInt64(instant.tv_sec).multipliedReportingOverflow(by: 1_000_000_000)
    let total = seconds.partialValue.addingReportingOverflow(UInt64(instant.tv_nsec))
    guard !seconds.overflow, !total.overflow else { return nil }
    return total.partialValue
}

extension QualifiedOutcome: Sendable where Value: Sendable {}
