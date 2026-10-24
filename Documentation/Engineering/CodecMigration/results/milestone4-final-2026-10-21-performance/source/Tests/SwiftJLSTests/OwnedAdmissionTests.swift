// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Owned destination admission and required metadata")
struct OwnedAdmissionTests {
    @Test func requiredMetadataMembershipAndErrorOrder() throws {
        let missing = ImageMetadata(entries: ["present": Data([1])], requiredKeys: ["absent"])
        let tiny = try ResourceLimits(maximumMetadataBytes: 1)
        #expect(throws: CodecError(.invalidArgument, "Required metadata has no value.")) {
            try missing.validate(limits: tiny, additionalBytes: Int.max)
        }
        // Empty Data is a present value, and UTF-8 key bytes still count.
        let emptyValue = ImageMetadata(entries: ["é": Data()], requiredKeys: ["é"])
        #expect(try emptyValue.validate(limits: ResourceLimits(maximumMetadataBytes: 2)) == 2)
        #expect(throws: CodecError(.resourceLimitExceeded, "Metadata limit exceeded.")) {
            try emptyValue.validate(limits: tiny)
        }
        let mixed = ImageMetadata(entries: ["r": Data(), "extra": Data([1])], requiredKeys: ["r"])
        #expect(try mixed.validate(limits: ResourceLimits(maximumMetadataBytes: 7)) == 7)
        #expect(throws: CodecError(.resourceLimitExceeded, "Metadata limit exceeded.")) {
            try mixed.validate(limits: ResourceLimits(maximumMetadataBytes: 6))
        }
        #expect(try ImageMetadata.empty.validate(limits: tiny) == 0)
        #expect(throws: CodecError(.resourceLimitExceeded, "Metadata limit exceeded.")) {
            try ImageMetadata.empty.validate(limits: tiny, additionalBytes: 2)
        }
    }

    @Test func ownedAllocationKeepsAdmissionOrderAndExactLimits() throws {
        let plane = try PlaneDescriptor(width: 3, height: 2, rowBytes: 6, byteCount: 12)
        let descriptor = try ImageDescriptor(width: 3, height: 2, planes: [plane], iccProfile: Data([1, 2, 3, 4]))
        let descriptorError = CodecError(.resourceLimitExceeded, "Image descriptor exceeds operation limits.")
        for limits in [
            try ResourceLimits(maximumDecodedBytes: 11, maximumMemoryBytes: 1),
            try ResourceLimits(maximumPixels: 5, maximumMemoryBytes: 1),
            try ResourceLimits(maximumDimension: 2, maximumMemoryBytes: 1),
            try ResourceLimits(maximumICCBytes: 3, maximumMemoryBytes: 1),
            try ResourceLimits(maximumMetadataBytes: 3, maximumMemoryBytes: 1)
        ] {
            #expect(throws: descriptorError) {
                try ImageDestination.allocate(descriptor: descriptor, limits: limits)
            }
        }
        #expect(throws: CodecError(.resourceLimitExceeded, "Destination exceeds the admission budget.")) {
            try ImageDestination.allocate(descriptor: descriptor, limits: ResourceLimits(maximumMemoryBytes: 15))
        }
        let exact = try ResourceLimits(maximumDecodedBytes: 12, maximumMetadataBytes: 4,
            maximumICCBytes: 4, maximumMemoryBytes: 16)
        let destination = try ImageDestination.allocate(descriptor: descriptor, limits: exact)
        #expect(destination.storage.byteCount == 12)
        let image = try destination.writeUInt16 { x, y in UInt16(x + 3 * y) }
        #expect(image.descriptor == descriptor)
        #expect(try image.sampleUInt16(x: 2, y: 1) == 5)
    }

    @Test func cancellationStillFollowsDescriptorPreflight() async throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 2, height: 1)
        let invalid = try ResourceLimits(maximumDecodedBytes: 3)
        let rejected = Task {
            withUnsafeCurrentTask { $0?.cancel() }
            _ = try ImageDestination.allocate(descriptor: descriptor, limits: invalid)
        }
        await #expect(throws: CodecError(.resourceLimitExceeded, "Image descriptor exceeds operation limits.")) {
            try await rejected.value
        }
        let cancelled = Task {
            withUnsafeCurrentTask { $0?.cancel() }
            _ = try ImageDestination.allocate(descriptor: descriptor)
        }
        await #expect(throws: CancellationError.self) { try await cancelled.value }
    }
}
