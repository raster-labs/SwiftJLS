// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Core/JPEGLSPresetParameters.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal struct QualifiedPresetParameters: Sendable, Equatable {
    internal let maxValue: Int

    internal let threshold1: Int

    internal let threshold2: Int

    internal let threshold3: Int

    internal let reset: Int

    internal static func qualified(maxValue: Int,
        threshold1: Int,
        threshold2: Int,
        threshold3: Int,
        reset: Int
    ) -> QualifiedOutcome<Self> {
        // Validate parameters according to ITU-T.87 Section 4.2
        guard maxValue >= 1 && maxValue <= 65535 else {
            return .failure(QualifiedFailure(.maxValue, maxValue))
        }

        guard threshold1 >= 1 && threshold1 <= maxValue else {
            return .failure(QualifiedFailure(.threshold1, threshold1))
        }

        guard threshold2 >= threshold1 && threshold2 <= maxValue else {
            return .failure(QualifiedFailure(.threshold2, threshold2))
        }

        guard threshold3 >= threshold2 && threshold3 <= maxValue else {
            return .failure(QualifiedFailure(.threshold3, threshold3))
        }

        guard reset >= 3 && reset <= 255 else {
            return .failure(QualifiedFailure(.reset, reset))
        }

        return .success(Self(validatedMaxValue: maxValue, threshold1: threshold1,
            threshold2: threshold2, threshold3: threshold3, reset: reset))
    }

    private init(validatedMaxValue maxValue: Int, threshold1: Int, threshold2: Int, threshold3: Int, reset: Int) {
        self.maxValue = maxValue
        self.threshold1 = threshold1
        self.threshold2 = threshold2
        self.threshold3 = threshold3
        self.reset = reset
    }

    internal static func qualifiedDefaultParameters(bitsPerSample: Int, near: Int = 0) -> QualifiedOutcome<QualifiedPresetParameters> {
        guard bitsPerSample >= 2 && bitsPerSample <= 16 else {
            return .failure(QualifiedFailure(.invalidBitsPerSample, bitsPerSample))
        }

        let maxValue = (1 << bitsPerSample) - 1

        // FACTOR computation per ITU-T.87 Table C.2
        let factor: Int
        if maxValue >= 128 {
            factor = (min(maxValue, 4095) + 128) / 256
        } else {
            factor = (256 + maxValue / 2) / (maxValue + 1)
        }

        // BASIC_T values from Table C.2
        let basicT1 = 3
        let basicT2 = 7
        let basicT3 = 21

        // Threshold computation per ITU-T.87 Table C.2
        // T1 = CLAMP(FACTOR*(BASIC_T1-2) + 2 + 3*NEAR, NEAR+1, MAXVAL)
        // T2 = CLAMP(FACTOR*(BASIC_T2-3) + 3 + 5*NEAR, T1,     MAXVAL)
        // T3 = CLAMP(FACTOR*(BASIC_T3-4) + 4 + 7*NEAR, T2,     MAXVAL)
        var threshold1 = factor * (basicT1 - 2) + 2 + 3 * near
        threshold1 = min(max(threshold1, near + 1), maxValue)

        var threshold2 = factor * (basicT2 - 3) + 3 + 5 * near
        threshold2 = min(max(threshold2, threshold1), maxValue)

        var threshold3 = factor * (basicT3 - 4) + 4 + 7 * near
        threshold3 = min(max(threshold3, threshold2), maxValue)

        // Default reset value
        let reset = 64

        return qualified(
            maxValue: maxValue,
            threshold1: threshold1,
            threshold2: threshold2,
            threshold3: threshold3,
            reset: reset
        )
    }

}
