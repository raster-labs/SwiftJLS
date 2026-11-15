// SPDX-License-Identifier: MIT
// Copyright 2026 Raster Images Private Limited
// Adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc, Sources/JPEGLS/Encoder/JPEGLSRegularMode.swift.
// Internal implementation; the successor public API is defined in CodecAPI.swift.

/// JPEG-LS regular mode encoding implementation per ITU-T.87.
///
/// Regular mode is the primary encoding mode for JPEG-LS, used when the local
/// gradient indicates non-uniform pixel values. It uses context-based adaptive
/// prediction and Golomb-Rice coding to compress prediction errors efficiently.

import Foundation

/// Regular mode encoder for JPEG-LS compression.
///
/// The regular mode encoder implements the core JPEG-LS algorithm:
/// 1. Compute local gradients (D1, D2, D3) around the current pixel
/// 2. Quantize gradients to determine context
/// 3. Predict pixel value using MED (Median Edge Detector)
/// 4. Apply bias correction based on context statistics
/// 5. Compute prediction error with modular reduction
/// 6. Encode error using Golomb-Rice coding
/// 7. Update context statistics for adaptation
struct JPEGLSRegularMode: Sendable {
    // MARK: - Properties

    /// Preset parameters controlling thresholds and limits
    private let parameters: JPEGLSPresetParameters

    /// Public accessor for preset parameters
    var presetParameters: JPEGLSPresetParameters { parameters }

    /// Near-lossless parameter (0 for lossless mode)
    private let near: Int

    internal let range: Int
    internal let qbpp: Int
    internal let gradientTable: [Int8]
    internal let gradientTableOffset: Int
    internal let wrapRange: Int
    internal let halfRangeHigh: Int
    internal let halfRangeLow: Int

    // MARK: - Initialization

    /// Initialize regular mode encoder with preset parameters.
    ///
    /// - Parameters:
    ///   - parameters: Preset parameters (thresholds, MAXVAL, RESET)
    ///   - near: Near-lossless parameter (0 for lossless mode)
    /// - Throws: `JPEGLSError.invalidNearParameter` if NEAR is invalid
    init(parameters: JPEGLSPresetParameters, near: Int = 0) throws {
        guard near >= 0 && near <= 255 else {
            throw JPEGLSError.invalidNearParameter(near: near)
        }

        self.parameters = parameters
        self.near = near

        // Compute quantization factor per ITU-T.87 Section 4.2.1
        self.qbpp = (near == 0) ? 0 : ((near << 1) | 1)

        // Compute RANGE per ITU-T.87 Section 4.2.1
        // RANGE = (MAXVAL + 2*NEAR)/qbpp + 1
        if near == 0 {
            self.range = parameters.maxValue + 1
        } else {
            self.range = (parameters.maxValue + 2 * near) / qbpp + 1
        }

        // Pre-compute modular-reduction bounds and wrap range to avoid per-pixel arithmetic.
        self.halfRangeHigh = (self.range - 1) / 2
        self.halfRangeLow  = -(self.range / 2)
        self.wrapRange     = near == 0 ? self.range : self.range * ((near << 1) | 1)

        // Fill the gradient quantisation intervals directly when NEAR < T1;
        // retain the encoder's existing branch loop for the internal NEAR >= T1 case.
        // Values outside [-T3, T3] always map to ±4 (handled by early-exit checks).
        let t3 = parameters.threshold3
        let tableSize = 2 * t3 + 1
        self.gradientTableOffset = t3
        let t1 = parameters.threshold1, t2 = parameters.threshold2
        if near < t1 {
            self.gradientTable = Array(unsafeUninitializedCapacity: tableSize) { buffer, initializedCount in
                UnsafeMutableBufferPointer(rebasing: buffer[0..<1]).initialize(repeating: -4)
                UnsafeMutableBufferPointer(rebasing: buffer[1..<(t3 - t2 + 1)]).initialize(repeating: -3)
                UnsafeMutableBufferPointer(rebasing: buffer[(t3 - t2 + 1)..<(t3 - t1 + 1)]).initialize(repeating: -2)
                UnsafeMutableBufferPointer(rebasing: buffer[(t3 - t1 + 1)..<(t3 - near)]).initialize(repeating: -1)
                UnsafeMutableBufferPointer(rebasing: buffer[(t3 - near)..<(t3 + near + 1)]).initialize(repeating: 0)
                UnsafeMutableBufferPointer(rebasing: buffer[(t3 + near + 1)..<(t3 + t1)]).initialize(repeating: 1)
                UnsafeMutableBufferPointer(rebasing: buffer[(t3 + t1)..<(t3 + t2)]).initialize(repeating: 2)
                UnsafeMutableBufferPointer(rebasing: buffer[(t3 + t2)..<(2 * t3)]).initialize(repeating: 3)
                UnsafeMutableBufferPointer(rebasing: buffer[(2 * t3)..<tableSize]).initialize(repeating: 4)
                initializedCount = tableSize
            }
        } else {
            var table = [Int8](repeating: 0, count: tableSize)
            for i in 0..<tableSize {
                let g = i - t3  // gradient in [−T3, T3]
                if g < -near {
                    if g <= -t2 { table[i] = -3 }
                    else if g <= -t1 { table[i] = -2 }
                    else { table[i] = -1 }
                } else if g <= near {
                    table[i] = 0
                } else {
                    if g < t1 { table[i] = 1 }
                    else if g < t2 { table[i] = 2 }
                    else { table[i] = 3 }
                }
            }
            table[0] = -4
            table[tableSize - 1] = 4
            self.gradientTable = table
        }
    }

