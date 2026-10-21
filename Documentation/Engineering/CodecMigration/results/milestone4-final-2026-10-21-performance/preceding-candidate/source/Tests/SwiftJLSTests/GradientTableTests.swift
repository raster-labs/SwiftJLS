// SPDX-License-Identifier: Apache-2.0
import Testing
@testable import SwiftJLS

@Suite("Decoder gradient table intervals")
struct GradientTableTests {
    // An independent branch oracle preserves the published quantizer's outer
    // clamps and historical precedence, including internal NEAR >= T1 inputs.
    // The candidate instead fills nine constant intervals once at construction.
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

    private func firstMismatch(_ p: JPEGLSPresetParameters, near: Int,
                               gradients: ClosedRange<Int>) throws -> String? {
        let decoder = try JPEGLSRegularModeDecoder(parameters: p, near: near)
        for gradient in gradients {
            let actual = decoder.quantizeGradient(gradient)
            let expected = reference(gradient, p, near: near)
            if actual != expected {
                return "T=(\(p.threshold1),\(p.threshold2),\(p.threshold3)), NEAR=\(near), gradient=\(gradient): \(actual) != \(expected)"
            }
        }
        // Very large gradients must use the unchanged outer clamps without
        // indexing the table or adding T3 to an extreme signed value.
        if decoder.quantizeGradient(Int.min) != -4 || decoder.quantizeGradient(Int.max) != 4 {
            return "Extreme gradient did not use its outer clamp."
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
    }
}
