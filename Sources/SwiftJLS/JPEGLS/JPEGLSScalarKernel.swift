// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Scalar kernels adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc.
// See Documentation/Engineering/MigrationPreflight/scalar-provenance.json.
import Foundation

struct JPEGLSScalarKernel {
    func encodeFlatRowsLossless<Reader: JPEGSampleReader>(
        buf: Reader,
        rowStride: Int,
        rowRange: Range<Int>,
        width: Int,
        regularMode: JPEGLSRegularMode,
        runMode: JPEGLSRunMode,
        context: inout JPEGLSContextModel,
        writer: JPEGLSBitstreamWriter,
        limit: Int,
        qbppBits: Int,
        checkpoint: () throws -> Void
    ) throws {
        guard width > 0, rowStride >= width, rowRange.lowerBound >= 0,
              rowRange.upperBound > rowRange.lowerBound,
              try checkedAdd(checkedMultiply(rowRange.upperBound - 1, rowStride), width) <= buf.count else {
            throw CodecError(.incompatibleImageLayout, "Invalid scalar input extent.")
        }
        do {
            var prevRowEdge = 0
            let firstRow = rowRange.lowerBound
            for row in rowRange {
                try checkpoint()
                // Note: RUNindex is NOT reset per line. Per ITU-T.87 §A.7.1,
                // RUNindex persists across scan lines; it is only initialised to 0 at scan start.
                let rowBase = row * rowStride
                let prevBase = rowBase - rowStride
                let edgeForThisRow = prevRowEdge
                if row > firstRow {
                    prevRowEdge = Int(buf[prevBase])
                }
                var col = 0
                while col < width {
                    if col & 255 == 0 { try checkpoint() }
                    // Causal neighbours per ITU-T.87 §3.2 (same boundary
                    // semantics as the general path). The first row of the
                    // range uses row-0 semantics (zero previous line).
                    let actual = Int(buf[rowBase + col])
                    let a: Int, b: Int, c: Int, d: Int
                    if row == firstRow {
                        a = col == 0 ? 0 : Int(buf[rowBase + col - 1])
                        b = 0; c = 0; d = 0
                    } else if col == 0 {
                        let top = Int(buf[prevBase])
                        a = top
                        b = top
                        c = edgeForThisRow
                        d = width > 1 ? Int(buf[prevBase + 1]) : top
                    } else {
                        a = Int(buf[rowBase + col - 1])
                        b = Int(buf[prevBase + col])
                        c = Int(buf[prevBase + col - 1])
                        d = col + 1 < width ? Int(buf[prevBase + col + 1]) : b
                    }

                    // Check for run mode: all quantized gradients are zero
                    let (d1, d2, d3) = regularMode.computeGradients(a: a, b: b, c: c, d: d)
                    let q1 = regularMode.quantizeGradient(d1)
                    let q2 = regularMode.quantizeGradient(d2)
                    let q3 = regularMode.quantizeGradient(d3)

                    if q1 == 0 && q2 == 0 && q3 == 0 {
                        // Run mode: scan the rest of the row for the run value
                        // (exact equality — lossless) with a 4-way unrolled test.
                        let runValue = a
                        let rv16 = UInt16(truncatingIfNeeded: runValue)
                        let rowEnd = rowBase + width
                        var i = rowBase + col
                        while i + 4 <= rowEnd {
                            if (i - rowBase - col) & 255 == 0 { try checkpoint() }
                            if !buf.fourEqual(at: i, to: rv16) {
                                break
                            }
                            i += 4
                        }
                        while i < rowEnd && buf[i] == rv16 {
                            i += 1
                        }
                        let actualRunLength = i - (rowBase + col)
                        let remainingInLine = width - col

                        // Encode run length
                        let encoded = runMode.encodeRunLength(
                            runLength: actualRunLength,
                            runIndex: context.currentRunIndex
                        )

                        // Write continuation bits (1s)
                        writer.writeOnes(encoded.continuationBits)

                        // Compute finalRunIndex now so it can be used for the interruption
                        // pixel's adjustedLimit (matching the decoder, which uses the
                        // post-continuation run index when computing J for the limit).
                        let finalRunIndex = min(encoded.runIndex + encoded.continuationBits, 31)

                        if actualRunLength < remainingInLine {
                            // Run was interrupted — write termination and remainder.
                            writeRunTermination(encoded: encoded, writer: writer)

                            let interruptionCol = col + actualRunLength
                            let interruptionActual = Int(buf[rowBase + interruptionCol])
                            let encRb = row > firstRow ? Int(buf[prevBase + interruptionCol]) : 0

                            // Per ITU-T.87: use finalRunIndex (post-continuation)
                            // for J when computing adjustedLimit in the interruption pixel.
                            context.setRunIndex(finalRunIndex)
                            _ = writeRunInterruptionBits(
                                interruptionValue: interruptionActual,
                                runValue: runValue,
                                rb: encRb,
                                near: 0,
                                context: &context,
                                regularMode: regularMode,
                                runMode: runMode,
                                writer: writer,
                                limit: limit,
                                qbppBits: qbppBits
                            )
                            // Decrement RUNindex after the interruption pixel, matching
                            // the decoder which calls decrementRunIndex() at this point.
                            context.setRunIndex(max(finalRunIndex - 1, 0))
                            col = interruptionCol + 1
                        } else {
                            // Run reaches end of line: write one '1' bit for a
                            // partial last block; nothing for an exact fill
                            // (per ITU-T.87 §A.7.1).
                            if encoded.remainder > 0 {
                                writer.writeBits(1, count: 1)
                            }
                            col += actualRunLength
                            context.setRunIndex(finalRunIndex)
                        }
                    } else {
                        // Regular mode
                        _ = encodePixel(
                            actual: actual,
                            a: a, b: b, c: c,
                            q1: q1, q2: q2, q3: q3,
                            regularMode: regularMode,
                            context: &context,
                            writer: writer,
                            limit: limit,
                            qbppBits: qbppBits
                        )
                        col += 1
                    }
                }
            }
        }
    }

