// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Decoder/JPEGLSRegularModeDecoder.swift; Decoder/JPEGLSRunModeDecoder.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal struct QualifiedRegularModeDecoder {
 private let parameters: QualifiedPresetParameters
 private let near: Int
 private let range: Int
 private let qbpp: Int
    internal static func qualified(parameters: QualifiedPresetParameters, near: Int) -> QualifiedOutcome<Self> {
        guard near >= 0 && near <= 255 else {
            return .failure(QualifiedFailure(.invalidNearParameter, near))
        }
        return .success(Self(validatedParameters: parameters, near: near))
    }
    private init(validatedParameters parameters: QualifiedPresetParameters, near: Int) {

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

        // Use the branch quantiser; this caller-workspace path owns no table.

    }
    private static func quantizeGradientReference(
        _ gradient: Int, t1: Int, t2: Int, t3: Int, near: Int
    ) -> Int {
        if gradient <= -t3 { return -4 }
        if gradient <= -t2 { return -3 }
        if gradient <= -t1 { return -2 }
        if gradient < -near { return -1 }
        if gradient <= near { return 0 }
        if gradient < t1 { return 1 }
        if gradient < t2 { return 2 }
        if gradient < t3 { return 3 }
        return 4
    }
    internal func computeGradients(a: Int, b: Int, c: Int, d: Int) -> (d1: Int, d2: Int, d3: Int) {
        let d1 = d - b  // Top-right minus top
        let d2 = b - c  // Top minus top-left
        let d3 = c - a  // Top-left minus left

        return (d1, d2, d3)
    }
    internal func computeMEDPrediction(a: Int, b: Int, c: Int) -> Int {
        // MED prediction per ITU-T.87 Section 4.1.1
        if c >= max(a, b) {
            return min(a, b)
        } else if c <= min(a, b) {
            return max(a, b)
        } else {
            return a + b - c
        }
    }
    internal func applyBiasCorrection(prediction: Int, biasC: Int, sign: Int) -> Int {
        // Bias correction per ITU-T.87 Section 4.3.3
        // Corrected prediction = Px + sign × C[context]
        let corrected = prediction + sign * biasC

        // Clamp to valid range [0, MAXVAL]
        return max(0, min(parameters.maxValue, corrected))
    }
    internal func unmapError(_ mappedError: Int) -> Int {
        if mappedError % 2 == 0 {
            // Even: positive error
            return mappedError / 2
        } else {
            // Odd: negative error
            return -((mappedError + 1) / 2)
        }
    }
    private func dequantizeError(_ error: Int) -> Int {
        guard near > 0 else { return error }
        return error * qbpp
    }
    internal func reconstructSample(prediction: Int, error: Int) -> Int {
        let dequantized = dequantizeError(error)
        var sample = prediction + dequantized

        // Per ITU-T.87 §A.4.4 fix_reconstructed_value:
        // wrap range is RANGE × (2·NEAR + 1); thresholds are −NEAR and MAXVAL+NEAR.
        let wrapRange = near == 0 ? range : range * qbpp
        if sample < -near {
            sample += wrapRange
        } else if sample > parameters.maxValue + near {
            sample -= wrapRange
        }

        // Clamp to valid range [0, MAXVAL]
        return max(0, min(parameters.maxValue, sample))
    }
    func quantizeGradient(_ gradient: Int) -> Int { Self.quantizeGradientReference(gradient, t1: parameters.threshold1, t2: parameters.threshold2, t3: parameters.threshold3, near: near) }
    internal func decodePixel(
        mappedError: Int,
        a: Int,
        b: Int,
        c: Int,
        contextIndex: Int,
        sign: Int,
        biasC: Int,
        errorCorrection: Int = 0
    ) -> QualifiedDecodedPixel {
        // Step 4: Compute MED prediction
        let basePrediction = computeMEDPrediction(a: a, b: b, c: c)

        // Step 5: Apply bias correction
        let correctedPrediction = applyBiasCorrection(
            prediction: basePrediction,
            biasC: biasC,
            sign: sign
        )

        // Step 6: Unmap error from non-negative to signed (sign-adjusted Errval)
        var signAdjustedError = unmapError(mappedError)

        // Step 6b: Apply error correction XOR per ITU-T.87 §A.4.1.
        // When k=0 and lossless, the map swap flips the error sign for biased contexts.
        signAdjustedError = signAdjustedError ^ errorCorrection

        // Step 6a: Undo sign normalisation to recover the raw prediction error.
        // The encoder negated the error when the context sign was -1, so to
        // reconstruct the correct sample we must apply the inverse: rawError = sign × Errval.
        let rawError = sign * signAdjustedError

        // Step 7: Reconstruct sample value
        let sample = reconstructSample(prediction: correctedPrediction, error: rawError)

        return QualifiedDecodedPixel(
            contextIndex: contextIndex,
            sign: sign,
            prediction: correctedPrediction,
            mappedError: mappedError,
            error: rawError,
            sample: sample
        )
    }
}
internal struct QualifiedDecodedPixel: Sendable, Equatable {
    internal let contextIndex: Int

    internal let sign: Int

    internal let prediction: Int

    internal let mappedError: Int

    internal let error: Int

    internal let sample: Int

    internal init(
        contextIndex: Int,
        sign: Int,
        prediction: Int,
        mappedError: Int,
        error: Int,
        sample: Int
    ) {
        self.contextIndex = contextIndex
        self.sign = sign
        self.prediction = prediction
        self.mappedError = mappedError
        self.error = error
        self.sample = sample
    }
}
internal struct QualifiedRunModeDecoder {
 private let parameters: QualifiedPresetParameters
 private let near: Int
 private let maxRunLength: Int
    internal static func qualified(parameters: QualifiedPresetParameters,
        near: Int = 0, maxRunLength: Int = 65536) -> QualifiedOutcome<Self> {
        guard near >= 0 && near <= 255 else {
            return .failure(QualifiedFailure(.invalidNearParameter, near))
        }
        return .success(Self(validatedParameters: parameters, near: near, maxRunLength: maxRunLength))
    }
    private init(validatedParameters parameters: QualifiedPresetParameters, near: Int, maxRunLength: Int) {
        self.parameters = parameters
        self.near = near
        self.maxRunLength = maxRunLength
    }
    internal func computeJ(runIndex: Int) -> Int {
        let idx = max(0, min(runIndex, 31))
        if idx < 16 { return idx / 4 }
        if idx < 24 { return 4 + (idx - 16) / 2 }
        return idx - 16
    }
    internal func reconstructSample(prediction: Int, error: Int) -> Int {
        let qbpp = near == 0 ? 1 : (2 * near + 1)
        let dequantized = error * qbpp
        var sample = prediction + dequantized

        // Per ITU-T.87 §A.4.4 fix_reconstructed_value
        let range: Int
        if near == 0 {
            range = parameters.maxValue + 1
        } else {
            range = (parameters.maxValue + 2 * near) / qbpp + 1
        }
        let wrapRange = range * qbpp
        if sample < -near {
            sample += wrapRange
        } else if sample > parameters.maxValue + near {
            sample -= wrapRange
        }
        return max(0, min(parameters.maxValue, sample))
    }
}
