// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("HP RGB transform boundaries")
struct HPTransformTests {
    @Test func modularBoundaryPixelsAreReversible() {
        for bits in [8, 16] {
            let maximum = (1 << bits) - 1
            for transform: CodecOptions.ColourTransform in [.hp1, .hp2, .hp3] {
                for r in [0, 1, maximum / 2, maximum] {
                    for g in [0, 1, maximum / 2, maximum] {
                        for b in [0, 1, maximum / 2, maximum] {
                            let encoded = HPTransform.forward(r, g, b, transform: transform, bits: bits)
                            let rgb = HPTransform.inverse(encoded.0, encoded.1, encoded.2, transform: transform, bits: bits)
                            #expect(rgb.0 == r && rgb.1 == g && rgb.2 == b)
                        }
                    }
                }
            }
        }
    }
    @Test func incompatibleEncoderRequestsAreRejected() async throws {
        for transform: CodecOptions.ColourTransform in [.hp1, .hp2, .hp3] {
            let options = try CodecOptions(restartIntervalLines: 0, interleaveMode: .sample, colourTransform: transform)
            #expect(throws: CodecError.self) {
                try EncoderConfiguration(mode: .nearLossless(maximumAbsoluteError: 1), codecOptions: options)
            }
            #expect(throws: CodecError.self) {
                try EncoderConfiguration(codecOptions: .init(restartIntervalLines: 0, colourTransform: transform))
            }
            #expect(throws: CodecError.self) {
                try EncoderConfiguration(codecOptions: .init(restartIntervalLines: 0,
                    preset: .init(maximumSampleValue: 255, threshold1: 3, threshold2: 7, threshold3: 21),
                    interleaveMode: .line, colourTransform: transform))
            }
            let data = try ComponentCodecTests().fixture("c3-i2-p12-n0-17x13-noise", ext: "jls")
            let image = try await Decoder().decode(data).image
            await #expect(throws: CodecError.self) { try await Encoder(configuration: .init(codecOptions: options)).encode(image) }
        }
    }
    @Test func malformedAndIncompatibleSignalsRejectBeforeDestinationWrite() async throws {
        let data = try ComponentCodecTests().fixture("hp1-c3-i2-p8-n0-17x13-noise", ext: "jls")
        let marker = try #require(data.range(of: Data([255, 232, 0, 7, 109, 114, 102, 120, 1])))
        let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        var unknown = data; unknown[marker.upperBound - 1] = 4
        var duplicate = data; duplicate.insert(contentsOf: data[marker], at: marker.lowerBound)
        var late = data; late.insert(contentsOf: data[marker], at: late.count - 2)
        let sos = try #require(data.range(of: Data([255, 218])))
        var near = data; near[sos.lowerBound + 11] = 1
        for malformed in [unknown, duplicate, late, near, data.prefix(marker.upperBound - 1)] {
            let destination = try ImageDestination.allocate(descriptor: header.descriptor(limits: .default))
            await #expect(throws: CodecError.self) { try await Decoder().decode(malformed, into: destination) }
            // Header rejection leaves the caller's one-shot reservation available.
            _ = try await Decoder().decode(data, into: destination)
        }
        let limits = try ResourceLimits(maximumMetadataBytes: 34)
        #expect(throws: CodecError.self) { try Decoder().inspect(data, options: .init(resourceLimits: limits)) }
    }
    @Test func transformOnlyHeaderStillDeclaresRGB() async throws {
        let data = try ComponentCodecTests().fixture("hp3-c3-i1-p16-n0-1x19-edge", ext: "jls")
        // Remove the fixed SPIFF header and its empty directory, retaining SOI.
        let withoutSPIFF = data.prefix(2) + data.dropFirst(46)
        let decoded = try await Decoder().decode(withoutSPIFF)
        #expect(decoded.image.descriptor.colour == .rgb)
        try ComponentCodecTests().check(decoded.image,
            against: ComponentCodecTests().fixture("hp3-c3-i1-p16-n0-1x19-edge", ext: "u16le"), maximumError: 0, padding: false)
    }
    @Test func explicitLegacyMigrationPreservesSamplesAndLayout() async throws {
        let helpers = ComponentCodecTests()
        let manifest = try JSONDecoder().decode(ComponentCodecTests.Manifest.self,
            from: helpers.fixture("components-legacy-hp", ext: "json"))
        let options = try CodecOptions(restartIntervalLines: 0, hpInterpretation: .legacyJLSwift)
        #expect(throws: CodecError.self) { try EncoderConfiguration(codecOptions: options) }
        let decoder = try Decoder(configuration: .init(codecOptions: options))
        for f in manifest.cases {
            let original = try helpers.fixture(f.name, ext: "u16le")
            let data = try helpers.fixture(f.name, ext: "jls")
            for planar in [false, true] {
                for order: ByteOrder in [.littleEndian, .bigEndian] {
                    let descriptor = try helpers.descriptor(f, planar: planar, storageBits: 16, order: order)
                    let destination = try ImageDestination.allocate(descriptor: descriptor)
                    let image = try await decoder.decode(data, into: destination).image
                    #expect(image.storage.allocationID == destination.storage.allocationID)
                    try helpers.check(image, against: original, maximumError: 0, padding: false)
                    let transform = try #require(CodecOptions.ColourTransform(rawValue: UInt8(f.transform ?? 0)))
                    let migrated = try await Encoder(configuration: .init(codecOptions:
                        .init(restartIntervalLines: 0, interleaveMode: .sample, colourTransform: transform))).encode(image)
                    let decoded = try await Decoder().decode(migrated.data).image
                    try helpers.check(decoded, against: original, maximumError: 0, padding: false)
                }
            }
        }
    }

}
