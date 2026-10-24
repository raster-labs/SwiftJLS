// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization
import Testing
import SwiftJLS

@Suite("Initial marker fill and inspection progress policy")
struct MarkerFillInspectPolicyTests {
    private func fixture() throws -> Data {
        try ComponentCodecTests().fixture("p8-1x1-max", ext: "jls")
    }

    @Test func leadingFillPreservesSamplesAndSuppliedStorage() async throws {
        let original = try fixture()
        let decoder = try Decoder()
        // JLSwift d175 accepts these prefixes. Include both sides of the
        // parser's bounded cancellation checkpoint as well as sliced Data.
        for count in [0, 1, 2, 7, 4095, 4096, 4097] {
            let filled = Data(repeating: 255, count: count) + original
            for slicePrefix in [0, 3] {
                let input = (Data(repeating: 7, count: slicePrefix) + filled).dropFirst(slicePrefix)
                let info = try decoder.inspect(input)
                #expect(info.descriptor.width == 1 && info.descriptor.height == 1)
                let owned = try await decoder.decode(input)
                #expect(try owned.image.sampleUInt16(x: 0, y: 0) == 255)
                let destination = try ImageDestination.allocate(descriptor: info.descriptor)
                let supplied = try await decoder.decode(input, into: destination)
                #expect(supplied.image.storage.allocationID == destination.storage.allocationID)
                #expect(supplied.report.pixelAllocationCount == 0 && supplied.report.copyEvents.isEmpty)
                #expect(try supplied.image.sampleUInt16(x: 0, y: 0) == 255)
            }
        }
    }

    @Test func dicomPaddingParityIncludesLeadingFill() async throws {
        let original = try fixture()
        let decoder = try Decoder()
        let descriptor = try decoder.inspect(original).descriptor
        for addComment in [false, true] {
            var stream = original
            // Five bytes change parity without changing any decoded samples.
            if addComment { stream.insert(contentsOf: [255, 254, 0, 3, 65], at: 2) }
            for fillCount in [1, 2] {
                let filled = Data(repeating: 255, count: fillCount) + stream
                let padded = (Data([7, 7, 7]) + filled + Data([0])).dropFirst(3)
                let destination = try ImageDestination.allocate(descriptor: descriptor)
                if filled.count % 2 == 1 {
                    #expect(try decoder.inspect(padded).descriptor == descriptor)
                    let owned = try await decoder.decode(padded)
                    #expect(try owned.image.sampleUInt16(x: 0, y: 0) == 255)
                    let supplied = try await decoder.decode(padded, into: destination)
                    #expect(supplied.image.storage.allocationID == destination.storage.allocationID)
                    #expect(try supplied.image.sampleUInt16(x: 0, y: 0) == 255)
                } else {
                    #expect(throws: CodecError.self) { try decoder.inspect(padded) }
                    await #expect(throws: CodecError.self) { try await decoder.decode(padded) }
                    await #expect(throws: CodecError.self) { try await decoder.decode(padded, into: destination) }
                    let recovered = try await decoder.decode(filled, into: destination)
                    #expect(try recovered.image.sampleUInt16(x: 0, y: 0) == 255)
                }
            }
        }
    }

    @Test func truncatedFillAndCompressedLimitsPreserveReservation() async throws {
        let original = try fixture()
        let decoder = try Decoder()
        let descriptor = try decoder.inspect(original).descriptor
        for input in [Data(), Data([255]), Data([255, 255]),
                      Data(repeating: 255, count: 4097), Data([255, 255, 0]),
                      Data([255, 255, 217]), Data([255, 255, 216])] {
            #expect(throws: CodecError.self) { try decoder.inspect(input) }
            await #expect(throws: CodecError.self) { try await decoder.decode(input) }
            let destination = try ImageDestination.allocate(descriptor: descriptor)
            await #expect(throws: CodecError.self) { try await decoder.decode(input, into: destination) }
            let recovered = try await decoder.decode(original, into: destination)
            #expect(try recovered.image.sampleUInt16(x: 0, y: 0) == 255)
        }
        let filled = Data(repeating: 255, count: 4097) + original
        let exact = DecodeOptions(resourceLimits: try ResourceLimits(maximumCompressedBytes: filled.count))
        let short = DecodeOptions(resourceLimits: try ResourceLimits(maximumCompressedBytes: filled.count - 1))
        #expect(try decoder.inspect(filled, options: exact).descriptor == descriptor)
        #expect(throws: CodecError(.resourceLimitExceeded, "Compressed input exceeds operation limits.")) {
            try decoder.inspect(filled, options: short)
        }
        let destination = try ImageDestination.allocate(descriptor: descriptor)
        await #expect(throws: CodecError.self) { try await decoder.decode(filled, into: destination, options: short) }
        let recovered = try await decoder.decode(filled, into: destination, options: exact)
        #expect(try recovered.image.sampleUInt16(x: 0, y: 0) == 255)
    }

    @Test func synchronousInspectionRejectsProgressBeforeParsing() async throws {
        let original = try fixture()
        let updates = Mutex<[ProgressUpdate]>([])
        let options = DecodeOptions(progress: { update in updates.withLock { $0.append(update) } })
        let decoder = try Decoder()
        for input in [original, Data()] {
            #expect(throws: CodecError(.unsupportedFeature, "Synchronous inspection does not support progress callbacks.")) {
                try decoder.inspect(input, options: options)
            }
        }
        #expect(updates.withLock { $0.isEmpty })
        #expect(try decoder.inspect(original).descriptor.width == 1)
        // The same options still deliver the existing ordered async callbacks.
        let decoded = try await decoder.decode(original, options: options)
        #expect(try decoded.image.sampleUInt16(x: 0, y: 0) == 255)
        let observed = updates.withLock { $0 }
        #expect(observed.map(\.phase) == [.processing, .completed])
        #expect(observed.map(\.completedUnits) == [0, 1])
        #expect(observed.allSatisfy { $0.totalUnits == 1 })
    }
}
