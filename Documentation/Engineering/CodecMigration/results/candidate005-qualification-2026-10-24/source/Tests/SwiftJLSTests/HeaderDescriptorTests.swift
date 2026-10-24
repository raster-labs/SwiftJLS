// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Parsed header descriptor reuse")
struct HeaderDescriptorTests {
    @Test func reusedLayoutRechecksRequestedLimits() throws {
        // Exercise grey, interpreted RGB, uninterpreted components, and unequal
        // sampling planes: each parsed layout remains subject to later limits.
        for name in ["p12-33x9-zero", "c3-i0-p2-n0-17x13-noise",
                     "c3-i2-p8-n3-33x9-flat", "subsampled-zero-n0"] {
            let data = try ComponentCodecTests().fixture(name, ext: "jls")
            let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
            let descriptor = try header.descriptor(limits: .default)
            let pixels = descriptor.width * descriptor.height
            let dimension = max(descriptor.width, descriptor.height)
            let exact = try ResourceLimits(maximumDecodedBytes: descriptor.requiredByteCount,
                maximumPixels: pixels, maximumDimension: dimension)
            #expect(try header.descriptor(limits: exact) == descriptor)

            let smallDimension = try ResourceLimits(maximumDimension: dimension - 1)
            #expect(throws: CodecError(.resourceLimitExceeded, "Image dimension limit exceeded.")) {
                try header.descriptor(limits: smallDimension)
            }
            let smallPixels = try ResourceLimits(maximumPixels: pixels - 1)
            #expect(throws: CodecError(.resourceLimitExceeded, "Image pixel limit exceeded.")) {
                try header.descriptor(limits: smallPixels)
            }
            let smallCapacity = try ResourceLimits(maximumDecodedBytes: descriptor.requiredByteCount - 1)
            #expect(throws: CodecError(.resourceLimitExceeded, "Decoded storage limit exceeded.")) {
                try header.descriptor(limits: smallCapacity)
            }
            // A rejected request must neither invalidate nor relax the layout.
            #expect(try header.descriptor(limits: exact) == descriptor)
            #expect(try header.descriptor(limits: .default) == descriptor)
        }
    }
}
