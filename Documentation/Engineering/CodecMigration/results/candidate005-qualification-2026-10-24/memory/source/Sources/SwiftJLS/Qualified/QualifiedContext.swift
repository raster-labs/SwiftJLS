// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Core/JPEGLSContextModel.swift; Core/JPEGLSBorrowedStorage.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal struct QualifiedWorkingBuffer<Element: BitwiseCopyable> {
    private let storage: UnsafeMutableBufferPointer<Element>
    init(repeating value: Element, count: Int, borrowing pointer: UnsafeMutableBufferPointer<Element>) {
        // All five slice counts are fixed and checked before the kernel is entered.
        pointer.initialize(repeating: value)
        storage = pointer
    }
    subscript(index: Int) -> Element {
        get { storage[index] }
        nonmutating set { storage[index] = newValue }
    }
}
internal struct QualifiedContextModel {
    // MARK: - Constants

    internal static let regularContextCount = 365

    internal static let runContextCount = 2

    // MARK: - Context State

    private struct ContextRecord: BitwiseCopyable, Sendable {
        var a: Int
        var b: Int
        var c: Int
        var n: Int
    }

    private var contexts: QualifiedWorkingBuffer<ContextRecord>

    // MARK: - Run-Length State

    private var runInterruptionIndex: QualifiedWorkingBuffer<Int>

    private var runInterruptionA: QualifiedWorkingBuffer<Int>

    private var runInterruptionN: QualifiedWorkingBuffer<Int>

    private var runInterruptionNN: QualifiedWorkingBuffer<Int>

    private var runLength: Int

    private var runIndex: Int

    // MARK: - Parameters

    private let parameters: QualifiedPresetParameters

    private let near: Int

    private let aInit: Int

    private let resetThreshold: Int
    private let bFactor: Int

    // MARK: - Initialization

    internal static var workspaceByteCount: Int {
        regularContextCount * MemoryLayout<ContextRecord>.stride + 8 * MemoryLayout<Int>.stride
    }

    internal static func qualified(parameters: QualifiedPresetParameters, near: Int,
                  workspace: UnsafeMutableRawBufferPointer) -> QualifiedOutcome<Self> {
        guard near >= 0 && near <= 255 else {
            return .failure(QualifiedFailure(.invalidNearParameter, near))
        }
        return .success(Self(validatedParameters: parameters, near: near, workspace: workspace))
    }

    private init(validatedParameters parameters: QualifiedPresetParameters, near: Int,
                  workspace: UnsafeMutableRawBufferPointer) {

        self.parameters = parameters
        self.near = near

        // Compute RANGE per ITU-T.87 Section 4.2.1
        let range: Int
        if near == 0 {
            range = parameters.maxValue + 1
        } else {
            let qbpp = (near << 1) | 1
            range = (parameters.maxValue + 2 * near) / qbpp + 1
        }

        // Compute A initial value per ITU-T.87 Section 4.3:
        // A[i] = max(2, floor((RANGE + 32) / 64))
        self.aInit = max(2, (range + 32) / 64)
        self.resetThreshold = parameters.reset
        self.bFactor = 2 * near + 1

        // Initialize context records to default values per ITU-T.87 Section 4.3
        self.contexts = QualifiedWorkingBuffer(
            repeating: ContextRecord(a: 0, b: 0, c: 0, n: 1), count: Self.regularContextCount,
            borrowing: Self.buffer(workspace: workspace, ContextRecord.self, offset: 0, count: Self.regularContextCount))
        let runOffset = Self.regularContextCount * MemoryLayout<ContextRecord>.stride
        let pair = 2 * MemoryLayout<Int>.stride
        let riAInit = max(2, (range + 32) / 64)
        self.runInterruptionIndex = QualifiedWorkingBuffer(repeating: 0, count: 2,
            borrowing: Self.buffer(workspace: workspace, Int.self, offset: runOffset, count: 2))
        self.runInterruptionA = QualifiedWorkingBuffer(repeating: riAInit, count: 2,
            borrowing: Self.buffer(workspace: workspace, Int.self, offset: runOffset + pair, count: 2))
        self.runInterruptionN = QualifiedWorkingBuffer(repeating: 1, count: 2,
            borrowing: Self.buffer(workspace: workspace, Int.self, offset: runOffset + pair * 2, count: 2))
        self.runInterruptionNN = QualifiedWorkingBuffer(repeating: 0, count: 2,
            borrowing: Self.buffer(workspace: workspace, Int.self, offset: runOffset + pair * 3, count: 2))
        self.runLength = 0
        self.runIndex = 0

        // Set initial context values according to ITU-T.87
        initializeContexts()
    }

    private static func buffer<T>(workspace: UnsafeMutableRawBufferPointer, _ type: T.Type,
                                  offset: Int, count: Int) -> UnsafeMutableBufferPointer<T> {
        // Caller admission proves nonempty/aligned scratch, and fixed slices are in range.
        let typed = UnsafeMutableRawBufferPointer(rebasing: workspace[offset..<(offset + count * MemoryLayout<T>.stride)]).bindMemory(to: T.self)
        return UnsafeMutableBufferPointer(rebasing: typed[..<count])
    }

    private mutating func initializeContexts() {
        for i in 0..<Self.regularContextCount {
            contexts[i] = ContextRecord(a: aInit, b: 0, c: 0, n: 1)
        }
    }

    // MARK: - Context Index Computation