    // MARK: - Gradient Computation

    @inline(__always)
    func computeGradients(a: Int, b: Int, c: Int, d: Int) -> (d1: Int, d2: Int, d3: Int) {
        return (d - b, b - c, c - a)
    }

    @inline(__always)
    func quantizeGradient(_ gradient: Int) -> Int {
        let t3 = gradientTableOffset
        let clamped = min(max(gradient, -t3), t3)
        return Int(gradientTable[clamped &+ t3])
    }

    // MARK: - MED Prediction

    @inline(__always)
    func computeMEDPrediction(a: Int, b: Int, c: Int) -> Int {
        let maxAB = max(a, b)
        let minAB = min(a, b)
        if c >= maxAB { return minAB }
        if c <= minAB { return maxAB }
        return a &+ b &- c
    }

    // MARK: - Bias Correction

    @inline(__always)
    func applyBiasCorrection(prediction: Int, biasC: Int, sign: Int) -> Int {
        let corrected = prediction &+ sign &* biasC
        return max(0, min(parameters.maxValue, corrected))
    }

    // MARK: - Prediction Error

    @inline(__always)
    private func computeQuantizedError(_ rawError: Int) -> Int {
        guard near > 0 else { return rawError }
        let sign = rawError >= 0 ? 1 : -1
        return sign * ((abs(rawError) + near) / qbpp)
    }

    @inline(__always)
    func computePredictionError(actual: Int, prediction: Int) -> Int {
        let rawError = actual - prediction
        var error = computeQuantizedError(rawError)
        if error > halfRangeHigh {
            error -= range
        } else if error < halfRangeLow {
            error += range
        }
        return error
    }

    @inline(__always)
    func computeReconstructedValue(prediction: Int, quantizedError: Int) -> Int {
        let dequantized = near > 0 ? quantizedError * qbpp : quantizedError
        var rv = prediction + dequantized
        if rv < -near {
            rv += wrapRange
        } else if rv > parameters.maxValue + near {
            rv -= wrapRange
        }
        return max(0, min(parameters.maxValue, rv))
    }

    @inline(__always)
    func mapErrorToNonNegative(_ error: Int) -> Int {
        return (error << 1) ^ (error >> (Int.bitWidth - 1))
    }

    // MARK: - Golomb-Rice Encoding

    @inline(__always)
    func golombEncode(value: Int, k: Int) -> (unaryLength: Int, remainder: Int) {
        let quotient = value >> k
        let remainder = value & ((1 << k) - 1)
        return (quotient, remainder)
    }

    /// Compute total bit length for Golomb-Rice encoded value.
    ///
    /// - Parameters:
    ///   - value: Non-negative value to encode
    ///   - k: Golomb-Rice parameter
    /// - Returns: Total number of bits required
    func golombBitLength(value: Int, k: Int) -> Int {
        let quotient = value >> k
        // Total bits = unary length + k bits for remainder
        return quotient + 1 + k
    }

    // MARK: - Complete Encoding Pipeline

    /// Encode a single pixel in regular mode.
    ///
    /// This is the complete encoding pipeline combining all steps:
    /// 1. Compute gradients
    /// 2. Quantize gradients
    /// 3. Compute context index
    /// 4. Compute MED prediction
    /// 5. Apply bias correction
    /// 6. Compute prediction error
    /// 7. Map to non-negative
    /// 8. Determine Golomb parameter k
    /// 9. Encode using Golomb-Rice
    ///
    /// - Parameters:
    ///   - actual: Actual pixel value to encode
    ///   - a: Left neighbor pixel value
    ///   - b: Top neighbor pixel value
    ///   - c: Top-left diagonal neighbor pixel value
    ///   - context: Context model (for accessing statistics)
    /// - Returns: Encoded result with context info and encoded bits
    func encodePixel(
        actual: Int,
        a: Int,
        b: Int,
        c: Int,
        d: Int,
        context: borrowing JPEGLSContextModel
    ) -> EncodedPixel {
        // Step 1: Compute local gradients
        let (d1, d2, d3) = computeGradients(a: a, b: b, c: c, d: d)

        // Step 2: Quantize gradients
        let q1 = quantizeGradient(d1)
        let q2 = quantizeGradient(d2)
        let q3 = quantizeGradient(d3)

        // Step 3: Compute context index and sign
        let (contextIndex, sign) = context.computeContextIndexAndSign(q1: q1, q2: q2, q3: q3)

        return encodePixel(
            actual: actual, a: a, b: b, c: c,
            contextIndex: contextIndex, sign: sign, context: context
        )
    }

