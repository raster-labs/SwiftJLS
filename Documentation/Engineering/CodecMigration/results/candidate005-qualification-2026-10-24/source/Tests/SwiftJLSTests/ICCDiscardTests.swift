// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization
import Testing
@testable import SwiftJLS

private final class ICCReadCounter: ReadOnlyImageStorage {
    let owner: any ReadOnlyImageStorage
    private let borrows = Mutex(0)
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    init(_ owner: any ReadOnlyImageStorage) { self.owner = owner }
    func reset() { borrows.withLock { $0 = 0 } }
    var count: Int { borrows.withLock { $0 } }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R {
        borrows.withLock { $0 += 1 }
        return try owner.withUnsafeBytes(body)
    }
}

@Suite("Explicit ICC discard on encode")
struct ICCDiscardTests {
    private func images(components: Int, icc: Data = Data([1, 2, 3, 4]),
                        metadata: ImageMetadata = .empty) throws -> (Image, Image, ICCReadCounter) {
        let width = 5, height = 3, rowBytes = 14, capacity = rowBytes * height
        let planes = try (0..<components).map { c in
            try PlaneDescriptor(width: width, height: height, components: [c],
                offset: 2 + c * capacity, rowBytes: rowBytes, byteCount: 2 + (c + 1) * capacity)
        }
        func shape(_ profile: Data?) throws -> ImageDescriptor {
            try ImageDescriptor(width: width, height: height, meaningfulBits: 12,
                components: components == 1 ? [.grey] : [.red, .green, .blue],
                colour: components == 1 ? .greyscale : .rgb, planes: planes, iccProfile: profile)
        }
        let plainShape = try shape(nil)
        let pixels = try ImageDestination.allocate(descriptor: plainShape).write { bytes in
            bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
            for c in 0..<components { for y in 0..<height { for x in 0..<width {
                let value = c * 31 + x * 13 + y * 17
                let at = planes[c].offset + y * rowBytes + x * 2
                bytes[at] = UInt8(truncatingIfNeeded: value)
                bytes[at + 1] = UInt8(value >> 8)
            } } }
        }
        let storage = ICCReadCounter(pixels.storage)
        let plain = try Image(descriptor: plainShape, storage: storage, metadata: metadata)
        let profiled = try Image(descriptor: shape(icc), storage: storage, metadata: metadata)
        storage.reset()
        return (plain, profiled, storage)
    }

    private func encoder(_ components: Int) throws -> Encoder {
        try Encoder(configuration: .init(codecOptions:
            .init(restartIntervalLines: 0, interleaveMode: components == 1 ? .none : .sample)))
    }

    private func rejects(_ image: Image, encoder: Encoder, storage: ICCReadCounter,
                         category: CodecError.Category, limits: ResourceLimits = .default,
                         policy: MetadataPolicy = .discardAncillary) async throws {
        storage.reset()
        let callbacks = Mutex(0)
        do {
            _ = try await encoder.encode(image, options: .init(resourceLimits: limits, metadataPolicy: policy,
                progress: { _ in callbacks.withLock { $0 += 1 } }))
            Issue.record("Expected ICC/metadata admission rejection.")
        } catch let error as CodecError {
            #expect(error.category == category)
        }
        #expect(storage.count == 0)
        #expect(callbacks.withLock { $0 } == 0)
    }

    @Test(arguments: [1, 3])
    func explicitDiscardMatchesUnprofiledWithoutCopy(components: Int) async throws {
        let (plain, profiled, storage) = try images(components: components)
        let originalDescriptor = profiled.descriptor
        let encoder = try encoder(components)
        let baseline = try await encoder.encode(plain)
        storage.reset()
        let discarded = try await encoder.encode(profiled, options: .init(metadataPolicy: .discardAncillary))
        #expect(storage.count == 1)
        #expect(discarded.data == baseline.data)
        #expect(discarded.report.pixelAllocationCount == 0 && discarded.report.copyEvents.isEmpty)
        #expect(profiled.descriptor == originalDescriptor)
        #expect(profiled.descriptor.iccProfile == Data([1, 2, 3, 4]))
        #expect(profiled.storage.allocationID == plain.storage.allocationID)
        let decoded = try await Decoder().decode(discarded.data).image
        #expect(decoded.descriptor.iccProfile == nil)
        #expect(decoded.descriptor.colour == originalDescriptor.colour)
        try decoded.storage.withUnsafeBytes { bytes in
            for c in 0..<components {
                let p = decoded.descriptor.planes[c]
                for y in 0..<3 { for x in 0..<5 {
                    let at = p.offset + y * p.rowBytes + x * p.pixelStride
                    #expect(Int(bytes[at]) | Int(bytes[at + 1]) << 8 == c * 31 + x * 13 + y * 17)
                } }
            }
        }
    }

