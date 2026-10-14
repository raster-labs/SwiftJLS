// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Bounded bitstream writer")
struct BitstreamWriterTests {
    @Test func stuffedBitsAndExactOutputLimits() throws {
        // Independent bit-at-a-time reference, including 32-bit writes and
        // repeated 0xff bytes whose successor has a leading stuffing bit.
        var expected: [UInt8] = [], byte: UInt8 = 0, used = 0
        let words: [(UInt32, Int)] = [(UInt32.max, 32), (0, 32), (0xffff, 16)]
            + (1...32).map { (UInt32(truncatingIfNeeded: UInt64($0) * 0x91e10da5), $0) }
        for (word, count) in words { for bit in stride(from: count - 1, through: 0, by: -1) {
            byte = (byte << 1) | UInt8((word >> bit) & 1); used += 1
            if used == 8 {
                expected.append(byte); used = byte == 0xff ? 1 : 0; byte = 0
            }
        } }
        if used > 0 { expected.append(byte << (8 - used)) }
        for limit in [0, 1, expected.count - 1, expected.count, expected.count + 1] {
            let writer = JPEGLSBitstreamWriter(capacity: 1, maximumBytes: limit)
            for (word, count) in words { writer.writeBits(word, count: count) }
            writer.flush()
            #expect(writer.currentPosition == min(limit, expected.count))
            if limit < expected.count {
                #expect(throws: CodecError.self) { try writer.getData() }
            } else { #expect(try writer.getData() == Data(expected)) }
        }
    }
}