    /// Encode a single pixel in regular mode with a precomputed context.
    ///
    /// Identical to `encodePixel(actual:a:b:c:d:context:)` from step 4
    /// onward; the caller supplies the context index and sign it already
    /// derived from the quantized gradients (the scan loop computes them
    /// for the run-mode test, so recomputing here would quantize every
    /// gradient twice per pixel).
    func encodePixel(
        actual: Int,
        a: Int,
        b: Int,
        c: Int,
        contextIndex: Int,
        sign: Int,
        context: borrowing JPEGLSContextModel
    ) -> EncodedPixel {
        // Steps 5/7/7a inputs: bias C[Q], Golomb k, and the k=0 error
        // correction from a single context-record load.
        let (biasC, k, errorCorrection) = context.pixelCodingState(contextIndex: contextIndex)

        // Step 4: Compute MED prediction
        let basePrediction = computeMEDPrediction(a: a, b: b, c: c)

        // Step 5: Apply bias correction
        let correctedPrediction = applyBiasCorrection(
            prediction: basePrediction,
            biasC: biasC,
            sign: sign
        )

        // Normalise the raw error BEFORE quantisation/modular reduction
        // (T.87 A.4.3–A.4.5). Reversing these steps selects the wrong side
        // of the half-range boundary when the context sign is negative.
        // Both samples are in 0...MAXVAL (MAXVAL <= 65535), so their
        // difference and its sign normalisation fit Int even on 32-bit targets.
        let error = computePredictionError(actual: sign * (actual - correctedPrediction), prediction: 0)
        let quantisedError = sign * error

        // Step 7a: Apply error correction XOR per ITU-T.87 §A.4.1
        let correctedError = error ^ errorCorrection

        // Step 8: Map to non-negative for Golomb coding
        let mappedError = mapErrorToNonNegative(correctedError)

        // Step 9: Encode using Golomb-Rice
        let (unaryLength, remainder) = golombEncode(value: mappedError, k: k)

        // Compute reconstructed value for near-lossless neighbour tracking.
        // For lossless (NEAR=0) the reconstructed value is always equal to the
        // actual pixel, so we skip the modular-arithmetic computation entirely.
        let reconstructedValue: Int
        if near == 0 {
            reconstructedValue = actual
        } else {
            reconstructedValue = computeReconstructedValue(
                prediction: correctedPrediction,
                quantizedError: quantisedError
            )
        }

        // Store quantisedError (uncorrected, sign-denormalised) per ITU-T.87 §A.6.2.
        // The XOR correction is only for mapping; context update uses the original
        // error.  The caller's updateContext computes errval = sign × quantisedError
        // = sign-normalised uncorrected error, matching ITU-T.87 behaviour.
        return EncodedPixel(
            contextIndex: contextIndex,
            sign: sign,
            prediction: correctedPrediction,
            error: quantisedError,
            mappedError: mappedError,
            golombK: k,
            unaryLength: unaryLength,
            remainder: remainder,
            reconstructedValue: reconstructedValue
        )
    }
}

// MARK: - Encoded Pixel Result

/// Result of encoding a single pixel in regular mode.
///
/// Contains all intermediate values and final encoded bits for testing
/// and bitstream writing.
struct EncodedPixel: Sendable {
    /// Context index used (0 to 364)
    let contextIndex: Int

    /// Context sign (+1 or -1)
    let sign: Int

    /// Bias-corrected prediction value
    let prediction: Int

    /// Quantised prediction error (equals raw error for lossless mode)
    let error: Int

    /// Mapped non-negative error (MErrval)
    let mappedError: Int

    /// Golomb-Rice parameter k
    let golombK: Int

    /// Unary code length (quotient + 1)
    let unaryLength: Int

    /// Binary remainder (k bits)
    let remainder: Int

    /// Reconstructed sample value (what the decoder will produce).
    /// For lossless mode this equals the actual pixel value; for
    /// near-lossless it is the dequantised approximation.
    let reconstructedValue: Int

    /// Total encoded bit length
    var totalBitLength: Int {
        return unaryLength + 1 + golombK
    }
}