    /// Near-lossless prediction uses reconstructed neighbours. Two UInt16 rows
    /// are sufficient; original image storage remains borrowed and immutable.
    func encodeNearLossless<Reader: JPEGSampleReader>(buf: Reader, rowStride: Int, width: Int, height: Int,
                            near: Int, parameters: JPEGLSPresetParameters,
                            writer: JPEGLSBitstreamWriter, bits: Int,
                            checkpoint: () throws -> Void) throws {
        let regular = try JPEGLSRegularMode(parameters: parameters, near: near)
        let run = try JPEGLSRunMode(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)
        let coding = computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: bits)
        var previous = [UInt16](repeating: 0, count: width)
        var current = [UInt16](repeating: 0, count: width)
        var edge = 0
        for y in 0..<height {
            try checkpoint()
            let oldEdge = edge
            edge = Int(previous[0])
            var x = 0
            while x < width {
                if x & 255 == 0 { try checkpoint() }
                let a = x == 0 ? Int(previous[0]) : Int(current[x - 1])
                let b = Int(previous[x])
                let c = x == 0 ? oldEdge : Int(previous[x - 1])
                let d = Int(previous[min(x + 1, width - 1)])
                let q1 = regular.quantizeGradient(d - b)
                let q2 = regular.quantizeGradient(b - c)
                let q3 = regular.quantizeGradient(c - a)
                if q1 == 0 && q2 == 0 && q3 == 0 {
                    let start = x
                    while x < width && abs(Int(buf[y * rowStride + x]) - a) <= near {
                        if x & 255 == 0 { try checkpoint() }
                        current[x] = UInt16(a)
                        x += 1
                    }
                    let encoded = run.encodeRunLength(runLength: x - start, runIndex: context.currentRunIndex)
                    writer.writeOnes(encoded.continuationBits)
                    let finalIndex = min(encoded.runIndex + encoded.continuationBits, 31)
                    context.setRunIndex(finalIndex)
                    if x < width {
                        writeRunTermination(encoded: encoded, writer: writer)
                        let reconstructed = writeRunInterruptionBits(
                            interruptionValue: Int(buf[y * rowStride + x]), runValue: a,
                            rb: Int(previous[x]), near: near, context: &context,
                            regularMode: regular, runMode: run, writer: writer,
                            limit: coding.limit, qbppBits: coding.qbppBits)
                        current[x] = UInt16(reconstructed)
                        context.decrementRunIndex()
                        x += 1
                    } else if encoded.remainder > 0 {
                        writer.writeBits(1, count: 1)
                    }
                } else {
                    let reconstructed = encodePixel(actual: Int(buf[y * rowStride + x]),
                        a: a, b: b, c: c, q1: q1, q2: q2, q3: q3, regularMode: regular,
                        context: &context, writer: writer, limit: coding.limit, qbppBits: coding.qbppBits)
                    current[x] = UInt16(reconstructed)
                    x += 1
                }
            }
            swap(&previous, &current)
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
        writer: JPEGLSBitstreamWriter,
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
        writeRegularModeBits(encodedPixel, to: writer, limit: limit, qbppBits: qbppBits)

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
        to writer: JPEGLSBitstreamWriter,
        limit: Int,
        qbppBits: Int
    ) {
        let limitThreshold = limit - qbppBits - 1
        if encoded.unaryLength >= limitThreshold {
            // Limited binary code: write limitThreshold zeros + 1, then MErrval−1 in qbppBits.
            writer.writeUnaryCode(limitThreshold)
            writer.writeBits(UInt32(encoded.mappedError - 1), count: qbppBits)
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
        writer: JPEGLSBitstreamWriter,
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
        let params = parameters(regularMode)
        let qbpp = near > 0 ? (2 * near + 1) : 1
        let range: Int
        if near == 0 {
            range = params.maxValue + 1
        } else {
            range = (params.maxValue + 2 * near) / qbpp + 1
        }

        // Quantize for near-lossless (identity for lossless)
        var reducedError: Int
        if near > 0 {
            if rawError >= 0 {
                reducedError = (rawError + near) / qbpp
            } else {
                reducedError = -((abs(rawError) + near) / qbpp)
            }
        } else {
            reducedError = rawError
        }

        // Modular reduction with RANGE
        if reducedError < 0 { reducedError += range }
        if reducedError >= ((range + 1) / 2) { reducedError -= range }

        let k = context.computeRunInterruptionGolombK(riType: riType)
        let map = context.computeRunInterruptionMap(errorValue: reducedError, k: k, riType: riType)

        // Map to the non-negative interruption code per ITU-T.87:
        // e_mapped = 2 * |error| - riType - map
        let eMappedErrorValue = 2 * abs(reducedError) - riType - (map ? 1 : 0)

        // Adjusted limit for run interruption
        let j = runMode.computeJ(runIndex: context.currentRunIndex)
        let adjustedLimit = limit - j - 1
        let limitThreshold = adjustedLimit - qbppBits - 1

        let (unaryLength, remainder) = regularMode.golombEncode(value: eMappedErrorValue, k: k)
        if unaryLength >= limitThreshold {
            writer.writeUnaryCode(limitThreshold)
            writer.writeBits(UInt32(eMappedErrorValue - 1), count: qbppBits)
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
        let dequantized = reducedError * qbpp
        let signedError: Int
        if riType == 1 {
            signedError = dequantized
        } else {
            signedError = dequantized * (rb >= ra ? 1 : -1)
        }
        var rv = prediction + signedError
        let wrapRange = range * qbpp
        if rv < -near { rv += wrapRange }
        else if rv > params.maxValue + near { rv -= wrapRange }
        return max(0, min(params.maxValue, rv))
    }

    private func parameters(_ regularMode: JPEGLSRegularMode) -> JPEGLSPresetParameters {
        regularMode.presetParameters
    }

    func writeRunTermination(
        encoded: EncodedRun,
        writer: JPEGLSBitstreamWriter
    ) {
        writer.writeBits(0, count: 1)  // Termination bit
        if encoded.j > 0 {
            writer.writeBits(UInt32(encoded.remainder), count: encoded.j)
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
        to writer: JPEGLSBitstreamWriter
    ) throws {
        writer.writeMarker(.startOfFrameJPEGLS)

        // Length: 8 + 3 * componentCount
        let length = UInt16(8 + 3 * frameHeader.componentCount)
        writer.writeUInt16(length)

        // Precision (bits per sample)
        writer.writeByte(UInt8(frameHeader.bitsPerSample))

        // Dimensions — use 0 for any dimension > 65535 (encoded in preceding LSE type 4)
        writer.writeUInt16(UInt16(frameHeader.height > 65535 ? 0 : frameHeader.height))
        writer.writeUInt16(UInt16(frameHeader.width  > 65535 ? 0 : frameHeader.width))

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
    }

    func writeScanHeaderInternal(
        _ scanHeader: JPEGLSScanHeader,
        to writer: JPEGLSBitstreamWriter
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
        guard rows > 0, width > 0, rowStride >= width,
              try checkedAdd(checkedMultiply(rows - 1, rowStride), width) <= buf.count else {
            throw CodecError(.incompatibleImageLayout, "Invalid scalar output extent.")
        }
        let decoder = try JPEGLSRegularModeDecoder(parameters: parameters, near: near)
        let runDecoder = try JPEGLSRunModeDecoder(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)

        do {
            // Track the left-edge value for boundary Rc at col=0.
            // The edge buffer is previous_line[0], which equals the first pixel
            // of the row decoded two iterations ago (0 for rows 0 and 1).
            var prevRowEdge = 0

            // Decode pixels in raster order
            for row in 0..<rows {
                try checkpoint()
                // Note: RUNindex is NOT reset per line. Per ITU-T.87 §A.7.1,
                // RUNindex persists across scan lines; it is only initialised to 0 at scan start.
                let rowBase = row * rowStride
                let prevBase = rowBase - rowStride

                // Capture the edge value before this row updates it.
                let edgeForThisRow = prevRowEdge
                if row > 0 {
                    prevRowEdge = Int(buf[prevBase])
                }
                var col = 0
                while col < width {
                    if col & 255 == 0 { try checkpoint() }
                    // Causal neighbours per ITU-T.87 §3.2 (same boundary
                    // semantics as getNeighbors, over the flat plane).
                    let a: Int, b: Int, c: Int, d: Int
                    if row == 0 {
                        a = col == 0 ? 0 : Int(buf[rowBase + col - 1])
                        b = 0; c = 0; d = 0
                    } else if col == 0 {
                        let top = Int(buf[prevBase])
                        a = top
                        b = top
                        c = edgeForThisRow
                        d = width > 1 ? Int(buf[prevBase + 1]) : top
                    } else {
                        a = Int(buf[rowBase + col - 1])
                        b = Int(buf[prevBase + col])
                        c = Int(buf[prevBase + col - 1])
                        d = col + 1 < width ? Int(buf[prevBase + col + 1]) : b
                    }

                    // Check for run mode: all quantized gradients are zero
                    let (d1, d2, d3) = decoder.computeGradients(a: a, b: b, c: c, d: d)
                    let q1 = decoder.quantizeGradient(d1)
                    let q2 = decoder.quantizeGradient(d2)
                    let q3 = decoder.quantizeGradient(d3)

                    if q1 == 0 && q2 == 0 && q3 == 0 {
                        // Run mode: decode run of pixels with value = a.
                        // readRunLength clamps to remainingInLine, so the
                        // fill below cannot overrun the row.
                        let remainingInLine = width - col
                        let runLength = try readRunLength(
                            reader: reader,
                            runDecoder: runDecoder,
                            context: &context,
                            remainingInLine: remainingInLine
                        )
                        if runLength > 0 {
                            let rv = UInt16(truncatingIfNeeded: a)
                            let end = rowBase + col + runLength
                            for first in stride(from: rowBase + col, to: end, by: 256) {
                                try checkpoint()
                                buf.fill(rv, range: first..<min(end, first + 256))
                            }
                            col += runLength
                        }

                        if runLength < remainingInLine {
                            // Interrupted run: decode the interruption sample
                            // (per ITU-T.87 §A.7.2).
                            let ra = a
                            let rb = row > 0 ? Int(buf[prevBase + col]) : 0
                            let riType = (abs(ra - rb) <= near) ? 1 : 0
                            let k = context.computeRunInterruptionGolombK(riType: riType)
                            let j = runDecoder.computeJ(runIndex: context.currentRunIndex)
                            let adjustedLimit = limit - j - 1
                            let eMappedErrorValue = try readGolombCode(
                                reader: reader, k: k, limit: adjustedLimit, qbppBits: qbppBits
                            )
                            let errorValue = context.computeRunInterruptionErrorValue(
                                temp: eMappedErrorValue + riType, k: k, riType: riType
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
                            // Per ITU-T.87, decrement RUNindex AFTER the interruption pixel.
                            context.decrementRunIndex()

                            buf[rowBase + col] = UInt16(truncatingIfNeeded: sample)
                            col += 1
                        }
                    } else {
                        // Regular mode
                        let pixel = try decodeSinglePixel(
                            reader: reader,
                            decoder: decoder,
                            runDecoder: runDecoder,
                            context: &context,
                            a: a, b: b, c: c,
                            q1: q1, q2: q2, q3: q3,
                            parameters: parameters,
                            near: near,
                            limit: limit,
                            qbppBits: qbppBits
                        )
                        buf[rowBase + col] = UInt16(truncatingIfNeeded: pixel)
                        col += 1
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
        // Get context, reusing the quantized gradients the scan loop already
        // computed for the run-mode test. Bias C[Q], Golomb k, and the k=0
        // error correction come from a single context-record load.
        let (contextIndex, sign) = context.computeContextIndexAndSign(q1: q1, q2: q2, q3: q3)
        let (biasC, k, errorCorrection) = context.pixelCodingState(contextIndex: contextIndex)

        // Read Golomb-Rice encoded error
        let mappedError = try readGolombCode(reader: reader, k: k, limit: limit, qbppBits: qbppBits)

        // Decode pixel using decoder
        let result = decoder.decodePixel(
            mappedError: mappedError,
            a: a, b: b, c: c,
            contextIndex: contextIndex,
            sign: sign,
            biasC: biasC,
            errorCorrection: errorCorrection
        )

        // Update context
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
        let limitThreshold = limit - qbppBits - 1
        // Read unary prefix (count zeros until first '1')
        guard k >= 0, k <= 31, (1...16).contains(qbppBits), limitThreshold > 0 else {
            throw CodecError(.malformedInput, "Invalid Golomb coding state.")
        }
        let unaryCount = try reader.readUnaryCount(maximum: limitThreshold)
        // Per ITU-T.87 §6.1.2: when unaryCount >= limitThreshold the encoder used
        // the limited binary code — read qbppBits bits for MErrval − 1.
        if unaryCount >= limitThreshold {
            let rawValue = Int(try reader.readBits(qbppBits))
            return rawValue + 1
        }
        // Standard Golomb-Rice code
        let remainder = k > 0 ? Int(try reader.readBits(k)) : 0
        let mapped = (unaryCount << k) | remainder
        // Sign normalisation and the k=0 bias mapping can exceed RANGE.
        // Bound at twice the representable range, including that mapping.
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
        var runLength = 0
        var runIndex = context.currentRunIndex

        // Read continuation bits per ITU-T.87 §A.7.1.
        // Each '1' bit contributes min(2^J[RUNindex], remaining) pixels.
        // run_index is only incremented when a FULL block is used.
        while true {
            let bit = try reader.readBits(1)
            if bit == 0 {
                break  // Run interrupted
            }
            let j = runDecoder.computeJ(runIndex: runIndex)
            let blockSize = 1 << j  // 2^J
            let count = min(blockSize, remainingInLine - runLength)
            runLength += count

            // Only increment run_index when a full block was consumed
            if count == blockSize && runIndex < 31 {
                runIndex += 1
            }

            if runLength >= remainingInLine {
                break  // Run reached end of line
            }
        }

        if runLength < remainingInLine {
            // Incomplete run — read J[RUNindex] remainder bits.
            // Note: run_index is NOT decremented here; the caller decrements
            // after the interruption pixel is decoded (matching ITU-T.87).
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
