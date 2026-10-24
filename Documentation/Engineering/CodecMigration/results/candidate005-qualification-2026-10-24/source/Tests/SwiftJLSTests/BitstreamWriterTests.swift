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
            var writer = JPEGLSBitstreamWriter(capacity: 1, maximumBytes: limit)
            for (word, count) in words { writer.writeBits(word, count: count) }
            writer.flush()
            #expect(writer.currentPosition == min(limit, expected.count))
            if limit < expected.count {
                #expect(throws: CodecError.self) { try writer.getData() }
            } else { #expect(try writer.getData() == Data(expected)) }
        }
    }

    @Test func unaryWindowStuffingOracleAndBoundaryRejection() throws {
        // 1. Algebraic equivalence across all valid bitsInBuffer (1...63) and high-bit garbage patterns.
        let patterns: [UInt64] = [
            0, 1, UInt64.max, 0x8000_0000_0000_0000, 0xFFFF_FFFF_0000_0000,
            0xAAAA_AAAA_AAAA_AAAA, 0x5555_5555_5555_5555, 0xF0F0_F0F0_0F0F_0F0F,
        ]
        for b in 1...63 {
            let boundaryPatterns = patterns + [
                (UInt64(1) << UInt64(b)) &- 1,
                ~((UInt64(1) << UInt64(b)) &- 1),
                UInt64(1) << UInt64(b - 1),
                UInt64(1) << UInt64(b),
            ]
            for x in boundaryPatterns {
                let masked = (x & ((UInt64(1) << UInt64(b)) &- 1)) << UInt64(64 - b)
                let unmasked = x &<< (64 &- b)
                #expect(unmasked == masked)
                #expect((x << UInt64(64 - b)) == masked)
                #expect(min(unmasked.leadingZeroBitCount, b) == min(masked.leadingZeroBitCount, b))
            }
        }

        // 2. Independent bit-by-bit oracle over mixed readBits(1...32), unary runs (0...190),
        //    high consumed bits in bitBuffer, and 0xFF7F stuffing across refill boundaries.
        enum Op {
            case bits(UInt32, Int)
            case unary(Int)
        }
        var ops: [Op] = [
            .bits(0xFFFF_FFFF, 32), // leaves all-1s in high bits of bitBuffer and emits 0xFF7F stuffed pairs
            .unary(0),
            .bits(0b1111_111, 7),
            .unary(0),
            .bits(0xFF, 8),
            .unary(15),
            .bits(0xFF, 8),
            .bits(0x7F, 7),
            .unary(1),
            .bits(0xDEAD_BEEF, 31), // unmasked 32-bit literal with 31-bit width
            .unary(63),             // full window of zeros after high 1-bits
            .bits(0x7FFF_FFFF, 31),
            .unary(190),            // multi-refill unary prefix
        ]
        for step in 0..<48 {
            let width = (step % 32) + 1
            let mask: UInt64 = width == 64 ? UInt64.max : ((UInt64(1) << UInt64(width)) - 1)
            let raw = UInt32(truncatingIfNeeded: (UInt64(step + 1) &* 0x9E37_79B9_7F4A_7C15) & mask)
            ops.append(.bits(raw | 1, width))
            ops.append(.unary((step * 7) % 95))
        }

        var writer = JPEGLSBitstreamWriter(capacity: 512, maximumBytes: 16384)
        var rawBitOracle: [UInt8] = []
        for op in ops {
            switch op {
            case let .bits(val, count):
                writer.writeBits(val, count: count)
                for b in stride(from: count - 1, through: 0, by: -1) {
                    rawBitOracle.append(UInt8((val >> b) & 1))
                }
            case let .unary(zeros):
                var rem = zeros
                while rem >= 31 {
                    writer.writeBits(0, count: 31)
                    rem -= 31
                }
                if rem > 0 {
                    writer.writeBits(0, count: rem)
                }
                writer.writeBits(1, count: 1)
                rawBitOracle.append(contentsOf: repeatElement(0, count: zeros))
                rawBitOracle.append(1)
            }
        }
        writer.flush()
        let encoded = try writer.getData()
        #expect(encoded.count == 403)
        #expect(encoded.ranges(of: Data([0xFF, 0x7F])).isEmpty == false)

        let reader = JPEGLSBitstreamReader(data: encoded)
        let bitByBitReader = JPEGLSBitstreamReader(data: encoded)
        var oracleCursor = 0
        for op in ops {
            switch op {
            case let .bits(expectedVal, count):
                let actual = try reader.readBits(count)
                var bitRef: UInt32 = 0
                for _ in 0..<count {
                    let bit = try bitByBitReader.readBits(1)
                    #expect(bit == UInt32(rawBitOracle[oracleCursor]))
                    oracleCursor += 1
                    bitRef = (bitRef << 1) | bit
                }
                let widthMask: UInt32 = count < 32 ? ((UInt32(1) << count) - 1) : UInt32.max
                #expect(actual == (expectedVal & widthMask))
                #expect(actual == bitRef)
            case let .unary(expectedZeros):
                let actualZeros = try reader.readUnaryCount(maximum: expectedZeros)
                var refZeros = 0
                while true {
                    let bit = try bitByBitReader.readBits(1)
                    #expect(bit == UInt32(rawBitOracle[oracleCursor]))
                    oracleCursor += 1
                    if bit == 1 { break }
                    refZeros += 1
                }
                #expect(actualZeros == expectedZeros)
                #expect(actualZeros == refZeros)
            }
        }
        try reader.validateEndOfScan()
        try bitByBitReader.validateEndOfScan()

        // 3. Maximum-prefix acceptance at exact limit, rejection at one-bit-over, and 0xFF00 stuffing.
        for limit in [0, 1, 7, 15, 31, 63, 64, 130] {
            var w = JPEGLSBitstreamWriter(capacity: 64, maximumBytes: 256)
            w.writeBits(0xFF, count: 8) // high 1-bits + 0xFF00 stuffing when followed by >= 7 zero bits
            var rem = limit + 1
            while rem >= 31 { w.writeBits(0, count: 31); rem -= 31 }
            if rem > 0 { w.writeBits(0, count: rem) }
            w.writeBits(1, count: 1)
            w.flush()
            let stream = try w.getData()
            if limit >= 7 {
                #expect(stream.starts(with: [0xFF, 0x00]))
            }

            let acceptReader = JPEGLSBitstreamReader(data: stream)
            #expect(try acceptReader.readBits(8) == 0xFF)
            #expect(try acceptReader.readUnaryCount(maximum: limit + 1) == limit + 1)
            try acceptReader.validateEndOfScan()

            let rejectReader = JPEGLSBitstreamReader(data: stream)
            #expect(try rejectReader.readBits(8) == 0xFF)
            #expect(throws: CodecError.self) {
                _ = try rejectReader.readUnaryCount(maximum: limit)
            }
        }

        // 4. Single-remaining-bit windows after 7 consumed 1-bits:
        //    (a) Data([0xFF]): last bit is 1 -> unary count 0 and clean end of scan.
        let singleBitTerminated = JPEGLSBitstreamReader(data: Data([0xFF]))
        #expect(try singleBitTerminated.readBits(7) == 127)
        #expect(try singleBitTerminated.readUnaryCount(maximum: 0) == 0)
        try singleBitTerminated.validateEndOfScan()

        //    (b) Data([0xFE]): last bit is 0 -> stale high 1-bits must not terminate unary scan.
        let singleBitUnterminated = JPEGLSBitstreamReader(data: Data([0xFE]))
        #expect(try singleBitUnterminated.readBits(7) == 127)
        #expect(throws: JPEGLSError.self) {
            _ = try singleBitUnterminated.readUnaryCount(maximum: 1)
        }

        // 5. Truncated zero prefix (prematureEndOfStream) after high consumed 1-bits, and scan padding checks.
        let truncated = JPEGLSBitstreamReader(data: Data([0b1111_0000, 0b0000_0000]))
        #expect(try truncated.readBits(4) == 0b1111)
        #expect(throws: JPEGLSError.self) {
            _ = try truncated.readUnaryCount(maximum: 64)
        }

        let validPad = JPEGLSBitstreamReader(data: Data([0b1110_0000]))
        #expect(try validPad.readBits(3) == 0b111)
        try validPad.validateEndOfScan()

        let invalidPad = JPEGLSBitstreamReader(data: Data([0b1110_0001]))
        #expect(try invalidPad.readBits(3) == 0b111)
        #expect(throws: CodecError.self) {
            try invalidPad.validateEndOfScan()
        }
    }
}
