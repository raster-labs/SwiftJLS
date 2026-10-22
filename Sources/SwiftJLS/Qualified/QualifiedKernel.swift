// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/JPEGLSDecoder.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
extension QualifiedMonochromeDecoder {
    internal func decodeFlatRegionQualified(
        reader: inout QualifiedBitstreamCursor, rows: Int, width: Int, rowStride: Int,
        parameters: QualifiedPresetParameters, near: Int, limit: Int, qbppBits: Int,
        into buf: UnsafeMutableBufferPointer<UInt16>,
        workspace: UnsafeMutableRawBufferPointer
    ) -> QualifiedFailure? {
        let decoder: QualifiedRegularModeDecoder
        switch QualifiedRegularModeDecoder.qualified(parameters: parameters, near: near) {
        case .success(let value): decoder = value
        case .failure(let failure): return failure
        }
        let runDecoder: QualifiedRunModeDecoder
        switch QualifiedRunModeDecoder.qualified(parameters: parameters, near: near) {
        case .success(let value): runDecoder = value
        case .failure(let failure): return failure
        }
        var context: QualifiedContextModel
        switch QualifiedContextModel.qualified(parameters: parameters, near: near, workspace: workspace) {
        case .success(let value): context = value
        case .failure(let failure): return failure
        }
            // Track the left-edge value for boundary Rc at col=0.
            // The edge buffer is previous_line[0], which equals the first pixel
            // of the row decoded two iterations ago (0 for rows 0 and 1).
            var prevRowEdge = 0

            // Decode pixels in raster order
            for row in 0..<rows {
                if let failure = reader.cancellation.checkpoint() { return failure }
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
                    if col & 255 == 0, let failure = reader.cancellation.checkpoint() { return failure }
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
                        let runLength: Int
                        switch readRunLengthQualified(
                            reader: &reader,
                            runDecoder: runDecoder,
                            context: &context,
                            remainingInLine: remainingInLine
                        ) {
                        case .success(let value): runLength = value
                        case .failure(let failure): return failure
                        }
                        if runLength > 0 {
                            let rv = UInt16(truncatingIfNeeded: a)
                            for i in (rowBase + col)..<(rowBase + col + runLength) {
                                if (i - rowBase - col) & 255 == 0, let failure = reader.cancellation.checkpoint() { return failure }
                                buf[i] = rv
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
                            let eMappedErrorValue: Int
                            switch readGolombCodeQualified(
                                reader: &reader, k: k, limit: adjustedLimit, qbppBits: qbppBits
                            ) {
                            case .success(let value): eMappedErrorValue = value
                            case .failure(let failure): return failure
                            }
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
                        let pixel: Int
                        switch decodeSinglePixelQualified(
                            reader: &reader,
                            decoder: decoder,
                            runDecoder: runDecoder,
                            context: &context,
                            a: a, b: b, c: c,
                            q1: q1, q2: q2, q3: q3,
                            parameters: parameters,
                            near: near,
                            limit: limit,
                            qbppBits: qbppBits
                        ) {
                        case .success(let value): pixel = value
                        case .failure(let failure): return failure
                        }
                        buf[rowBase + col] = UInt16(truncatingIfNeeded: pixel)
                        col += 1
                    }
                }
            }
        return nil
    }
    private func decodeSinglePixelQualified(
        reader: inout QualifiedBitstreamCursor,
        decoder: QualifiedRegularModeDecoder,
        runDecoder: QualifiedRunModeDecoder,
        context: inout QualifiedContextModel,
        a: Int, b: Int, c: Int,
        q1: Int, q2: Int, q3: Int,
        parameters: QualifiedPresetParameters,
        near: Int,
        limit: Int,
        qbppBits: Int
    ) -> QualifiedOutcome<Int> {
        // Get context, reusing the quantized gradients the scan loop already
        // computed for the run-mode test. Bias C[Q], Golomb k, and the k=0
        // error correction come from a single context-record load.
        let (contextIndex, sign) = context.computeContextIndexAndSign(q1: q1, q2: q2, q3: q3)
        let (biasC, k, errorCorrection) = context.pixelCodingState(contextIndex: contextIndex)

        // Read Golomb-Rice encoded error
        let mappedError: Int
        switch readGolombCodeQualified(reader: &reader, k: k, limit: limit, qbppBits: qbppBits) {
        case .success(let value): mappedError = value
        case .failure(let failure): return .failure(failure)
        }

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

        return .success(result.sample)
    }
    internal func computeGolombLimit(
        parameters: QualifiedPresetParameters,
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
        // qbppBits = ⌈log₂(range)⌉
        var qbppBits = 0
        var r = range - 1
        while r > 0 {
            qbppBits += 1
            r >>= 1
        }
        qbppBits = max(qbppBits, 2)
        let limit = 2 * (bitsPerSample + max(8, bitsPerSample))
        return (limit, qbppBits)
    }
    private func readGolombCodeQualified(
        reader: inout QualifiedBitstreamCursor,
        k: Int,
        limit: Int,
        qbppBits: Int
    ) -> QualifiedOutcome<Int> {
        let limitThreshold = limit - qbppBits - 1
        guard k >= 0, k <= 31, qbppBits >= 1, qbppBits <= 16, limitThreshold > 0 else {
            return .failure(QualifiedFailure(.invalidEntropy))
        }
        // Read unary prefix (count zeros until first '1')
        let unaryCount: Int
        switch reader.readUnaryCount(maximum: limitThreshold) {
        case .success(let value): unaryCount = value
        case .failure(let failure): return .failure(failure)
        }
        // Per ITU-T.87 §6.1.2: when unaryCount >= limitThreshold the encoder used
        // the limited binary code — read qbppBits bits for MErrval − 1.
        if unaryCount >= limitThreshold {
            let rawValue: Int
            switch reader.readBits(qbppBits) {
            case .success(let value): rawValue = Int(value)
            case .failure(let failure): return .failure(failure)
            }
            return .success(rawValue + 1)
        }
        // Standard Golomb-Rice code
        var remainder = 0
        if k > 0 {
            switch reader.readBits(k) {
            case .success(let value): remainder = Int(value)
            case .failure(let failure): return .failure(failure)
            }
        }
        // Compute before narrowing so malformed entropy cannot wrap on arm64_32.
        let mapped = (UInt64(unaryCount) << k) | UInt64(remainder)
        guard mapped <= UInt64(2 << qbppBits) else { return .failure(QualifiedFailure(.invalidEntropy)) }
        return .success(Int(mapped))
    }
    private func readRunLengthQualified(
        reader: inout QualifiedBitstreamCursor,
        runDecoder: QualifiedRunModeDecoder,
        context: inout QualifiedContextModel,
        remainingInLine: Int
    ) -> QualifiedOutcome<Int> {
        var runLength = 0
        var runIndex = context.currentRunIndex

        // Read continuation bits per ITU-T.87 §A.7.1.
        // Each '1' bit contributes min(2^J[RUNindex], remaining) pixels.
        // run_index is only incremented when a FULL block is used.
        while true {
            let bit: UInt32
            switch reader.readBits(1) {
            case .success(let value): bit = value
            case .failure(let failure): return .failure(failure)
            }
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
            var remainder = 0
            if j > 0 {
                switch reader.readBits(j) {
                case .success(let value): remainder = Int(value)
                case .failure(let failure): return .failure(failure)
                }
            }
            guard remainder < remainingInLine - runLength else { return .failure(QualifiedFailure(.invalidEntropy)) }
            runLength += remainder
        }

        context.setRunIndex(runIndex)
        return .success(runLength)
    }
}
