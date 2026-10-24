// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Bounded kernel storage")
struct KernelWorkspaceTests {
    @Test func packedRunPrefixRespectsMismatchAndRowExtent() {
        for sampleBytes in [1, 2] {
            for little in [false, true] {
                for stride in [sampleBytes, sampleBytes * 3] {
                    let width = 35, rowBytes = width * stride + 3
                    for mismatch in 0...width {
                        var bytes = [UInt8](repeating: 0xa5, count: 1 + rowBytes * 2)
                        let value: UInt16 = sampleBytes == 1 ? 0xb7 : 0xfedc
                        for x in 0..<width {
                            let sample = x == mismatch ? value - 1 : value
                            let at = 1 + rowBytes + x * stride
                            bytes[at] = UInt8(truncatingIfNeeded: little || sampleBytes == 1 ? sample : sample >> 8)
                            if sampleBytes == 2 { bytes[at + 1] = UInt8(truncatingIfNeeded: little ? sample >> 8 : sample) }
                        }
                        bytes.withUnsafeBytes { raw in
                            let view = ComponentSampleReader(bytes: raw, width: width, height: 2,
                                offset: 1, rowBytes: rowBytes, pixelStride: stride,
                                sampleBytes: sampleBytes, littleEndian: little)
                            #expect(view.matchingPrefix(in: width..<(width * 2), to: value) == mismatch)
                            for end in [0, 1, 15, 16, 17, 31, 32, 35] {
                                #expect(view.matchingPrefix(in: width..<(width + end), to: value) == min(mismatch, end))
                            }
                        }
                    }
                }
            }
        }
    }

    @Test func widePrecisionCheckRejectsEveryInvalidLane() {
        for little in [false, true] {
            for invalid in 0..<35 {
                var bytes = [UInt8](repeating: 0, count: 1 + 35 * 2)
                bytes[1 + invalid * 2 + (little ? 1 : 0)] = 0x10
                bytes.withUnsafeBytes { raw in
                    let view = ScalarSampleReader(bytes: .init(rebasing: raw[1...]), littleEndian: little)
                    #expect(throws: CodecError.self) {
                        try view.validate(width: 35, height: 1, rowStride: 35, maximum: 4095, checkpoint: {})
                    }
                }
            }
        }
    }

    @Test func finiteDeadlineDoesNotRequireIntegerConversion() throws {
        let budget = CodecBudget(limits: try .init(deadlineSeconds: .greatestFiniteMagnitude))
        try budget.check()
        #expect(budget.elapsedSeconds >= 0)
    }
}
