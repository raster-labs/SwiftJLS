// SPDX-License-Identifier: MIT
// Copyright 2026 Raster Images Private Limited
// Scalar kernels adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc.
// See Documentation/Engineering/MigrationPreflight/scalar-provenance.json.
import Foundation

// Select the proof once at scan entry. Concrete validators let specialised
// kernels omit per-pixel optional dispatch and checks already proved by storage
// width or a prepass. These types never own sample memory or escape a borrow.
protocol JPEGLSSampleValidator {
    func validate(_ sample: Int) throws
}
struct JPEGLSPrevalidatedSamples: JPEGLSSampleValidator {
    @inline(__always) func validate(_ sample: Int) throws {}
}
struct JPEGLSMaximumSample: JPEGLSSampleValidator {
    let maximum: Int
    @inline(__always) func validate(_ sample: Int) throws {
        guard sample <= maximum else {
            throw CodecError(.invalidArgument, "Sample exceeds declared meaningful precision.")
        }
    }
}

struct JPEGLSScalarKernel {
    func encodeFlatRowsLossless<Reader: JPEGSampleReader>(
        buf: Reader,
        rowStride: Int,
        rowRange: Range<Int>,
        scanFirstRow: Int? = nil,
        sampleMaximum: Int? = nil,
        width: Int,
        regularMode: JPEGLSRegularMode,
        runMode: JPEGLSRunMode,
        context: inout JPEGLSContextModel,
        writer: inout JPEGLSBitstreamWriter,
        limit: Int,
        qbppBits: Int,
        checkpoint: () throws -> Void
    ) throws {
        if let sampleMaximum {
            try encodeFlatRowsLossless(buf: buf, rowStride: rowStride, rowRange: rowRange,
                scanFirstRow: scanFirstRow, sampleValidator: JPEGLSMaximumSample(maximum: sampleMaximum),
                width: width, regularMode: regularMode, runMode: runMode, context: &context,
                writer: &writer, limit: limit, qbppBits: qbppBits, checkpoint: checkpoint)
        } else {
            try encodeFlatRowsLossless(buf: buf, rowStride: rowStride, rowRange: rowRange,
                scanFirstRow: scanFirstRow, sampleValidator: JPEGLSPrevalidatedSamples(),
                width: width, regularMode: regularMode, runMode: runMode, context: &context,
                writer: &writer, limit: limit, qbppBits: qbppBits, checkpoint: checkpoint)
        }
    }

