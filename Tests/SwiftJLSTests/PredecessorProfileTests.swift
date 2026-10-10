// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Remaining predecessor profiles")
struct PredecessorProfileTests {
    let helper = ComponentCodecTests()
    @Test func legacyPrecisionAndScanSchedules() async throws {
        let manifest = try JSONDecoder().decode(ComponentCodecTests.Manifest.self, from: helper.fixture("legacy-profiles", ext: "json"))
        let decoder = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, hpInterpretation: .legacyJLSwift)))
        for f in manifest.cases {
            let image = try await decoder.decode(helper.fixture(f.name, ext: "jls")).image
            try helper.check(image, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
            let migrated = try await Encoder().encode(image)
            try helper.check(try await Decoder().decode(migrated.data).image, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
        }
    }
    @Test func independentlyEncodedExtendedDimensions() async throws {
        let manifest = try JSONDecoder().decode(ComponentCodecTests.Manifest.self, from: helper.fixture("extended", ext: "json"))
        for f in manifest.cases {
            let data = try helper.fixture(f.name, ext: "jls")
            let image = try await Decoder().decode(data).image
            #expect(image.descriptor.width == f.width && image.descriptor.height == f.height)
            try helper.check(image, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
            let encoded = try await Encoder().encode(image)
            try helper.check(try await Decoder().decode(encoded.data).image, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
            let limited = try ResourceLimits(maximumDimension: 65535)
            #expect(throws: CodecError.self) { try Decoder().inspect(data, options: .init(resourceLimits: limited)) }
        }
    }
    @Test func subsampledRowsRemainInTheirOwnPlanes() async throws {
        for near in [0,3] {
            let data = try helper.fixture("subsampled-zero-n\(near)", ext: "jls")
            let info = try Decoder().inspect(data)
            #expect(info.descriptor.planes.map(\.width) == [17,17,9])
            #expect(info.descriptor.planes.map(\.height) == [19,5,10])
            let planes = try info.descriptor.planes.enumerated().map { index, p in
                try PlaneDescriptor(width: p.width, height: p.height, components: [index], offset: index * 2048 + 2,
                    rowBytes: p.width * 2 + 6, byteCount: (index + 1) * 2048,
                    horizontalSamplingFactor: p.horizontalSamplingFactor, verticalSamplingFactor: p.verticalSamplingFactor)
            }
            let d = try ImageDescriptor(width: 17, height: 19, meaningfulBits: 8, byteOrder: .bigEndian,
                components: info.descriptor.components, colour: .unknown, planes: planes)
            let destination = try ImageDestination.allocate(descriptor: d)
            let decoded = try await Decoder().decode(data, into: destination)
            #expect(decoded.image.storage.allocationID == destination.storage.allocationID)
            try decoded.image.storage.withUnsafeBytes { bytes in
                for p in planes { for y in 0..<p.height { for x in 0..<p.width {
                    let at = p.offset + y * p.rowBytes + x * 2
                    #expect(bytes[at] == 0 && bytes[at+1] == 0)
                } } }
            }
            await #expect(throws: CodecError.self) { try await Encoder().encode(decoded.image) }
        }
    }
    @Test func actualLegacyDimensionsAndContinuations() async throws {
        let decoder = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0,
            mappingOutputPrecision: 16, legacyMappingContinuations: true, legacyExtendedDimensions: true)))
        for (width, height) in [(65537, 1), (1, 65537)] {
            let data = try helper.fixture("legacy-extended-\(width)x\(height)", ext: "jls")
            let image = try await decoder.decode(data).image
            #expect(image.descriptor.width == width && image.descriptor.height == height)
            for y in 0..<height { for x in 0..<width {
                #expect(try image.sampleUInt16(x: x, y: y) == UInt16((x * 17 + y * 3) & 255))
            } }
        }
        for width in [1, 2] {
            let data = try helper.fixture("legacy-mapping-w\(width)", ext: "jls")
            let image = try await decoder.decode(data).image
            for (x, value) in [0, 1, 32764, 32765, 65535].enumerated() {
                #expect(try image.sampleUInt16(x: x, y: 0) == UInt16((value * 271) & (width == 1 ? 255 : 65535)))
            }
        }
    }

    @Test func predecessorCombinedMappingAndHPOrder() async throws {
        let manifest = try JSONDecoder().decode(ComponentCodecTests.Manifest.self, from: helper.fixture("legacy-combined", ext: "json"))
        let decoder = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, hpInterpretation: .legacyJLSwift)))
        for f in manifest.cases {
            let data = try helper.fixture(f.name, ext: "jls")
            let decoded = try await decoder.decode(data)
            try helper.check(decoded.image, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
            #expect(decoded.image.metadata.entries[JPEGLSMappingTables.key] == nil)
            #expect(decoded.report.fidelity == (f.near == 0 ? .exactSamples : .boundedError((1 << f.meaningfulBits) - 1)))
            let encoded = try await Encoder().encode(decoded.image)
            try helper.check(try await Decoder().decode(encoded.data).image, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
        }
    }

    @Test func smallPlanesCannotHideDifferentSamplingRatios() async throws {
        var data = try helper.fixture("subsampled-zero-n0", ext: "jls")
        data[7] = 0; data[8] = 1; data[9] = 0; data[10] = 1
        let parsed = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        data = data.prefix(parsed.records[0].ranges[0].lowerBound) + Data([0xe0, 255, 217])
        let info = try Decoder().inspect(data)
        _ = try await Decoder().decode(data)
        let planes = try (0..<3).map { i in
            try PlaneDescriptor(width: 1, height: 1, components: [i], offset: i * 2, rowBytes: 2, byteCount: (i + 1) * 2)
        }
        let wrong = try ImageDescriptor(width: 1, height: 1, meaningfulBits: 8,
            components: info.descriptor.components, colour: .unknown, planes: planes)
        let destination = try ImageDestination.allocate(descriptor: wrong)
        await #expect(throws: CodecError.self) { try await Decoder().decode(data, into: destination) }
        _ = try destination.write { $0.initializeMemory(as: UInt8.self, repeating: 0) }
    }

}
