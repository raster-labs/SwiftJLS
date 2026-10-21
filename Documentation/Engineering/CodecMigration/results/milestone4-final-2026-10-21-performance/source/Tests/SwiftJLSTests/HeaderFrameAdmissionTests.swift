// SPDX-License-Identifier: Apache-2.0
import Testing
@testable import SwiftJLS

@Suite("Header frame admission")
struct HeaderFrameAdmissionTests {
    private func rejection(_ operation: () throws -> Void) throws -> CodecError? {
        do {
            try operation()
            return nil
        } catch let error as CodecError {
            return error
        } catch {
            throw error
        }
    }

    @Test func matchesDescriptorLimitsOverflowAndErrorOrder() throws {
        let geometries = [(1, 1), (2, 2), (37, 23), (65537, 1), (1, 65537),
                          (0, 1), (-1, 1), (1, 0), (Int.max, 1),
                          (Int.max / 2 + 1, 1), (Int.max / 2, 2), (1, Int.max)]
        let limits = try [ResourceLimits.default,
            ResourceLimits(maximumDecodedBytes: 1, maximumPixels: 1, maximumDimension: 1),
            ResourceLimits(maximumDecodedBytes: 1, maximumPixels: 3, maximumDimension: 2),
            ResourceLimits(maximumDecodedBytes: 7, maximumPixels: 4, maximumDimension: 2),
            ResourceLimits(maximumDecodedBytes: 8, maximumPixels: 4, maximumDimension: 2),
            // Total-memory admission belongs to the surrounding parser budget;
            // this extent check must preserve the descriptor's narrower scope.
            ResourceLimits(maximumMemoryBytes: 1)]
        for (width, height) in geometries {
            for bits in [0, 1, 2, 12, 16, 17] {
                for limit in limits {
                    let expected = try rejection {
                        _ = try ImageDescriptor.greyscale16(width: width, height: height,
                            meaningfulBits: bits, limits: limit)
                    }
                    let actual = try rejection {
                        try JPEGLSHeader.validateFrameAdmission(width: width, height: height,
                            meaningfulBits: bits, limits: limit)
                    }
                    #expect(actual == expected)
                }
            }
        }
    }
}