    func encodeFlatRowsLossless<Reader: JPEGSampleReader, Validator: JPEGLSSampleValidator>(
        buf: Reader, rowStride: Int, rowRange: Range<Int>, scanFirstRow: Int?, sampleValidator: Validator,
        width: Int, regularMode: JPEGLSRegularMode, runMode: JPEGLSRunMode,
        context: inout JPEGLSContextModel, writer: inout JPEGLSBitstreamWriter,
        limit: Int, qbppBits: Int, checkpoint: () throws -> Void
    ) throws {
        guard width > 0, rowStride >= width, rowRange.lowerBound >= 0,
              rowRange.upperBound > rowRange.lowerBound,
              try checkedAdd(checkedMultiply(rowRange.upperBound - 1, rowStride), width) <= buf.count else {
            throw CodecError(.incompatibleImageLayout, "Invalid scalar input extent.")
        }
        if let scalar = buf.scalarLayout {
            try encodeFlatRowsLossless(buf: scalar.view, rowStride: scalar.rowStride,
                rowRange: rowRange, scanFirstRow: scanFirstRow, sampleValidator: sampleValidator, width: width,
                regularMode: regularMode, runMode: runMode, context: &context,
                writer: &writer, limit: limit, qbppBits: qbppBits, checkpoint: checkpoint)
            return
        }
        if let native = buf.nativeLayout {
            try encodeFlatRowsLossless(buf: native, rowStride: rowStride, rowRange: rowRange,
                scanFirstRow: scanFirstRow, sampleValidator: sampleValidator, width: width,
                regularMode: regularMode, runMode: runMode, context: &context,
                writer: &writer, limit: limit, qbppBits: qbppBits, checkpoint: checkpoint)
            return
        }
        let firstRow = scanFirstRow ?? rowRange.lowerBound
        let t3 = regularMode.gradientTableOffset
        let negT3 = -t3
        let maxVal = regularMode.presetParameters.maxValue
        let rangeVal = regularMode.range
        let halfHigh = regularMode.halfRangeHigh
        let halfLow = regularMode.halfRangeLow
        let resetThresh = context.resetThreshold
        let limitThreshold = limit - qbppBits - 1
        let ctxBuffer = context.rawContextsBuffer

        try regularMode.gradientTable.withUnsafeBufferPointer { gradBuf in
            let gradPtr = gradBuf.baseAddress!
            try ctxBuffer.withUnsafeMutablePointerToElements { ctxPtr in
                var prevRowEdge = rowRange.lowerBound > firstRow + 1 ? Int(buf[(rowRange.lowerBound - 2) * rowStride]) : 0
                for row in rowRange {
                    try checkpoint(); try writer.checkLimit()
                    let rowBase = row &* rowStride
                    let prevBase = rowBase &- rowStride
                    let edgeForThisRow = prevRowEdge
                    if row > firstRow {
                        prevRowEdge = Int(buf[prevBase])
                    }
                    var col = 0
                    while col < width {
                        if (col & 255) == 0 && col != 0 { try checkpoint(); try writer.checkLimit() }
                        let a: Int, b: Int, c: Int, d: Int
                        if row == firstRow {
                            a = col == 0 ? 0 : Int(buf[rowBase &+ col &- 1])
                            b = 0; c = 0; d = 0
                        } else if col == 0 {
                            let top = Int(buf[prevBase])
                            a = top
                            b = top
                            c = edgeForThisRow
                            d = width > 1 ? Int(buf[prevBase &+ 1]) : top
                        } else {
                            a = Int(buf[rowBase &+ col &- 1])
                            b = Int(buf[prevBase &+ col])
                            c = Int(buf[prevBase &+ col &- 1])
                            d = col &+ 1 < width ? Int(buf[prevBase &+ col &+ 1]) : b
                        }

                        let q1 = Int(gradPtr[min(max(d &- b, negT3), t3) &+ t3])
                        let q2 = Int(gradPtr[min(max(b &- c, negT3), t3) &+ t3])
                        let q3 = Int(gradPtr[min(max(c &- a, negT3), t3) &+ t3])

                        if (q1 | q2 | q3) == 0 {
                            let runValue = a
                            let rv16 = UInt16(truncatingIfNeeded: runValue)
                            let rowEnd = rowBase &+ width
                            let start = rowBase &+ col
                            var i = start
                            while i < rowEnd {
                                if i != start { try checkpoint(); try writer.checkLimit() }
                                let end = min(rowEnd, i &+ 256)
                                i &+= buf.matchingPrefix(in: i..<end, to: rv16)
                                if i < end { break }
                            }
                            let actualRunLength = i &- start
                            let remainingInLine = width &- col

                            let encoded = runMode.encodeRunLength(
                                runLength: actualRunLength,
                                runIndex: context.currentRunIndex
                            )
                            writer.writeOnes(encoded.continuationBits)
                            let finalRunIndex = min(encoded.runIndex &+ encoded.continuationBits, 31)

                            if actualRunLength < remainingInLine {
                                writeRunTermination(encoded: encoded, writer: &writer)
                                let interruptionCol = col &+ actualRunLength
                                let interruptionActual = Int(buf[rowBase &+ interruptionCol])
                                try sampleValidator.validate(interruptionActual)
                                let encRb = row > firstRow ? Int(buf[prevBase &+ interruptionCol]) : 0

                                context.setRunIndex(finalRunIndex)
                                _ = writeRunInterruptionBits(
                                    interruptionValue: interruptionActual,
                                    runValue: runValue,
                                    rb: encRb,
                                    near: 0,
                                    context: &context,
                                    regularMode: regularMode,
                                    runMode: runMode,
                                    writer: &writer,
                                    limit: limit,
                                    qbppBits: qbppBits
                                )
                                context.setRunIndex(max(finalRunIndex &- 1, 0))
                                col = interruptionCol &+ 1
                            } else {
                                if encoded.remainder > 0 {
                                    writer.writeBits(1, count: 1)
                                }
                                col &+= actualRunLength
                                context.setRunIndex(finalRunIndex)
                            }
                        } else {
                            // Fused in-register regular-mode lossless step.
                            let actual = Int(buf[rowBase &+ col])
                            try sampleValidator.validate(actual)

                            let raw = (q1 &* 9 &+ q2) &* 9 &+ q3
                            let signMask = raw >> (Int.bitWidth - 1)
                            let ctxIdx = (raw ^ signMask) &- signMask
                            var r = ctxPtr[ctxIdx]

                            let k = JPEGLSContextModel.golombParameter(a: r.a, n: r.n)
                            let errorCorrection = (k == 0 && (2 &* r.b &+ r.n &- 1) < 0) ? -1 : 0

                            let maxAB = max(a, b)
                            let minAB = min(a, b)
                            let px = c >= maxAB ? minAB : (c <= minAB ? maxAB : (a &+ b &- c))
                            let correctedPrediction = max(0, min(maxVal, px &+ ((r.c ^ signMask) &- signMask)))

                            var errval = ((actual &- correctedPrediction) ^ signMask) &- signMask
                            if errval > halfHigh {
                                errval &-= rangeVal
                            } else if errval < halfLow {
                                errval &+= rangeVal
                            }

                            let correctedError = errval ^ errorCorrection
                            let mappedError = (correctedError << 1) ^ (correctedError >> (Int.bitWidth - 1))
                            let unaryLength = mappedError >> k
                            let remainder = mappedError & ((1 &<< k) &- 1)

                            if unaryLength >= limitThreshold {
                                writer.writeUnaryCode(limitThreshold)
                                writer.writeBits(UInt32(mappedError &- 1), count: qbppBits)
                            } else if unaryLength &+ 1 &+ k <= 32 {
                                writer.writeBits((UInt32(1) &<< k) | UInt32(remainder),
                                                 count: unaryLength &+ 1 &+ k)
                            } else {
                                writer.writeUnaryCode(unaryLength)
                                if k > 0 {
                                    writer.writeBits(UInt32(remainder), count: k)
                                }
                            }

                            r.a &+= abs(errval)
                            r.b &+= errval
                            if r.n >= resetThresh {
                                r.a >>= 1
                                r.b >>= 1
                                r.n = max(r.n >> 1, 1)
                            }
                            r.n &+= 1
                            if r.b &+ r.n <= 0 {
                                r.b = max(r.b &+ r.n, 1 &- r.n)
                                r.c = max(r.c &- 1, -128)
                            } else if r.b > 0 {
                                r.b = min(r.b &- r.n, 0)
                                r.c = min(r.c &+ 1, 127)
                            }
                            ctxPtr[ctxIdx] = r

                            col &+= 1
                        }
                    }
                }
            }
        }
    }

    /// Near-lossless prediction uses reconstructed neighbours. Two UInt16 rows
    /// are sufficient; original image storage remains borrowed and immutable.
    func encodeNearLossless<Reader: JPEGSampleReader>(buf: Reader, rowStride: Int, width: Int, height: Int,
                            near: Int, parameters: JPEGLSPresetParameters,
                            writer: inout JPEGLSBitstreamWriter, bits: Int,
                            checkpoint: () throws -> Void) throws {
        if let scalar = buf.scalarLayout {
            try encodeNearLossless(buf: scalar.view, rowStride: scalar.rowStride, width: width, height: height,
                near: near, parameters: parameters, writer: &writer, bits: bits, checkpoint: checkpoint)
            return
        }
        if let native = buf.nativeLayout {
            try encodeNearLossless(buf: native, rowStride: rowStride, width: width, height: height,
                near: near, parameters: parameters, writer: &writer, bits: bits, checkpoint: checkpoint)
            return
        }
        let regular = try JPEGLSRegularMode(parameters: parameters, near: near)
        let run = try JPEGLSRunMode(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)
        let coding = computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: bits)

