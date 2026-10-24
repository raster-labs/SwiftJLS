// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Parser workspace admission")
struct WorkspaceAdmissionTests {
    private let exhausted = CodecError(.resourceLimitExceeded,
        "Codec operation exceeds its memory budget.")
    private let malformed = CodecError(.malformedInput,
        "Invalid or truncated JPEG-LS header.")

    private func restarted(height: Int) async throws -> (data: Data, source: Image) {
        let descriptor = try ImageDescriptor.greyscale16(width: 3, height: height, meaningfulBits: 12)
        let source = try ImageDestination.allocate(descriptor: descriptor).write { bytes in
            for row in 0..<height { for column in 0..<3 {
                let sample = (row * 71 + column * 29) & 4095
                let offset = row * 6 + column * 2
                bytes[offset] = UInt8(truncatingIfNeeded: sample)
                bytes[offset + 1] = UInt8(sample >> 8)
            } }
        }
        let encoder = try Encoder(configuration: .init(codecOptions: .init(restartIntervalLines: 1)))
        return (try await encoder.encode(source).data, source)
    }

    @Test func metadataFreeInspectionEnforcesWorkspaceAndTotalBoundaries() async throws {
        let (data, source) = try await restarted(height: 5)
        let decoder = try Decoder()
        // Five final directory entries plus the operation's fixed control
        // allowance. This stream has no ancillary/mapping/SPIFF metadata.
        let admitted = 64 * 1024 + 5 * MemoryLayout<Range<Int>>.stride * 2
        let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        #expect(header.metadataBytes == 0)
        #expect(header.scans.count == 5)
        for limit in [32, admitted - 1] {
            let options = DecodeOptions(resourceLimits: try .init(maximumWorkspaceBytes: limit))
            #expect(throws: exhausted) { try decoder.inspect(data, options: options) }
        }
        for limit in [admitted, admitted + 1] {
            let options = DecodeOptions(resourceLimits: try .init(maximumWorkspaceBytes: limit))
            #expect(try decoder.inspect(data, options: options).descriptor == source.descriptor)
        }

        let total = data.count + source.descriptor.requiredByteCount + admitted
        let belowTotal = DecodeOptions(resourceLimits: try .init(maximumWorkspaceBytes: admitted,
            maximumMemoryBytes: total - 1))
        #expect(throws: exhausted) { try decoder.inspect(data, options: belowTotal) }
        let exactTotal = DecodeOptions(resourceLimits: try .init(maximumWorkspaceBytes: admitted,
            maximumMemoryBytes: total))
        #expect(try decoder.inspect(data, options: exactTotal).descriptor == source.descriptor)
    }

    @Test func metadataChargeRetainsFixedReservationBeforeAllocatingPayload() throws {
        // COM has length4 (including its length word), charged as length+1.
        // No frame follows: at the exact reservation parsing reaches malformed
        // EOF, while one byte less must reject at the metadata admission itself.
        let fragment = Data([255, 216, 255, 254, 0, 4, 65, 66])
        let required = 64 * 1024 + 5 * 32
        let decoder = try Decoder()
        let below = DecodeOptions(resourceLimits: try .init(maximumWorkspaceBytes: required - 1))
        #expect(throws: exhausted) { try decoder.inspect(fragment, options: below) }
        let exact = DecodeOptions(resourceLimits: try .init(maximumWorkspaceBytes: required))
        #expect(throws: malformed) { try decoder.inspect(fragment, options: exact) }
    }

    @Test func restartDirectoriesAroundCapacityBoundariesPreserveSamples() async throws {
        let decoder = try Decoder()
        for height in [3, 4, 5, 7, 8, 9, 15, 16, 17, 31, 32, 33] {
            let (data, source) = try await restarted(height: height)
            let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
            #expect(header.scans.count == height)
            #expect(header.scans.allSatisfy { !$0.isEmpty })
            let decoded = try await decoder.decode(data)
            for row in 0..<height { for column in 0..<3 {
                #expect(try decoded.image.sampleUInt16(x: column, y: row)
                    == source.sampleUInt16(x: column, y: row))
            } }
            #expect(decoded.report.peakWorkspaceBytes == nil)
        }
    }

    @Test func truncatedRestartDirectoryRejectsBeforeTakingDestinationLease() async throws {
        let (original, source) = try await restarted(height: 3)
        var truncated = original
        let sof = try #require(truncated.range(of: Data([255, 247]))).lowerBound
        // Claim65,535 one-row intervals while retaining only three ranges.
        // The default directory budget admits this declared payload; available
        // encoded bytes must reject it before reserveCapacity(expected).
        truncated[sof + 5] = 255
        truncated[sof + 6] = 255
        let decoder = try Decoder()
        #expect(throws: malformed) { try decoder.inspect(truncated) }
        let destination = try ImageDestination.allocate(descriptor: source.descriptor)
        await #expect(throws: malformed) { try await decoder.decode(truncated, into: destination) }
        _ = try destination.write { $0.initializeMemory(as: UInt8.self, repeating: 0) }
    }
}
