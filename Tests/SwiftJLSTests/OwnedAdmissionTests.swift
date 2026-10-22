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

    @Test func admittedOwnedWriteRejectsPostFillCancellationAndInvalidatesStorage() async throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 2, height: 1)
        let destination = try ImageDestination.allocate(descriptor: descriptor)
        let cancelledWrite = Task {
            try destination.write { bytes in
                bytes.initializeMemory(as: UInt8.self, repeating: 0)
                withUnsafeCurrentTask { $0?.cancel() }
            }
        }
        await #expect(throws: CancellationError.self) { try await cancelledWrite.value }
        #expect(throws: CodecError(.storageUnavailable, "Destination was already used.")) {
            _ = try destination.write { $0.initializeMemory(as: UInt8.self, repeating: 0) }
        }
        #expect(throws: CodecError(.storageUnavailable, "Storage already has a writer or is sealed/invalid.")) {
            _ = try destination.storage.reserveWrite()
        }

        let destinationUInt16 = try ImageDestination.allocate(descriptor: descriptor)
        let cancelledUInt16 = Task {
            try destinationUInt16.writeUInt16 { x, _ in
                if x == 1 {
                    withUnsafeCurrentTask { $0?.cancel() }
                }
                return 0
            }
        }
        await #expect(throws: CancellationError.self) { try await cancelledUInt16.value }
        #expect(throws: CodecError(.storageUnavailable, "Storage already has a writer or is sealed/invalid.")) {
            _ = try destinationUInt16.storage.reserveWrite()
        }
    }

    @Test func ownedDecodeAndInspectReuseAdmittedDescriptorAndKeepBudgetGuards() async throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 4, height: 3, meaningfulBits: 12)
        let source = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { x, y in
            UInt16((x * 17 + y * 31) & 0x0FFF)
        }
        let encoded = try await Encoder().encode(source)
        let info = try Decoder().inspect(encoded.data)
        #expect(info.descriptor == descriptor)

        let decodedOwned = try await Decoder().decode(encoded.data)
        #expect(decodedOwned.image.descriptor == descriptor)
        #expect(decodedOwned.report.pixelAllocationCount == 1)
        #expect(decodedOwned.report.peakPixelBytes == 24)
        for y in 0..<3 {
            for x in 0..<4 {
                #expect(try decodedOwned.image.sampleUInt16(x: x, y: y) == UInt16((x * 17 + y * 31) & 0x0FFF))
            }
        }

        let supplied = try ImageDestination.allocate(descriptor: descriptor)
        let decodedInto = try await Decoder().decode(encoded.data, into: supplied)
        #expect(decodedInto.image.descriptor == descriptor)
        #expect(decodedInto.report.pixelAllocationCount == 0)
        #expect(decodedInto.report.peakPixelBytes == 0)

        let tightDecodedLimits = try ResourceLimits(maximumDecodedBytes: 23)
        await #expect(throws: CodecError(.resourceLimitExceeded, "Decoded storage limit exceeded.")) {
            _ = try await Decoder().decode(encoded.data, options: .init(resourceLimits: tightDecodedLimits))
        }
        let tightMemoryLimits = try ResourceLimits(maximumMemoryBytes: encoded.data.count + 24)
        await #expect(throws: CodecError(.resourceLimitExceeded, "Codec operation exceeds its memory budget.")) {
            _ = try await Decoder().decode(encoded.data, options: .init(resourceLimits: tightMemoryLimits))
        }
    }

    @Test func ownedWriteMetadataPreflightRejectsBeforeStartAndRetainsReservationForRetry() throws {
        let plane = try PlaneDescriptor(width: 1, height: 1, rowBytes: 2, byteCount: 2)
        let descriptor = try ImageDescriptor(width: 1, height: 1, planes: [plane], iccProfile: Data([0xAA, 0xBB]))
        let meta2 = ImageMetadata(entries: ["a": Data([0xCC])], requiredKeys: ["a"])

        // 1. Exact pixel (2) + ICC (2) + metadata (2) = 6 capacity succeeds.
        let exactLimits = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 4, maximumICCBytes: 2, maximumMemoryBytes: 6
        )
        let exactDest = try ImageDestination.allocate(descriptor: descriptor, limits: exactLimits)
        let exactImg = try exactDest.write(metadata: meta2) { bytes in
            bytes[0] = 0x34
            bytes[1] = 0x12
        }
        #expect(exactImg.storage.allocationID == exactDest.storage.allocationID)
        #expect(try exactImg.sampleUInt16(x: 0, y: 0) == 0x1234)
        #expect(exactImg.metadata == meta2)

        // 2. Missing required key and 1-byte-short aggregate memory limit (5 vs 6) reject before
        // fill starts, and corrected metadata can then reuse the same destination reservation.
        let shortMemLimits = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 4, maximumICCBytes: 2, maximumMemoryBytes: 5
        )
        let retryMemDest = try ImageDestination.allocate(descriptor: descriptor, limits: shortMemLimits)
        var fillRan = false
        let missingKeyMeta = ImageMetadata(entries: ["a": Data([0xCC])], requiredKeys: ["missing"])
        #expect(throws: CodecError(.invalidArgument, "Required metadata has no value.")) {
            _ = try retryMemDest.write(metadata: missingKeyMeta) { _ in fillRan = true }
        }
        #expect(!fillRan)
        #expect(throws: CodecError(.resourceLimitExceeded, "Destination and metadata exceed the admission budget.")) {
            _ = try retryMemDest.write(metadata: meta2) { _ in fillRan = true }
        }
        #expect(!fillRan)
        let retriedMemImg = try retryMemDest.write(metadata: .empty) { bytes in
            fillRan = true
            bytes[0] = 0x78
            bytes[1] = 0x56
        }
        #expect(fillRan)
        #expect(retriedMemImg.storage.allocationID == retryMemDest.storage.allocationID)
        #expect(try retriedMemImg.sampleUInt16(x: 0, y: 0) == 0x5678)
        #expect(retriedMemImg.metadata == .empty)

        // 3. 1-byte-short metadata limit (maximumMetadataBytes: 3 vs ICC 2 + meta 2 = 4) rejects
        // before fill starts, and 1-byte metadata (ICC 2 + meta 1 = 3) reuses the same destination.
        let shortMetaLimits = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 3, maximumICCBytes: 2, maximumMemoryBytes: 6
        )
        let retryMetaDest = try ImageDestination.allocate(descriptor: descriptor, limits: shortMetaLimits)
        var metaFillRan = false
        #expect(throws: CodecError(.resourceLimitExceeded, "Metadata limit exceeded.")) {
            _ = try retryMetaDest.write(metadata: meta2) { _ in metaFillRan = true }
        }
        #expect(!metaFillRan)
        let meta1 = ImageMetadata(entries: ["a": Data()], requiredKeys: ["a"])
        let retriedMetaImg = try retryMetaDest.write(metadata: meta1) { bytes in
            metaFillRan = true
            bytes[0] = 0xBC
            bytes[1] = 0x9A
        }
        #expect(metaFillRan)
        #expect(retriedMetaImg.storage.allocationID == retryMetaDest.storage.allocationID)
        #expect(try retriedMetaImg.sampleUInt16(x: 0, y: 0) == 0x9ABC)
        #expect(retriedMetaImg.metadata == meta1)
    }

    @Test func freshOwnedFactoryLifecycleMetadataAndLimits() async throws {
        let plane = try PlaneDescriptor(width: 1, height: 1, rowBytes: 2, byteCount: 2)
        let descriptor = try ImageDescriptor(width: 1, height: 1, planes: [plane], iccProfile: Data([0xAA, 0xBB]))
        let meta = ImageMetadata(entries: ["a": Data([0xCC])], requiredKeys: ["a"])
        let exactLimits = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 4, maximumICCBytes: 2, maximumMemoryBytes: 6
        )

        var fillRan = false
        let missingKey = ImageMetadata(entries: ["a": Data([0xCC])], requiredKeys: ["missing"])
        #expect(throws: CodecError(.invalidArgument, "Required metadata has no value.")) {
            _ = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: missingKey, limits: exactLimits) { _ in
                fillRan = true
            }
        }
        #expect(!fillRan)

        let shortDecoded = try ResourceLimits(
            maximumDecodedBytes: 1, maximumMetadataBytes: 4, maximumICCBytes: 2, maximumMemoryBytes: 6
        )
        #expect(throws: CodecError(.resourceLimitExceeded, "Storage allocation exceeds the admission budget.")) {
            _ = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: shortDecoded) { _ in
                fillRan = true
            }
        }
        #expect(!fillRan)

        let shortICCMem = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 4, maximumICCBytes: 2, maximumMemoryBytes: 3
        )
        #expect(throws: CodecError(.resourceLimitExceeded, "Storage allocation exceeds the admission budget.")) {
            _ = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: shortICCMem) { _ in
                fillRan = true
            }
        }
        #expect(!fillRan)

        let shortMeta = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 3, maximumICCBytes: 2, maximumMemoryBytes: 6
        )
        #expect(throws: CodecError(.resourceLimitExceeded, "Metadata limit exceeded.")) {
            _ = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: shortMeta) { _ in
                fillRan = true
            }
        }
        #expect(!fillRan)

        let shortCombined = try ResourceLimits(
            maximumDecodedBytes: 2, maximumMetadataBytes: 4, maximumICCBytes: 2, maximumMemoryBytes: 5
        )
        #expect(throws: CodecError(.resourceLimitExceeded, "Destination and metadata exceed the admission budget.")) {
            _ = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: shortCombined) { _ in
                fillRan = true
            }
        }
        #expect(!fillRan)

        let first = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: exactLimits) { bytes in
            #expect(bytes.count == 2)
            #expect(bytes.allSatisfy { $0 == 0 })
            bytes[0] = 0x34
            bytes[1] = 0x12
        }
        let second = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: exactLimits) { bytes in
            #expect(bytes.allSatisfy { $0 == 0 })
            bytes[0] = 0x78
            bytes[1] = 0x56
        }
        #expect(first.storage.allocationID != second.storage.allocationID)
        #expect(first.storage.byteCount == 2)
        #expect(first.metadata == meta)
        #expect(try first.sampleUInt16(x: 0, y: 0) == 0x1234)
        #expect(try second.sampleUInt16(x: 0, y: 0) == 0x5678)

        let fillFailure = CodecError(.malformedInput, "Simulated fill failure.")
        #expect(throws: fillFailure) {
            _ = try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: exactLimits) { bytes in
                bytes[0] = 0xFF
                throw fillFailure
            }
        }

        let cancelledBefore = Task {
            withUnsafeCurrentTask { $0?.cancel() }
            return try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: exactLimits) { _ in }
        }
        await #expect(throws: CancellationError.self) { _ = try await cancelledBefore.value }

        let cancelledDuringFill = Task {
            try Image.writeAdmittedOwned(descriptor: descriptor, metadata: meta, limits: exactLimits) { bytes in
                bytes[0] = 1
                withUnsafeCurrentTask { $0?.cancel() }
            }
        }
        await #expect(throws: CancellationError.self) { _ = try await cancelledDuringFill.value }
    }

    @Test func ownedAndSuppliedDecodeMetadataPolicyFidelityAndDestinationLimits() async throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 2, height: 2, meaningfulBits: 2)
        let comment = try JPEGLSMetadata.Segment(marker: 0xFE, payload: Data([0x41, 0x42]))
        let ancillary = JPEGLSMetadata(segments: [comment]).metadata
        let table = try JPEGLSMappingTable(id: 1, entryWidth: 2, entries: [0, 10, 50, 400])
        let mapping = try JPEGLSMappingTables(tables: [table], componentTableIDs: [1]).metadata
        let combinedMeta = ImageMetadata(
            entries: ancillary.entries.merging(mapping.entries) { _, new in new },
            requiredKeys: mapping.requiredKeys
        )
        let source = try Image.writeAdmittedOwned(
            descriptor: descriptor, metadata: combinedMeta, limits: .default
        ) { bytes in
            for (i, sample) in [UInt16(0), 1, 2, 3].enumerated() {
                bytes[i * 2] = UInt8(sample & 0xFF)
                bytes[i * 2 + 1] = UInt8(sample >> 8)
            }
        }
        let config = try EncoderConfiguration(mode: .nearLossless(maximumAbsoluteError: 1))
        let encoded = try await Encoder(configuration: config).encode(source)

        // 1. Owned decode with mappingOutputPrecision and .preserve computes mapped NEAR
        // fidelity (max adjacent step for NEAR=1 in [0, 10, 50, 400] is 350) and keeps COM.
        let mappedOptions = try CodecOptions(restartIntervalLines: 0, mappingOutputPrecision: 12)
        let mappedDecoder = try Decoder(configuration: .init(codecOptions: mappedOptions))
        let ownedMapped = try await mappedDecoder.decode(
            encoded.data, options: .init(metadataPolicy: .preserve)
        )
        #expect(ownedMapped.report.fidelity == Fidelity.boundedError(350))
        #expect(ownedMapped.report.pixelAllocationCount == 1)
        #expect(ownedMapped.report.peakPixelBytes == 8)
        #expect(ownedMapped.image.descriptor.meaningfulBits == 12)
        #expect(ownedMapped.image.metadata.entries[JPEGLSMetadata.key] != nil)
        #expect(ownedMapped.image.metadata.entries[JPEGLSMappingTables.key] == nil)

        // 2. Owned decode with .discardAncillary removes non-required COM while retaining
        // required mapping table metadata when samples remain unmapped indices.
        let ownedDiscarded = try await Decoder().decode(
            encoded.data, options: .init(metadataPolicy: .discardAncillary)
        )
        #expect(ownedDiscarded.report.fidelity == Fidelity.boundedError(1))
        #expect(ownedDiscarded.image.storage.allocationID != ownedMapped.image.storage.allocationID)
        #expect(ownedDiscarded.image.metadata.entries[JPEGLSMetadata.key] == nil)
        #expect(ownedDiscarded.image.metadata.entries[JPEGLSMappingTables.key] != nil)
        #expect(ownedDiscarded.image.metadata.requiredKeys.contains(JPEGLSMappingTables.key))

        // 3. Supplied destination with narrower construction metadata/memory limits rejects
        // .preserve before fill and retains its reservation for a .discardAncillary retry.
        let mappedDescriptor = try ImageDescriptor.greyscale16(width: 2, height: 2, meaningfulBits: 12)
        let narrowDestLimits = try ResourceLimits(
            maximumDecodedBytes: 8, maximumMetadataBytes: 1, maximumMemoryBytes: 8
        )
        let supplied = try ImageDestination.allocate(descriptor: mappedDescriptor, limits: narrowDestLimits)
        await #expect(throws: CodecError(.resourceLimitExceeded, "Metadata limit exceeded.")) {
            _ = try await mappedDecoder.decode(
                encoded.data, into: supplied,
                options: .init(resourceLimits: .default, metadataPolicy: .preserve)
            )
        }
        let retried = try await mappedDecoder.decode(
            encoded.data, into: supplied,
            options: .init(resourceLimits: .default, metadataPolicy: .discardAncillary)
        )
        #expect(retried.report.fidelity == Fidelity.boundedError(350))
        #expect(retried.report.pixelAllocationCount == 0)
        #expect(retried.report.peakPixelBytes == 0)
        #expect(retried.image.storage.allocationID == supplied.storage.allocationID)
        #expect(retried.image.metadata == ImageMetadata.empty)

        let narrowCombinedDestLimits = try ResourceLimits(
            maximumDecodedBytes: 8, maximumMetadataBytes: 64, maximumMemoryBytes: 8
        )
        let suppliedCombined = try ImageDestination.allocate(
            descriptor: mappedDescriptor, limits: narrowCombinedDestLimits
        )
        await #expect(throws: CodecError(.resourceLimitExceeded, "Destination and metadata exceed the admission budget.")) {
            _ = try await mappedDecoder.decode(
                encoded.data, into: suppliedCombined,
                options: .init(resourceLimits: .default, metadataPolicy: .preserve)
            )
        }
        let retriedCombined = try await mappedDecoder.decode(
            encoded.data, into: suppliedCombined,
            options: .init(resourceLimits: .default, metadataPolicy: .discardAncillary)
        )
        #expect(retriedCombined.image.storage.allocationID == suppliedCombined.storage.allocationID)
        #expect(retriedCombined.image.metadata == ImageMetadata.empty)
    }
}