        let t3 = regular.gradientTableOffset
        let negT3 = -t3
        let maxVal = parameters.maxValue
        let rangeVal = regular.range
        let halfHigh = regular.halfRangeHigh
        let halfLow = regular.halfRangeLow
        let qbppVal = near > 0 ? (2 &* near &+ 1) : 1
        let qbppRecip: UInt64 = near > 0 ? ((UInt64(1) &<< 32) / UInt64(qbppVal) &+ 1) : 0
        let wrapRangeVal = regular.wrapRange
        let resetThresh = context.resetThreshold
        let bFactor = context.bFactor
        let limit = coding.limit
        let qbppBits = coding.qbppBits
        let limitThreshold = limit &- qbppBits &- 1
        let ctxBuffer = context.rawContextsBuffer

        var rowArena = [UInt16](repeating: 0, count: width * 2)
        try rowArena.withUnsafeMutableBufferPointer { arenaBuf in
            let arenaBase = arenaBuf.baseAddress!
            var prevOffset = 0
            var currOffset = width
            var edge = 0

            try regular.gradientTable.withUnsafeBufferPointer { gradBuf in
                let gradPtr = gradBuf.baseAddress!
                try ctxBuffer.withUnsafeMutablePointerToElements { ctxPtr in
                    for y in 0..<height {
                        try checkpoint(); try writer.checkLimit()
                        let prevPtr = arenaBase + prevOffset
                        let rowPtr = arenaBase + currOffset
                        let rowRaw = UnsafeMutableRawPointer(rowPtr)
                        let srcRowBase = y &* rowStride
                        let oldEdge = edge
                        edge = Int(prevPtr[0])

                        var x = 0
                        while x < width {
                            if (x & 255) == 0 && x != 0 { try checkpoint(); try writer.checkLimit() }
                            let a = x == 0 ? Int(prevPtr[0]) : Int(rowPtr[x &- 1])
                            let b = Int(prevPtr[x])
                            let c = x == 0 ? oldEdge : Int(prevPtr[x &- 1])
                            let d = x &+ 1 < width ? Int(prevPtr[x &+ 1]) : b

                            let q1 = Int(gradPtr[min(max(d &- b, negT3), t3) &+ t3])
                            let q2 = Int(gradPtr[min(max(b &- c, negT3), t3) &+ t3])
                            let q3 = Int(gradPtr[min(max(c &- a, negT3), t3) &+ t3])

                            if (q1 | q2 | q3) == 0 {
                                let start = x
                                let lo16 = UInt16(truncatingIfNeeded: max(0, a &- near))
                                let hi16 = UInt16(truncatingIfNeeded: min(65535, a &+ near))
                                let srcEnd = srcRowBase &+ width
                                var srcPos = srcRowBase &+ x
                                while srcPos < srcEnd {
                                    if srcPos != (srcRowBase &+ start) { try checkpoint(); try writer.checkLimit() }
                                    let chunkStop = min(srcEnd, srcPos &+ 256)
                                    srcPos &+= buf.matchingNearPrefix(in: srcPos..<chunkStop, lo: lo16, hi: hi16)
                                    if srcPos < chunkStop { break }
                                }
                                let runLen = srcPos &- (srcRowBase &+ start)
                                x &+= runLen

                                if runLen > 0 {
                                    let rv16 = UInt16(truncatingIfNeeded: a)
                                    var f = start
                                    if f &+ 8 <= x {
                                        let vec8 = SIMD8<UInt16>(repeating: rv16)
                                        while f &+ 8 <= x {
                                            rowRaw.storeBytes(of: vec8, toByteOffset: f &* 2, as: SIMD8<UInt16>.self)
                                            f &+= 8
                                        }
                                    }
                                    while f < x {
                                        rowPtr[f] = rv16
                                        f &+= 1
                                    }
                                }

                                let encoded = run.encodeRunLength(runLength: runLen, runIndex: context.currentRunIndex)
                                writer.writeOnes(encoded.continuationBits)
                                let finalIndex = min(encoded.runIndex &+ encoded.continuationBits, 31)
                                context.setRunIndex(finalIndex)
                                if x < width {
                                    writeRunTermination(encoded: encoded, writer: &writer)
                                    let reconstructed = writeRunInterruptionBits(
                                        interruptionValue: Int(buf[srcRowBase &+ x]), runValue: a,
                                        rb: Int(prevPtr[x]), near: near, context: &context,
                                        regularMode: regular, runMode: run, writer: &writer,
                                        limit: limit, qbppBits: qbppBits)
                                    rowPtr[x] = UInt16(truncatingIfNeeded: reconstructed)
                                    context.setRunIndex(max(finalIndex &- 1, 0))
                                    x &+= 1
                                } else if encoded.remainder > 0 {
                                    writer.writeBits(1, count: 1)
                                }
                            } else {
                                // Fused in-register near-lossless regular-mode step
                                let actual = Int(buf[srcRowBase &+ x])
                                let raw = (q1 &* 9 &+ q2) &* 9 &+ q3
                                let signMask = raw >> (Int.bitWidth - 1)
                                let ctxIdx = (raw ^ signMask) &- signMask
                                var r = ctxPtr[ctxIdx]

                                let k = JPEGLSContextModel.golombParameter(a: r.a, n: r.n)
                                let errorCorrection = (near == 0 && k == 0 && (2 &* r.b &+ r.n &- 1) < 0) ? -1 : 0

                                let maxAB = max(a, b)
                                let minAB = min(a, b)
                                let px = c >= maxAB ? minAB : (c <= minAB ? maxAB : (a &+ b &- c))
                                let correctedPrediction = max(0, min(maxVal, px &+ ((r.c ^ signMask) &- signMask)))

                                let signNormalisedDiff = ((actual &- correctedPrediction) ^ signMask) &- signMask
                                var errval: Int
                                if near > 0 {
                                    if signNormalisedDiff >= 0 {
                                        errval = Int((UInt64(signNormalisedDiff &+ near) &* qbppRecip) >> 32)
                                    } else {
                                        errval = -Int((UInt64((-signNormalisedDiff) &+ near) &* qbppRecip) >> 32)
                                    }
                                } else {
                                    errval = signNormalisedDiff
                                }

                                if errval > halfHigh {
                                    errval &-= rangeVal
                                } else if errval < halfLow {
                                    errval &+= rangeVal
                                }

                                let correctedError = errval ^ errorCorrection
                                let mappedError = (correctedError << 1) ^ (correctedError >> (Int.bitWidth - 1))
                                let unaryLength = mappedError >> k
                                let remainder = mappedError & ((1 &<< k) &- 1)

                                if unaryLength >= limitThreshold {
                                    writer.writeUnaryCode(limitThreshold)
                                    writer.writeBits(UInt32(mappedError &- 1), count: qbppBits)
                                } else if unaryLength &+ 1 &+ k <= 32 {
                                    writer.writeBits((UInt32(1) &<< k) | UInt32(remainder),
                                                     count: unaryLength &+ 1 &+ k)
                                } else {
                                    writer.writeUnaryCode(unaryLength)
                                    if k > 0 {
                                        writer.writeBits(UInt32(remainder), count: k)
                                    }
                                }

                                let reconstructed: Int
                                if near == 0 {
                                    reconstructed = actual
                                } else {
                                    let quantisedError = (errval ^ signMask) &- signMask
                                    var rv = correctedPrediction &+ (quantisedError &* qbppVal)
                                    if rv < -near {
                                        rv &+= wrapRangeVal
                                    } else if rv > maxVal &+ near {
                                        rv &-= wrapRangeVal
                                    }
                                    reconstructed = max(0, min(maxVal, rv))
                                }
                                rowPtr[x] = UInt16(truncatingIfNeeded: reconstructed)

                                r.a &+= abs(errval)
                                r.b &+= errval &* bFactor
                                if r.n >= resetThresh {
                                    r.a >>= 1
                                    r.b >>= 1
                                    r.n = max(r.n >> 1, 1)
                                }
                                r.n &+= 1
                                if r.b &+ r.n <= 0 {
                                    r.b = max(r.b &+ r.n, 1 &- r.n)
                                    r.c = max(r.c &- 1, -128)
                                } else if r.b > 0 {
                                    r.b = min(r.b &- r.n, 0)
                                    r.c = min(r.c &+ 1, 127)
                                }
                                ctxPtr[ctxIdx] = r

                                x &+= 1
                            }
                        }
                        swap(&prevOffset, &currOffset)
                    }
                }
            }
        }
    }

    func encodePixel(
        actual: Int,
        a: Int,
        b: Int,
        c: Int,
        q1: Int,
        q2: Int,
        q3: Int,
        regularMode: JPEGLSRegularMode,
        context: inout JPEGLSContextModel,
        writer: inout JPEGLSBitstreamWriter,
        limit: Int,
        qbppBits: Int
    ) -> Int {
        // Regular mode encoding, reusing the quantized gradients the scan
        // loop already computed for the run-mode test.
        let (contextIndex, sign) = context.computeContextIndexAndSign(q1: q1, q2: q2, q3: q3)
        let encodedPixel = regularMode.encodePixel(
            actual: actual,
            a: a,
            b: b,
            c: c,
            contextIndex: contextIndex,
            sign: sign,
            context: context
        )

        // Write Golomb-Rice encoded bits
        writeRegularModeBits(encodedPixel, to: &writer, limit: limit, qbppBits: qbppBits)

        // Update context
        context.updateContext(
            contextIndex: encodedPixel.contextIndex,
            predictionError: encodedPixel.error,
            sign: encodedPixel.sign
        )

        return encodedPixel.reconstructedValue
    }

    private func writeRegularModeBits(
        _ encoded: EncodedPixel,
        to writer: inout JPEGLSBitstreamWriter,
        limit: Int,
        qbppBits: Int
    ) {
        let limitThreshold = limit - qbppBits - 1
        if encoded.unaryLength >= limitThreshold {
            // Limited binary code: write limitThreshold zeros + 1, then MErrval−1 in qbppBits.
            writer.writeUnaryCode(limitThreshold)
            writer.writeBits(UInt32(encoded.mappedError - 1), count: qbppBits)
        } else if encoded.unaryLength + 1 + encoded.golombK <= 32 {
            // A short Golomb word fits one accumulator update. Leading zeros
            // come from the count; the one bit precedes the k-bit remainder.
            writer.writeBits((UInt32(1) << encoded.golombK) | UInt32(encoded.remainder),
                count: encoded.unaryLength + 1 + encoded.golombK)
        } else {
            // Standard Golomb-Rice: write unaryLength zeros + 1, then k-bit remainder.
            writer.writeUnaryCode(encoded.unaryLength)
            if encoded.golombK > 0 {
                writer.writeBits(UInt32(encoded.remainder), count: encoded.golombK)
            }
        }
    }

    func writeRunInterruptionBits(
        interruptionValue: Int,
        runValue: Int,
        rb: Int,
        near: Int,
        context: inout JPEGLSContextModel,
        regularMode: JPEGLSRegularMode,
        runMode: JPEGLSRunMode,
        writer: inout JPEGLSBitstreamWriter,
        limit: Int,
        qbppBits: Int,
        overrideRiType: Int? = nil
    ) -> Int {
        let ra = runValue
        let riType = overrideRiType ?? ((abs(ra - rb) <= near) ? 1 : 0)

        // Prediction and error per ITU-T.87
        let prediction: Int
        let rawError: Int
        if riType == 1 {
            prediction = ra
            rawError = interruptionValue - prediction
        } else {
            prediction = rb
            let raw = interruptionValue - prediction
            rawError = (rb >= ra) ? raw : -raw
        }

        // Quantize and modular-reduce the interruption error per ITU-T.87.
        let maxVal = regularMode.presetParameters.maxValue
        let qbpp = near > 0 ? regularMode.qbpp : 1
        let range = regularMode.range

        // Quantize for near-lossless (identity for lossless)
        var reducedError: Int
        if near > 0 {
            let qbppRecip = (UInt64(1) << 32) / UInt64(qbpp) + 1
            if rawError >= 0 {
                reducedError = Int((UInt64(rawError &+ near) &* qbppRecip) >> 32)
            } else {
                reducedError = -Int((UInt64((-rawError) &+ near) &* qbppRecip) >> 32)
            }
        } else {
            reducedError = rawError
        }

        // Modular reduction with RANGE
        if reducedError < 0 { reducedError &+= range }
        if reducedError >= ((range &+ 1) >> 1) { reducedError &-= range }

        let k = context.computeRunInterruptionGolombK(riType: riType)
        let map = context.computeRunInterruptionMap(errorValue: reducedError, k: k, riType: riType)

        // Map to the non-negative interruption code per ITU-T.87:
        // e_mapped = 2 * |error| - riType - map
        let eMappedErrorValue = (abs(reducedError) &<< 1) &- riType &- (map ? 1 : 0)

        // Adjusted limit for run interruption
        let j = runMode.computeJ(runIndex: context.currentRunIndex)
        let adjustedLimit = limit &- j &- 1
        let limitThreshold = adjustedLimit &- qbppBits &- 1

        let unaryLength = eMappedErrorValue >> k
        let remainder = eMappedErrorValue & ((1 &<< k) &- 1)
        if unaryLength >= limitThreshold {
            writer.writeUnaryCode(limitThreshold)
            writer.writeBits(UInt32(eMappedErrorValue &- 1), count: qbppBits)
        } else if unaryLength &+ 1 &+ k <= 32 {
            writer.writeBits((UInt32(1) &<< k) | UInt32(remainder), count: unaryLength &+ 1 &+ k)
        } else {
            writer.writeUnaryCode(unaryLength)
            if k > 0 {
                writer.writeBits(UInt32(remainder), count: k)
            }
        }

        context.updateRunInterruptionContext(
            errorValue: reducedError,
            eMappedErrorValue: eMappedErrorValue,
            riType: riType
        )

        // Compute what the decoder will reconstruct
        let dequantized = reducedError &* qbpp
        let signedError = (riType == 1 || rb >= ra) ? dequantized : -dequantized
        var rv = prediction &+ signedError
        let wrapRange = regularMode.wrapRange
        if rv < -near { rv &+= wrapRange }
        else if rv > maxVal &+ near { rv &-= wrapRange }
        return max(0, min(maxVal, rv))
    }

    @inline(__always)
    func writeRunTermination(
        encoded: EncodedRun,
        writer: inout JPEGLSBitstreamWriter
    ) {
        if encoded.j > 0 {
            writer.writeBits(UInt32(encoded.remainder), count: encoded.j &+ 1)
        } else {
            writer.writeBits(0, count: 1)
        }
    }

    func computeGolombLimitInternal(
        parameters: JPEGLSPresetParameters,
        near: Int,
        bitsPerSample: Int
    ) -> (limit: Int, qbppBits: Int) {
        let range: Int
        if near == 0 {
            range = parameters.maxValue + 1
        } else {
            let qstep = 2 * near + 1
            range = (parameters.maxValue + 2 * near) / qstep + 1
        }
        var qbppBits = 0
        var r = range - 1
        while r > 0 {
            qbppBits += 1
            r >>= 1
        }
        qbppBits = max(qbppBits, 1)
        let bpp = max(2, Int.bitWidth - parameters.maxValue.leadingZeroBitCount)
        let limit = 2 * (bpp + max(8, bpp))
        return (limit, qbppBits)
    }

    func writeFrameHeaderInternal(
        _ frameHeader: JPEGLSFrameHeader,
        to writer: inout JPEGLSBitstreamWriter
    ) throws {
        writer.writeMarker(.startOfFrameJPEGLS)

        // Length: 8 + 3 * componentCount
        let length = UInt16(8 + 3 * frameHeader.componentCount)
        writer.writeUInt16(length)

        // Precision (bits per sample)
        writer.writeByte(UInt8(frameHeader.bitsPerSample))

        // Dimensions — use 0 for any dimension > 65535 (encoded in preceding LSE type 4)
        writer.writeUInt16(UInt16(frameHeader.height > 65535 || frameHeader.width > 65535 ? 0 : frameHeader.height))
        writer.writeUInt16(UInt16(frameHeader.height > 65535 || frameHeader.width > 65535 ? 0 : frameHeader.width))

        // Component count
        writer.writeByte(UInt8(frameHeader.componentCount))

        // Component specifications
        for component in frameHeader.components {
            writer.writeByte(component.id)
            // Sampling factors combined into single byte: (H << 4) | V
            let samplingByte = (component.horizontalSamplingFactor << 4) | component.verticalSamplingFactor
            writer.writeByte(samplingByte)
            writer.writeByte(0)  // Quantization table ID (unused in JPEG-LS, always 0)
        }
        if frameHeader.width > 65535 || frameHeader.height > 65535 {
            writer.writeMarker(.jpegLSExtension); writer.writeUInt16(12)
            writer.writeByte(4); writer.writeByte(4)
            for value in [frameHeader.height, frameHeader.width] {
                writer.writeUInt16(UInt16(value >> 16)); writer.writeUInt16(UInt16(value & 65535))
            }
        }

    }

    func writeScanHeaderInternal(
        _ scanHeader: JPEGLSScanHeader,
        to writer: inout JPEGLSBitstreamWriter
    ) throws {
        writer.writeMarker(.startOfScan)

        // Length: 6 + 2 * componentCount
        let length = UInt16(6 + 2 * scanHeader.componentCount)
        writer.writeUInt16(length)

        // Component count
        writer.writeByte(UInt8(scanHeader.componentCount))

        // Component selectors
        for component in scanHeader.components {
            writer.writeByte(component.id)
            // Tdi field: mapping table ID (0 = no mapping table) per ITU-T.87 §5.1.2.
            writer.writeByte(component.mappingTableID)
        }

        // NEAR parameter
        writer.writeByte(UInt8(scanHeader.near))

        // Interleave mode (ILV)
        let ilv: UInt8 = switch scanHeader.interleaveMode {
        case .none: 0
        case .line: 1
        case .sample: 2
        }
        writer.writeByte(ilv)

        // Point transform (0 for lossless)
        writer.writeByte(UInt8(scanHeader.pointTransform))
    }

    func decodeFlatRegion<Writer: JPEGSampleWriter>(
        into buf: Writer,
        rowStride: Int,
        reader: JPEGLSBitstreamReader,
        rows: Int,
        width: Int,
        parameters: JPEGLSPresetParameters,
        near: Int,
        limit: Int,
        qbppBits: Int,
        checkpoint: () throws -> Void
    ) throws {
        var mutableReader = reader
        try decodeFlatRegion(
            into: buf, rowStride: rowStride, reader: &mutableReader, rows: rows, width: width,
            parameters: parameters, near: near, limit: limit, qbppBits: qbppBits, checkpoint: checkpoint
        )
    }

    func decodeFlatRegion<Writer: JPEGSampleWriter, Reader: JPEGLSBitSource>(
        into buf: Writer,
        rowStride: Int,
        reader: inout Reader,
        rows: Int,
        width: Int,
        parameters: JPEGLSPresetParameters,
        near: Int,
        limit: Int,
        qbppBits: Int,
        sharedDecoder: JPEGLSRegularModeDecoder? = nil,
        sharedRunDecoder: JPEGLSRunModeDecoder? = nil,
        checkpoint: () throws -> Void
    ) throws {
        guard rows > 0, width > 0, rowStride >= width,
              try checkedAdd(checkedMultiply(rows - 1, rowStride), width) <= buf.count else {
            throw CodecError(.incompatibleImageLayout, "Invalid scalar output extent.")
        }
        if let native = buf.nativeLayout {
            try decodeFlatRegion(
                into: native, rowStride: rowStride, reader: &reader, rows: rows, width: width,
                parameters: parameters, near: near, limit: limit, qbppBits: qbppBits,
                sharedDecoder: sharedDecoder, sharedRunDecoder: sharedRunDecoder, checkpoint: checkpoint
            )
            return
        }
        let decoder = try sharedDecoder ?? JPEGLSRegularModeDecoder(parameters: parameters, near: near)
        let runDecoder = try sharedRunDecoder ?? JPEGLSRunModeDecoder(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)

        let limitThreshold = limit - qbppBits - 1
        guard (1...16).contains(qbppBits), limitThreshold > 0 else {
            throw CodecError(.malformedInput, "Invalid Golomb coding state.")
        }
        let ctxBuffer = context.rawContextsBuffer

        try decoder.gradientTable.withUnsafeBufferPointer { gradBuf in
            let gradPtr = gradBuf.baseAddress!
            try ctxBuffer.withUnsafeMutablePointerToElements { ctxPtr in
                var prevRowEdge = 0
                for row in 0..<rows {
                    try checkpoint()
                    let rowBase = row &* rowStride
                    let prevBase = rowBase &- rowStride
                    let edgeForThisRow = prevRowEdge
                    if row > 0 {
                        prevRowEdge = Int(buf[prevBase])
                    }
                    try decodeRowCore(
                        into: buf, rowStride: rowStride, row: row, width: width,
                        edgeForThisRow: edgeForThisRow, reader: &reader, decoder: decoder,
                        runDecoder: runDecoder, context: &context, gradPtr: gradPtr, ctxPtr: ctxPtr,
                        parameters: parameters, near: near, limit: limit, limitThreshold: limitThreshold,
                        qbppBits: qbppBits, checkpointMask: 255, checkpoint: checkpoint
                    )
                }
            }
        }
    }

    @inline(__always)
    func decodeRow<Writer: JPEGSampleWriter>(
        into buf: Writer, rowStride: Int,
        row: Int, width: Int, edgeForThisRow: Int, reader: JPEGLSBitstreamReader,
        decoder: JPEGLSRegularModeDecoder, runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel, parameters: JPEGLSPresetParameters,
        near: Int, limit: Int, qbppBits: Int, checkpointMask: Int = 255,
        checkpoint: () throws -> Void
    ) throws {
        var mutableReader = reader
        try decodeRow(
            into: buf, rowStride: rowStride, row: row, width: width,
            edgeForThisRow: edgeForThisRow, reader: &mutableReader, decoder: decoder,
            runDecoder: runDecoder, context: &context, parameters: parameters,
            near: near, limit: limit, qbppBits: qbppBits, checkpointMask: checkpointMask,
            checkpoint: checkpoint
        )
    }

    /// A scan row shares adaptive contexts with the preceding scan rows.
    /// The caller supplies the per-component left boundary and run index.
    @inline(__always)
    func decodeRow<Writer: JPEGSampleWriter, Reader: JPEGLSBitSource>(
        into buf: Writer, rowStride: Int,
        row: Int, width: Int, edgeForThisRow: Int, reader: inout Reader,
        decoder: JPEGLSRegularModeDecoder, runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel, parameters: JPEGLSPresetParameters,
        near: Int, limit: Int, qbppBits: Int, checkpointMask: Int = 255,
        checkpoint: () throws -> Void
    ) throws {
        if let native = buf.nativeLayout {
            try decodeRow(
                into: native, rowStride: rowStride, row: row, width: width,
                edgeForThisRow: edgeForThisRow, reader: &reader, decoder: decoder, runDecoder: runDecoder,
                context: &context, parameters: parameters, near: near, limit: limit,
                qbppBits: qbppBits, checkpointMask: checkpointMask, checkpoint: checkpoint
            )
            return
        }

        let limitThreshold = limit - qbppBits - 1
        guard (1...16).contains(qbppBits), limitThreshold > 0 else {
            throw CodecError(.malformedInput, "Invalid Golomb coding state.")
        }
        let ctxBuffer = context.rawContextsBuffer

        try decoder.gradientTable.withUnsafeBufferPointer { gradBuf in
            let gradPtr = gradBuf.baseAddress!
            try ctxBuffer.withUnsafeMutablePointerToElements { ctxPtr in
                try decodeRowCore(
                    into: buf, rowStride: rowStride, row: row, width: width,
                    edgeForThisRow: edgeForThisRow, reader: &reader, decoder: decoder,
                    runDecoder: runDecoder, context: &context, gradPtr: gradPtr, ctxPtr: ctxPtr,
                    parameters: parameters, near: near, limit: limit, limitThreshold: limitThreshold,
                    qbppBits: qbppBits, checkpointMask: checkpointMask, checkpoint: checkpoint
                )
            }
        }
    }

    @inline(__always)
    private func decodeRowCore<Writer: JPEGSampleWriter, Reader: JPEGLSBitSource>(
        into buf: Writer, rowStride: Int,
        row: Int, width: Int, edgeForThisRow: Int, reader: inout Reader,
        decoder: JPEGLSRegularModeDecoder, runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel,
        gradPtr: UnsafePointer<Int8>,
        ctxPtr: UnsafeMutablePointer<JPEGLSContextModel.ContextRecord>,
        parameters: JPEGLSPresetParameters,
        near: Int, limit: Int, limitThreshold: Int, qbppBits: Int, checkpointMask: Int,
        checkpoint: () throws -> Void
    ) throws {
        let maxMappedError = 2 << qbppBits
        let t3 = decoder.gradientTableOffset
        let negT3 = -t3
        let maxVal = parameters.maxValue
        let qbppVal = decoder.qbpp
        let wrapRangeVal = decoder.wrapRange
        let resetThresh = context.resetThreshold
        let bFactor = context.bFactor
        let rowBase = row &* rowStride
        let prevBase = rowBase &- rowStride

        do {
            do {
                var col = 0
                while col < width {
                    if (col & checkpointMask) == 0 && col != 0 { try checkpoint() }
                    let a: Int, b: Int, c: Int, d: Int
                    if row == 0 {
                        a = col == 0 ? 0 : Int(buf[rowBase &+ col &- 1])
                        b = 0; c = 0; d = 0
                    } else if col == 0 {
                        let top = Int(buf[prevBase])
                        a = top
                        b = top
                        c = edgeForThisRow
                        d = width > 1 ? Int(buf[prevBase &+ 1]) : top
                    } else {
                        a = Int(buf[rowBase &+ col &- 1])
                        b = Int(buf[prevBase &+ col])
                        c = Int(buf[prevBase &+ col &- 1])
                        d = col &+ 1 < width ? Int(buf[prevBase &+ col &+ 1]) : b
                    }

                    let q1 = Int(gradPtr[min(max(d &- b, negT3), t3) &+ t3])
                    let q2 = Int(gradPtr[min(max(b &- c, negT3), t3) &+ t3])
                    let q3 = Int(gradPtr[min(max(c &- a, negT3), t3) &+ t3])

                    if (q1 | q2 | q3) == 0 {
                        let remainingInLine = width &- col
                        let runLength = try readRunLength(
                            reader: &reader,
                            runDecoder: runDecoder,
                            context: &context,
                            remainingInLine: remainingInLine
                        )
                        if runLength > 0 {
                            let rv = UInt16(truncatingIfNeeded: a)
                            let start = rowBase &+ col
                            if runLength == 1 {
                                buf[start] = rv
                            } else if runLength == 2 {
                                buf[start] = rv
                                buf[start &+ 1] = rv
                            } else {
                                let end = start &+ runLength
                                if runLength <= 256 {
                                    buf.fill(rv, range: start..<end)
                                } else {
                                    for first in stride(from: start, to: end, by: 256) {
                                        try checkpoint()
                                        buf.fill(rv, range: first..<min(end, first &+ 256))
                                    }
                                }
                            }
                            col &+= runLength
                        }

                        if runLength < remainingInLine {
                            let ra = a
                            let rb = row > 0 ? Int(buf[prevBase &+ col]) : 0
                            let riType = (abs(ra - rb) <= near) ? 1 : 0
                            let k = context.computeRunInterruptionGolombK(riType: riType)
                            let j = runDecoder.computeJ(runIndex: context.currentRunIndex)
                            let adjustedLimit = limit &- j &- 1
                            let eMappedErrorValue = try readGolombCode(
                                reader: &reader, k: k, limit: adjustedLimit, qbppBits: qbppBits
                            )
                            let errorValue = context.computeRunInterruptionErrorValue(
                                temp: eMappedErrorValue &+ riType, k: k, riType: riType
                            )
                            let sample: Int
                            if riType == 1 {
                                sample = runDecoder.reconstructSample(prediction: ra, error: errorValue)
                            } else {
                                let signCorrectedError = errorValue * (rb >= ra ? 1 : -1)
                                sample = runDecoder.reconstructSample(prediction: rb, error: signCorrectedError)
                            }
                            context.updateRunInterruptionContext(
                                errorValue: errorValue,
                                eMappedErrorValue: eMappedErrorValue,
                                riType: riType
                            )
                            context.decrementRunIndex()

                            buf[rowBase &+ col] = UInt16(truncatingIfNeeded: sample)
                            col &+= 1
                        }
                    } else {
                        // Fused in-register regular-mode decode step.
                        let raw = (q1 &* 9 &+ q2) &* 9 &+ q3
                        let signMask = raw >> (Int.bitWidth - 1)
                        let ctxIdx = (raw ^ signMask) &- signMask
                        var r = ctxPtr[ctxIdx]

                        let k = JPEGLSContextModel.golombParameter(a: r.a, n: r.n)
                        let errorCorrection = (k == 0 && near == 0 && (2 &* r.b &+ r.n &- 1) < 0) ? -1 : 0

                        let unaryCount = try reader.readUnaryCount(maximum: limitThreshold)
                        let mappedError: Int
                        if unaryCount >= limitThreshold {
                            mappedError = Int(try reader.readBits(qbppBits)) &+ 1
                        } else {
                            let rem = k > 0 ? Int(try reader.readBits(k)) : 0
                            mappedError = (unaryCount &<< k) | rem
                            guard mappedError <= maxMappedError else {
                                throw CodecError(.malformedInput, "Golomb value exceeds the bounded coding range.")
                            }
                        }

                        let signAdjustedError = ((mappedError >> 1) ^ -(mappedError & 1)) ^ errorCorrection
                        let rawError = (signAdjustedError ^ signMask) &- signMask

                        let maxAB = max(a, b)
                        let minAB = min(a, b)
                        let px = c >= maxAB ? minAB : (c <= minAB ? maxAB : (a &+ b &- c))
                        let correctedPrediction = max(0, min(maxVal, px &+ ((r.c ^ signMask) &- signMask)))

                        var sample = correctedPrediction &+ (near > 0 ? rawError &* qbppVal : rawError)
                        if sample < -near {
                            sample &+= wrapRangeVal
                        } else if sample > maxVal &+ near {
                            sample &-= wrapRangeVal
                        }
                        sample = max(0, min(maxVal, sample))

                        r.a &+= abs(signAdjustedError)
                        r.b &+= signAdjustedError &* bFactor
                        if r.n >= resetThresh {
                            r.a >>= 1
                            r.b >>= 1
                            r.n = max(r.n >> 1, 1)
                        }
                        r.n &+= 1
                        if r.b &+ r.n <= 0 {
                            r.b = max(r.b &+ r.n, 1 &- r.n)
                            r.c = max(r.c &- 1, -128)
                        } else if r.b > 0 {
                            r.b = min(r.b &- r.n, 0)
                            r.c = min(r.c &+ 1, 127)
                        }
                        ctxPtr[ctxIdx] = r

                        buf[rowBase &+ col] = UInt16(truncatingIfNeeded: sample)
                        col &+= 1
                    }
                }
            }
        }
    }

    func decodeSinglePixel(
        reader: JPEGLSBitstreamReader,
        decoder: JPEGLSRegularModeDecoder,
        runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel,
        a: Int, b: Int, c: Int,
        q1: Int, q2: Int, q3: Int,
        parameters: JPEGLSPresetParameters,
        near: Int,
        limit: Int,
        qbppBits: Int
    ) throws -> Int {
        var mutableReader = reader
        return try decodeSinglePixel(
            reader: &mutableReader, decoder: decoder, runDecoder: runDecoder, context: &context,
            a: a, b: b, c: c, q1: q1, q2: q2, q3: q3, parameters: parameters,
            near: near, limit: limit, qbppBits: qbppBits
        )
    }

    @inline(__always)
    func decodeSinglePixel<Reader: JPEGLSBitSource>(
        reader: inout Reader,
        decoder: JPEGLSRegularModeDecoder,
        runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel,
        a: Int, b: Int, c: Int,
        q1: Int, q2: Int, q3: Int,
        parameters: JPEGLSPresetParameters,
        near: Int,
        limit: Int,
        qbppBits: Int
    ) throws -> Int {
        let (contextIndex, sign) = context.computeContextIndexAndSign(q1: q1, q2: q2, q3: q3)
        let (biasC, k, errorCorrection) = context.pixelCodingState(contextIndex: contextIndex)
        let mappedError = try readGolombCode(reader: &reader, k: k, limit: limit, qbppBits: qbppBits)
        let result = decoder.decodePixel(
            mappedError: mappedError,
            a: a, b: b, c: c,
            contextIndex: contextIndex,
            sign: sign,
            biasC: biasC,
            errorCorrection: errorCorrection
        )
        context.updateContext(
            contextIndex: contextIndex,
            predictionError: result.error,
            sign: result.sign
        )
        return result.sample
    }

    func readGolombCode(
        reader: JPEGLSBitstreamReader,
        k: Int,
        limit: Int,
        qbppBits: Int
    ) throws -> Int {
        var mutableReader = reader
        return try readGolombCode(reader: &mutableReader, k: k, limit: limit, qbppBits: qbppBits)
    }

    @inline(__always)
    func readGolombCode<Reader: JPEGLSBitSource>(
        reader: inout Reader,
        k: Int,
        limit: Int,
        qbppBits: Int
    ) throws -> Int {
        let limitThreshold = limit - qbppBits - 1
        guard k >= 0, k <= 31, (1...16).contains(qbppBits), limitThreshold > 0 else {
            throw CodecError(.malformedInput, "Invalid Golomb coding state.")
        }
        let unaryCount = try reader.readUnaryCount(maximum: limitThreshold)
        if unaryCount >= limitThreshold {
            let rawValue = Int(try reader.readBits(qbppBits))
            return rawValue + 1
        }
        let remainder = k > 0 ? Int(try reader.readBits(k)) : 0
        let mapped = (unaryCount << k) | remainder
        guard mapped <= 2 << qbppBits else {
            throw CodecError(.malformedInput, "Golomb value exceeds the bounded coding range.")
        }
        return mapped
    }

    func readRunLength(
        reader: JPEGLSBitstreamReader,
        runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel,
        remainingInLine: Int
    ) throws -> Int {
        var mutableReader = reader
        return try readRunLength(
            reader: &mutableReader, runDecoder: runDecoder, context: &context, remainingInLine: remainingInLine
        )
    }

    @inline(__always)
    func readRunLength<Reader: JPEGLSBitSource>(
        reader: inout Reader,
        runDecoder: JPEGLSRunModeDecoder,
        context: inout JPEGLSContextModel,
        remainingInLine: Int
    ) throws -> Int {
        var runLength = 0
        var runIndex = context.currentRunIndex

        while true {
            let bit = try reader.readSingleBit()
            if bit == 0 {
                break
            }
            let j = runDecoder.computeJ(runIndex: runIndex)
            let blockSize = 1 &<< j
            let count = min(blockSize, remainingInLine &- runLength)
            runLength &+= count

            if count == blockSize && runIndex < 31 {
                runIndex &+= 1
            }
            if runLength >= remainingInLine {
                break
            }
        }

        if runLength < remainingInLine {
            let j = runDecoder.computeJ(runIndex: runIndex)
            let remainder = j > 0 ? Int(try reader.readBits(j)) : 0
            guard remainder < remainingInLine - runLength else {
                throw CodecError(.malformedInput, "Interrupted run exceeds the scan line.")
            }
            runLength += remainder
        }

        context.setRunIndex(runIndex)
        return runLength
    }
}