    @inline(__always)
    internal func computeContextIndexAndSign(q1: Int, q2: Int, q3: Int) -> (index: Int, sign: Int) {
        let sign = computeContextSign(q1: q1, q2: q2, q3: q3)
        // Qt = 81 × Q1 + 9 × Q2 + Q3 over sign-normalised gradients
        // (ITU-T.87 Section 4.3.1).
        let index = 81 * (q1 * sign) + 9 * (q2 * sign) + (q3 * sign)
        return (max(0, min(index, Self.regularContextCount - 1)), sign)
    }

    // MARK: - Context State Access

    // MARK: - Context Update

    internal mutating func updateContext(contextIndex: Int, predictionError: Int, sign: Int) {
        guard contextIndex >= 0 && contextIndex < Self.regularContextCount else {
            return
        }

        // Load the record once; all updates happen on locals and store back
        // in a single write (one bounds + one CoW check per pixel).
        var r = contexts[contextIndex]

        // Update A (accumulated absolute prediction error) per ITU-T.87
        r.a += abs(predictionError)

        // Update B per ITU-T.87 §A.6.2: B[Q] += Errval × (2·NEAR + 1)
        // The caller passes predictionError = sign × Errval (sign-denormalised),
        // so sign × predictionError = Errval (sign-normalised error per the standard).
        let errval = sign * predictionError
        r.b += errval * bFactor

        // Reset when N reaches RESET value per ITU-T.87 Section A.6.2
        // Reset check happens BEFORE N is incremented (per standard).
        if r.n >= resetThreshold {
            r.a >>= 1
            r.b >>= 1
            // Use max(..., 1) to ensure N doesn't become zero after the right-shift.
            r.n = max(r.n >> 1, 1)
        }

        // Increment N (after reset check, before bias correction)
        r.n += 1

        // Bias correction per ITU-T.87 Section A.6.3 (code segment A.13).
        // Inner clamping uses max/min instead of nested branches to reduce
        // branch-predictor pressure in the hot encoding loop.
        if r.b + r.n <= 0 {
            r.b = max(r.b + r.n, 1 - r.n)
            r.c = max(r.c - 1, -128)
        } else if r.b > 0 {
            r.b = min(r.b - r.n, 0)
            r.c = min(r.c + 1, 127)
        }

        contexts[contextIndex] = r
    }

    // MARK: - Golomb Parameter Calculation

    @inline(__always)
    private static func golombParameter(a: Int, n: Int) -> Int {
        guard n > 0 else { return 0 }
        guard a > n else { return 0 }

        // Fast computation using integer bit widths:
        // floor(log2(a)) − floor(log2(n)) gives a lower bound on k;
        // at most one additional increment is ever needed.
        let logA = Int.bitWidth - 1 - a.leadingZeroBitCount  // floor(log2(a))
        let logN = Int.bitWidth - 1 - n.leadingZeroBitCount  // floor(log2(n))
        var k = logA - logN
        if n << k < a { k += 1 }
        return min(k, 16)
    }

    internal func pixelCodingState(contextIndex: Int) -> (biasC: Int, k: Int, errorCorrection: Int) {
        guard contextIndex >= 0 && contextIndex < Self.regularContextCount else {
            return (0, 0, 0)
        }
        let r = contexts[contextIndex]
        let k = Self.golombParameter(a: r.a, n: r.n)
        let errorCorrection = (k == 0 && near == 0 && (2 * r.b + r.n - 1) < 0) ? -1 : 0
        return (r.c, k, errorCorrection)
    }

    // MARK: - Run-Length Context

    internal var currentRunIndex: Int {
        return runIndex
    }

    internal mutating func setRunIndex(_ index: Int) {
        runIndex = max(0, min(31, index))
    }

    internal mutating func decrementRunIndex() {
        if runIndex > 0 {
            runIndex -= 1
        }
    }

    // MARK: - Run Interruption Context Statistics

    internal func computeRunInterruptionGolombK(riType: Int = 0) -> Int {
        let idx = min(max(riType, 0), 1)
        let n = runInterruptionN[idx]
        let a = runInterruptionA[idx]
        guard n > 0 else { return 0 }
        let temp = a + (n >> 1) * idx
        var k = 0
        var threshold = n
        while threshold < temp && k < 32 {
            threshold <<= 1
            k += 1
        }
        return k
    }

    internal func computeRunInterruptionErrorValue(temp: Int, k: Int, riType: Int) -> Int {
        let idx = min(max(riType, 0), 1)
        let map = (temp & 1) != 0
        let errorValueAbs = (temp + (map ? 1 : 0)) / 2
        let nn = runInterruptionNN[idx]
        let n = runInterruptionN[idx]

        if (k != 0 || (2 * nn >= n)) == map {
            return -errorValueAbs
        }
        return errorValueAbs
    }

    internal mutating func updateRunInterruptionContext(errorValue: Int, eMappedErrorValue: Int, riType: Int) {
        let idx = min(max(riType, 0), 1)

        if errorValue < 0 {
            runInterruptionNN[idx] += 1
        }

        runInterruptionA[idx] += (eMappedErrorValue + 1 - idx) >> 1

        if runInterruptionN[idx] == parameters.reset {
            runInterruptionA[idx] >>= 1
            runInterruptionN[idx] >>= 1
            runInterruptionNN[idx] >>= 1
        }

        runInterruptionN[idx] += 1
    }


    internal func computeContextSign(q1: Int, q2: Int, q3: Int) -> Int {
        if q1 < 0 || (q1 == 0 && q2 < 0) || (q1 == 0 && q2 == 0 && q3 < 0) {
            return -1
        }
        return 1
    }
}
