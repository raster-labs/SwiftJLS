// SPDX-License-Identifier: Apache-2.0
import Testing
@testable import SwiftJLS

@Suite("Quantized context mapping")
struct ContextIndexTests {
    @Test func combinedIndexAndSignMatchesEveryQuantizedTriple() throws {
        let parameters = try JPEGLSPresetParameters.defaultParameters(bitsPerSample: 8)
        let context = try JPEGLSContextModel(parameters: parameters)
        var indices = Set<Int>()
        for q1 in -4...4 { for q2 in -4...4 { for q3 in -4...4 {
            let result = context.computeContextIndexAndSign(q1: q1, q2: q2, q3: q3)
            #expect(result.index == context.computeContextIndex(q1: q1, q2: q2, q3: q3))
            #expect(result.sign == context.computeContextSign(q1: q1, q2: q2, q3: q3))
            #expect((0..<JPEGLSContextModel.regularContextCount).contains(result.index))
            indices.insert(result.index)
        } } }
        #expect(indices.count == JPEGLSContextModel.regularContextCount)
    }
}
