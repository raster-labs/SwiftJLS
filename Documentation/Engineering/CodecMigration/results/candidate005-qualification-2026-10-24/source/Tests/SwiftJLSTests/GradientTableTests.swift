// SPDX-License-Identifier: Apache-2.0
import Testing
@testable import SwiftJLS

@Suite("Decoder and encoder gradient table intervals")
struct GradientTableTests {
    // An independent branch oracle preserves the published decoder quantizer's
    // outer clamps and historical precedence, including internal NEAR >= T1 inputs.
    // The decoder fills nine constant intervals once at construction when NEAR < T1.
    private func reference(_ gradient: Int, _ p: JPEGLSPresetParameters, near: Int) -> Int {
        if gradient <= -p.threshold3 { return -4 }
        if gradient >= p.threshold3 { return 4 }
        if gradient <= -p.threshold2 { return -3 }
        if gradient <= -p.threshold1 { return -2 }
        if gradient < -near { return -1 }
        if gradient <= near { return 0 }
        if gradient < p.threshold1 { return 1 }
        if gradient < p.threshold2 { return 2 }
        return 3
    }

    // Independent branch oracle for `JPEGLSRegularMode` (encoder). When NEAR < T1,
    // the encoder fills seven constant intervals once at construction; when
    // NEAR >= T1, the encoder's historical near-first branch order is preserved.
    private func encoderReference(_ gradient: Int, _ p: JPEGLSPresetParameters, near: Int) -> Int {
        if gradient <= -p.threshold3 { return -4 }
        if gradient >= p.threshold3 { return 4 }
        if gradient < -near {
            if gradient <= -p.threshold2 { return -3 }
            if gradient <= -p.threshold1 { return -2 }
            return -1
        }
        if gradient <= near { return 0 }
        if gradient < p.threshold1 { return 1 }
        if gradient < p.threshold2 { return 2 }
        return 3
    }

    private func firstMismatch(_ p: JPEGLSPresetParameters, near: Int,
                               gradients: ClosedRange<Int>) throws -> String? {
        let decoder = try JPEGLSRegularModeDecoder(parameters: p, near: near)
        let encoder = try JPEGLSRegularMode(parameters: p, near: near)
        for gradient in gradients {
            let actual = decoder.quantizeGradient(gradient)
            let expected = reference(gradient, p, near: near)
            if actual != expected {
                return "decoder T=(\(p.threshold1),\(p.threshold2),\(p.threshold3)), NEAR=\(near), gradient=\(gradient): \(actual) != \(expected)"
            }
            let actualEnc = encoder.quantizeGradient(gradient)
            let expectedEnc = encoderReference(gradient, p, near: near)
            if actualEnc != expectedEnc {
                return "encoder T=(\(p.threshold1),\(p.threshold2),\(p.threshold3)), NEAR=\(near), gradient=\(gradient): \(actualEnc) != \(expectedEnc)"
            }
        }
        // Very large gradients must use the unchanged outer clamps without
        // indexing the table or adding T3 to an extreme signed value.
        if decoder.quantizeGradient(Int.min) != -4 || decoder.quantizeGradient(Int.max) != 4 {
            return "Decoder extreme gradient did not use its outer clamp."
        }
        if encoder.quantizeGradient(Int.min) != -4 || encoder.quantizeGradient(Int.max) != 4 {
            return "Encoder extreme gradient did not use its outer clamp."
        }
        return nil
    }

    @Test func everySmallThresholdTripleAndNearValueMatchesReference() throws {
        // Exhaust all 120 ordered triples up to eight and all nine NEAR values.
        // Includes equality/empty intervals, NEAR == T1 and NEAR above T3.
        for t1 in 1...8 { for t2 in t1...8 { for t3 in t2...8 {
            let p = try JPEGLSPresetParameters(maxValue: 8,
                threshold1: t1, threshold2: t2, threshold3: t3, reset: 64)
            for near in 0...8 {
                let mismatch = try firstMismatch(p, near: near, gradients: -10...10)
                #expect(mismatch == nil, "\(mismatch ?? "")")
            }
        } } }
    }

    @Test func defaultsMatchEveryPossibleSampleGradient() throws {
        for bits in 2...16 {
            let maximum = (1 << bits) - 1
            let bounds = Set([0, min(3, maximum / 2), min(255, maximum / 2)]).sorted()
            for near in bounds {
                let p = try JPEGLSPresetParameters.defaultParameters(bitsPerSample: bits, near: near)
                let mismatch = try firstMismatch(p, near: near, gradients: (-maximum)...maximum)
                #expect(mismatch == nil, "\(mismatch ?? "")")
            }
        }
    }

    @Test func maximumTableAndFallbackBoundariesMatchEveryGradient() throws {
        // Largest table extent, both equal-threshold positions, an empty ±1
        // interval, and the exact fallback boundary at NEAR == T1.
        let cases: [(Int, Int, Int, Int)] = [
            (1, 1, 65535, 0),
            (1, 65535, 65535, 0),
            (65535, 65535, 65535, 255),
            (255, 255, 65535, 254),
            (255, 255, 65535, 255),
            (1, 1, 1, 255)
        ]
        for (t1, t2, t3, near) in cases {
            let p = try JPEGLSPresetParameters(maxValue: 65535,
                threshold1: t1, threshold2: t2, threshold3: t3, reset: 65535)
            let mismatch = try firstMismatch(p, near: near, gradients: -65536...65536)
            #expect(mismatch == nil, "\(mismatch ?? "")")
        }
        // Internal NEAR >= T1 fallback: encoder is near-first (0 for |g| <= NEAR),
        // whereas decoder tests negative thresholds before -NEAR (-2 at -T1, 0 at +T1).
        let fallbackParams = try JPEGLSPresetParameters(
            maxValue: 65535, threshold1: 2, threshold2: 5, threshold3: 8, reset: 64
        )
        let encFallback = try JPEGLSRegularMode(parameters: fallbackParams, near: 3)
        let decFallback = try JPEGLSRegularModeDecoder(parameters: fallbackParams, near: 3)
        #expect(encFallback.quantizeGradient(-2) == 0 && encFallback.quantizeGradient(2) == 0)
        #expect(decFallback.quantizeGradient(-2) == -2 && decFallback.quantizeGradient(2) == 0)

        for badNear in [-1, 256] {
            do {
                _ = try JPEGLSRegularMode(parameters: fallbackParams, near: badNear)
                Issue.record("Expected invalidNearParameter for encoder NEAR=\(badNear)")
            } catch JPEGLSError.invalidNearParameter(let near) {
                #expect(near == badNear)
            }
            do {
                _ = try JPEGLSRegularModeDecoder(parameters: fallbackParams, near: badNear)
                Issue.record("Expected invalidNearParameter for decoder NEAR=\(badNear)")
            } catch JPEGLSError.invalidNearParameter(let near) {
                #expect(near == badNear)
            }
        }
    }
}