    @Test(arguments: [1, 3])
    func preserveAndUnknownRequiredMetadataRejectBeforeBorrow(components: Int) async throws {
        let encoder = try encoder(components)
        let (_, profiled, storage) = try images(components: components)
        try await rejects(profiled, encoder: encoder, storage: storage, category: .unsupportedFeature, policy: .preserve)
        let required = ImageMetadata(entries: ["required": Data([42])], requiredKeys: ["required"])
        let (_, annotated, annotatedStorage) = try images(components: components, metadata: required)
        try await rejects(annotated, encoder: encoder, storage: annotatedStorage, category: .unsupportedFeature)
    }

    @Test(arguments: [1, 3])
    func knownRequiredMetadataSurvivesICCDiscard(components: Int) async throws {
        let archive = JPEGLSMetadata(segments: try [.init(marker: 0xfe, payload: Data([7, 8, 9]))]).metadata
        let required = ImageMetadata(entries: archive.entries, requiredKeys: [JPEGLSMetadata.key])
        let (plain, profiled, _) = try images(components: components, metadata: required)
        let encoder = try encoder(components)
        let options = EncodeOptions(metadataPolicy: .discardAncillary)
        let expected = try await encoder.encode(plain, options: options)
        let actual = try await encoder.encode(profiled, options: options)
        #expect(actual.data == expected.data)
        let info = try Decoder().inspect(actual.data)
        #expect(info.metadata.entries[JPEGLSMetadata.key] == archive.entries[JPEGLSMetadata.key])
        #expect(info.descriptor.iccProfile == nil)
    }

    @Test(arguments: [1, 3])
    func discardedProfileStillCountsAgainstAdmission(components: Int) async throws {
        let encoder = try encoder(components)
        let (_, profiled, storage) = try images(components: components)
        for limits in [try ResourceLimits(maximumICCBytes: 3), try ResourceLimits(maximumMetadataBytes: 3)] {
            try await rejects(profiled, encoder: encoder, storage: storage, category: .resourceLimitExceeded, limits: limits)
        }
        // Each part fits separately; the retained profile and other metadata
        // must share the ceiling, including RGB's required interpretation bytes.
        let metadata = ImageMetadata(entries: ["a": Data(repeating: 1, count: 8)])
        let (_, annotated, annotatedStorage) = try images(components: components, metadata: metadata)
        let aggregate = try ResourceLimits(maximumMetadataBytes: 12 + (components == 3 ? 30 : 0))
        try await rejects(annotated, encoder: encoder, storage: annotatedStorage,
                          category: .resourceLimitExceeded, limits: aggregate)
        let (plain, large, largeStorage) = try images(components: components, icc: Data(repeating: 1, count: 128 * 1024))
        let memory = try ResourceLimits(maximumMemoryBytes: 128 * 1024)
        _ = try await encoder.encode(plain, options: .init(resourceLimits: memory, metadataPolicy: .discardAncillary))
        try await rejects(large, encoder: encoder, storage: largeStorage, category: .resourceLimitExceeded, limits: memory)
    }

    @Test(arguments: [1, 3])
    func decodeCannotSilentlyDiscardDestinationICC(components: Int) async throws {
        let (plain, profiled, _) = try images(components: components)
        let encoded = try await encoder(components).encode(plain)
        let destination = try ImageDestination.allocate(descriptor: profiled.descriptor)
        do {
            _ = try await Decoder().decode(encoded.data, into: destination,
                                           options: .init(metadataPolicy: .discardAncillary))
            Issue.record("Decode must not reinterpret a profiled destination.")
        } catch let error as CodecError {
            #expect(error.category == .unsupportedFeature)
        }
        let reusable = try destination.write { $0.initializeMemory(as: UInt8.self, repeating: 0) }
        #expect(reusable.storage.allocationID == destination.storage.allocationID)
        #expect(reusable.descriptor.iccProfile == profiled.descriptor.iccProfile)
    }
}
