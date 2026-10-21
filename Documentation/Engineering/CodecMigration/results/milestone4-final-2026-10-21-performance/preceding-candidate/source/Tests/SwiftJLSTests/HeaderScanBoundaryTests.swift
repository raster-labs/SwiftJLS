// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Header entropy scan boundaries")
struct HeaderScanBoundaryTests {
    private func scanPrefix() throws -> Data {
        let input = try ComponentCodecTests().fixture("p8-1x1-max", ext: "jls")
        let header = try JPEGLSHeader.parse(input, budget: .init(limits: .default))
        return input.prefix(header.scan.lowerBound)
    }

    // These test the header directory scanner, not entropy decoding. Synthetic
    // scan bytes let every word lane and checkpoint boundary be exercised
    // independently of the codewords needed to reconstruct a particular image.
    @Test func markerAndFillAtEveryWordLaneAndCheckpointTail() throws {
        let prefix = try scanPrefix()
        for length in Array(1...16) + Array(4088...4112) {
            let entropy = Data(repeating: 0x55, count: length)
            for terminal: [UInt8] in [[0xff, 0xd9], [0xff, 0xff, 0xd9]] {
                let input = prefix + entropy + Data(terminal)
                let header = try JPEGLSHeader.parse(input, budget: .init(limits: .default))
                #expect(header.records.count == 1)
                #expect(header.scans == [prefix.count..<(prefix.count + length)])
            }
        }
    }

    @Test func stuffedFFRemainsEntropyAcrossWordAndCheckpointBoundaries() throws {
        let prefix = try scanPrefix()
        for base in [0, 8, 4088, 4096] {
            for lane in 0..<8 {
                var entropy = Data(repeating: 0x55, count: base + lane)
                entropy.append(contentsOf: [0xff, 0x7f])
                // Resume the word-skip path after the stuffed pair, then test
                // both an exact pair tail and each possible short word tail.
                for tail in 0...16 {
                    let payload = entropy + Data(repeating: 0x33, count: tail)
                    let input = prefix + payload + Data([0xff, 0xd9])
                    let header = try JPEGLSHeader.parse(input, budget: .init(limits: .default))
                    #expect(header.scans == [prefix.count..<(prefix.count + payload.count)])
                }
            }
        }
    }

    @Test func truncatedTerminalFailsAtEveryWordLaneAndCheckpointTail() throws {
        let prefix = try scanPrefix()
        for length in Array(1...16) + Array(4088...4112) {
            let entropy = Data(repeating: 0x55, count: length)
            // Missing EOI, a lone FF, and an unterminated fill sequence must
            // all fail even when the final full word contains no marker byte.
            for tail: [UInt8] in [[], [0xff], [0xff, 0xff]] {
                #expect(throws: CodecError.self) {
                    try JPEGLSHeader.parse(prefix + entropy + Data(tail), budget: .init(limits: .default))
                }
            }
        }
    }
}
