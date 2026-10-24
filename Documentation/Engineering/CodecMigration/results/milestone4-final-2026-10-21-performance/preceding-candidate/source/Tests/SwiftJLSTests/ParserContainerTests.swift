// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Bounded frame and scan bookkeeping")
struct ParserContainerTests {
    private let helper = ComponentCodecTests()

    private func rejected(_ data: Data, as expected: CodecError,
                          destinationFor valid: Data) async throws {
        let decoder = try Decoder()
        do {
            _ = try decoder.inspect(data)
            Issue.record("Invalid framing was accepted by inspect.")
        } catch let error as CodecError {
            #expect(error == expected)
        }
        let destination = try ImageDestination.allocate(descriptor: decoder.inspect(valid).descriptor)
        do {
            _ = try await decoder.decode(data, into: destination)
            Issue.record("Invalid framing was accepted by decode.")
        } catch let error as CodecError {
            #expect(error == expected)
        }
        // Header admission must reject before consuming the caller's write lease.
        _ = try destination.write { $0.initializeMemory(as: UInt8.self, repeating: 0) }
    }

    @Test func separateScansCoverEveryComponentExactlyOnceInAnyOrder() async throws {
        // Four independent CharLS scans exercise the highest admitted component
        // index as well as repeated/missing coverage across scan boundaries.
        let name = "c4-i0-p12-n0-17x13-noise"
        let original = try helper.fixture(name, ext: "jls")
        let expected = try helper.fixture(name, ext: "decoded.u16le")
        let header = try JPEGLSHeader.parse(original, budget: .init(limits: .default))
        #expect(header.records.count == 4)
        var scans: [Data] = []
        var firstStart: Int?
        for record in header.records {
            let first = try #require(record.ranges.first)
            let last = try #require(record.ranges.last)
            let start = first.lowerBound - (8 + 2 * record.components.count)
            #expect(original[start] == 255 && original[start + 1] == 218)
            if firstStart == nil { firstStart = start }
            scans.append(Data(original[start..<last.upperBound]))
        }
        let prefix = Data(original.prefix(try #require(firstStart)))
        func stream(_ order: [Int]) -> Data {
            var data = prefix
            for index in order { data.append(scans[index]) }
            data.append(contentsOf: [255, 217])
            return data
        }
        let reversed = stream([3, 2, 1, 0])
        let image = try await Decoder().decode(reversed).image
        try helper.check(image, against: expected, maximumError: 0, padding: false)

        let malformed = CodecError(.malformedInput, "Invalid or truncated JPEG-LS header.")
        var unknown = original
        // The selector is a component ID, not the bounded frame-array index.
        let selector = try #require(firstStart) + 5
        #expect(!header.componentIDs.contains(255))
        unknown[selector] = 255
        for invalid in [stream([0, 1, 2]), stream([0, 0, 1, 2, 3]), unknown] {
            try await rejected(invalid, as: malformed, destinationFor: original)
        }
        // Duplicate selectors within one scan already have a public rejection
        // regression in ComponentCodecTests.componentLimitsCancellationAndMalformedScans.
    }

    @Test func samplingEqualityKeepsInactiveRestartAndUnsupportedCombinationRules() async throws {
        let mixed = try helper.fixture("subsampled-zero-n0", ext: "jls")
        let header = try JPEGLSHeader.parse(mixed, budget: .init(limits: .default))
        let record = try #require(header.records.first)
        let first = try #require(record.ranges.first)
        let sos = first.lowerBound - (8 + 2 * record.components.count)
        let interleaveOffset = sos + 6 + 2 * record.components.count

        // DRI at or past the height is inactive, even for mixed sampling.
        let inactive = helper.withDRI(mixed, interval: UInt32(header.height))
        let decoded = try await Decoder().decode(inactive).image
        #expect(try decoded.storage.withUnsafeBytes { $0.allSatisfy { $0 == 0 } })

        var sampleInterleave = mixed
        sampleInterleave[interleaveOffset] = 2
        var hp = Data([255, 216, 255, 232, 0, 7, 109, 114, 102, 120, 1])
        hp.append(mixed.dropFirst(2))
        let unsupported = CodecError(.unsupportedFeature,
            "Subsampled decoding requires one line-interleaved scan without HP or restarts.")
        for invalid in [sampleInterleave, helper.withDRI(mixed, interval: 1), hp] {
            try await rejected(invalid, as: unsupported, destinationFor: mixed)
        }

        // Equal non-unit sampling factors remain a full-resolution sample scan;
        // the predicate must test equality, rather than assuming every byte is 0x11.
        let uniformName = "c3-i2-p12-n0-17x13-noise"
        var uniform = try helper.fixture(uniformName, ext: "jls")
        let sof = try #require(uniform.range(of: Data([255, 247]))).lowerBound
        for component in 0..<3 { uniform[sof + 11 + 3 * component] = 0x22 }
        let uniformImage = try await Decoder().decode(uniform).image
        try helper.check(uniformImage,
            against: helper.fixture(uniformName, ext: "decoded.u16le"), maximumError: 0, padding: false)
    }
}
