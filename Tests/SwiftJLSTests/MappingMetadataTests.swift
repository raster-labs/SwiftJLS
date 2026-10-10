// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Mapping tables and metadata")
struct MappingMetadataTests {
    let helper = ComponentCodecTests()
    @Test func independentMappingTablesPreserveIndicesAndMapExplicitly() async throws {
        let manifest = try JSONDecoder().decode(ComponentCodecTests.Manifest.self, from: helper.fixture("mapping", ext: "json"))
        for f in manifest.cases {
            let data = try helper.fixture(f.name, ext: "jls")
            let indices = try await Decoder().decode(data).image
            let tables = try JPEGLSMappingTables(metadata: indices.metadata)
            #expect(tables.tables.count == 1)
            #expect(tables.tables[0].data == (try helper.fixture(f.name, ext: "table")))
            #expect(tables.componentTableIDs == Array(repeating: 7, count: f.components))
            try helper.check(indices, against: helper.fixture(f.name, ext: "u16le"), maximumError: 0, padding: false)
            let discarded = try await Decoder().decode(data, options: .init(metadataPolicy: .discardAncillary)).image
            #expect(discarded.metadata == tables.metadata)
            let mode = try #require(CodecOptions.InterleaveMode(rawValue: UInt8(f.interleave)))
            let reencoded = try await Encoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, interleaveMode: mode))).encode(indices)
            #expect(try Decoder().inspect(reencoded.data).metadata == indices.metadata)
            if tables.tables[0].entryWidth > 2 {
                await #expect(throws: CodecError.self) {
                    try await Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, mappingOutputPrecision: 16))).decode(data)
                }
                continue
            }
            let decoder = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, mappingOutputPrecision: 16)))
            let info = try decoder.inspect(data)
            #expect(info.descriptor.meaningfulBits == 16)
            for order: ByteOrder in [.littleEndian, .bigEndian] {
                let descriptor: ImageDescriptor
                if f.components == 1 {
                    let row = f.width * 2 + 6
                    descriptor = try ImageDescriptor(width: f.width, height: f.height, meaningfulBits: 16, byteOrder: order,
                        planes: [.init(width: f.width, height: f.height, rowBytes: row, byteCount: row * f.height)])
                } else {
                    let layout = ComponentCodecTests.Fixture(name: f.name, width: f.width, height: f.height, meaningfulBits: 16, near: f.near, components: f.components, interleave: f.interleave, rgb: false)
                    descriptor = try helper.descriptor(layout, planar: false, storageBits: 16, order: order)
                }
                let destination = try ImageDestination.allocate(descriptor: descriptor)
                let mapped = try await decoder.decode(data, into: destination)
                #expect(mapped.image.storage.allocationID == destination.storage.allocationID)
                #expect(mapped.image.metadata.entries[JPEGLSMappingTables.key] == nil)
                try helper.check(mapped.image, against: helper.fixture(f.name, ext: "mapped.u16le"), maximumError: 0, padding: false)
                if f.near > 0 { #expect(mapped.report.fidelity != .boundedError(f.near)) }
            }
        }
    }
    @Test func orderedOpaqueSegmentsAndPolicies() async throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 3, height: 2, meaningfulBits: 8)
        let pixels = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { x, y in UInt16(x+y) }
        let ancillary = JPEGLSMetadata(segments: try [
            .init(marker: 0xfe, payload: Data([0, 255, 216, 128])),
            .init(marker: 0xe2, payload: Data("opaque ICC-like bytes".utf8)),
            .init(marker: 0xfe, payload: Data()), .init(marker: 0xe8, payload: Data([1,2]))])
        let image = try Image(descriptor: descriptor, storage: pixels.storage, metadata: ancillary.metadata)
        let encoded = try await Encoder().encode(image)
        #expect(try Decoder().inspect(encoded.data).metadata == image.metadata)
        #expect(try await Decoder().decode(encoded.data).image.metadata == image.metadata)
        #expect(try await Decoder().decode(encoded.data, options: .init(metadataPolicy: .discardAncillary)).image.metadata == .empty)
        let discarded = try await Encoder().encode(image, options: .init(metadataPolicy: .discardAncillary))
        #expect(try Decoder().inspect(discarded.data).metadata == .empty)
        let required = try Image(descriptor: descriptor, storage: pixels.storage,
            metadata: .init(entries: image.metadata.entries, requiredKeys: [JPEGLSMetadata.key]))
        let preserved = try await Encoder().encode(required, options: .init(metadataPolicy: .discardAncillary))
        #expect(try Decoder().inspect(preserved.data).metadata.entries == image.metadata.entries)
        #expect(throws: CodecError.self) { try Decoder().inspect(encoded.data, options: .init(resourceLimits: .init(maximumMetadataBytes: 3))) }
        let unknown = try Image(descriptor: descriptor, storage: pixels.storage, metadata: .init(entries: ["unknown": Data([1])], requiredKeys: ["unknown"]))
        await #expect(throws: CodecError.self) { try await Encoder().encode(unknown, options: .init(metadataPolicy: .discardAncillary)) }
    }
    @Test func spiffDensityAndDirectoryRoundTrip() async throws {
        var data = try helper.fixture("c3-i0-p8-n0-17x13-noise", ext: "jls")
        data[27] = 1; data[31] = 72; data[35] = 96 // unit, vertical, horizontal resolution (outer SOI adds two)
        let directory = Data([255,232,0,11,0,0,0,2,0,255,216,7,8])
        data.insert(contentsOf: directory, at: 36)
        let image = try await Decoder().decode(data).image
        let spiff = try #require(image.metadata.entries[JPEGLSMetadata.spiffKey])
        #expect(spiff.range(of: directory) != nil)
        let encoded = try await Encoder().encode(image)
        #expect(try Decoder().inspect(encoded.data).metadata == image.metadata)
        let discard = try await Encoder().encode(image, options: .init(metadataPolicy: .discardAncillary))
        #expect(try Decoder().inspect(discard.data).metadata.entries[JPEGLSMetadata.spiffKey]?.range(of: directory) == nil)
    }
    @Test func malformedMappingsRejectBeforeWritingAndLegacyIsExplicit() async throws {
        let data = try helper.fixture("map-p16-c1-i0-w2-n0", ext: "jls")
        let marker = try #require(data.range(of: Data([255,248,0,17,3,7,2]))) // second continuation is six remaining entries
        var legacy = data
        // Rewrite every continuation to the pinned predecessor's omitted-Wt syntax.
        var i = 2
        while i + 4 < legacy.count {
            guard legacy[i] == 255 else { break }
            let length = Int(legacy[i+2]) << 8 | Int(legacy[i+3])
            if legacy[i+1] == 218 { break }
            if legacy[i+1] == 248 && legacy[i+4] == 3 {
                legacy.remove(at: i+6); legacy[i+2] = UInt8((length-1)>>8); legacy[i+3] = UInt8((length-1)&255)
                i += length+1
            } else { i += length+2 }
        }
        #expect(marker.lowerBound > 0)
        await #expect(throws: CodecError.self) { try await Decoder().decode(legacy) }
        let decoder = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, mappingOutputPrecision: 16, legacyMappingContinuations: true)))
        try helper.check(try await decoder.decode(legacy).image, against: helper.fixture("map-p16-c1-i0-w2-n0", ext: "mapped.u16le"), maximumError: 0, padding: false)
        let small = try helper.fixture("map-p2-c1-i0-w2-n0", ext: "jls")
        let sos = try #require(small.range(of: Data([255,218])))
        var missing = small; missing[sos.lowerBound+6] = 99
        var short = small; let table = try #require(short.range(of: Data([255,248,0,13,2,7,2])))
        short.removeSubrange((table.upperBound+6)..<(table.upperBound+8)); short[table.lowerBound+3] = 11
        for bad in [missing, short, data.prefix(marker.upperBound)] {
            let destination = try ImageDestination.allocate(descriptor: Decoder().inspect(small).descriptor)
            await #expect(throws: CodecError.self) { try await Decoder().decode(bad, into: destination) }
            _ = try await Decoder().decode(small, into: destination)
        }
    }
    @Test func uninterpretedSPIFFIsRequiredAndLimitsPrecedePublication() async throws {
        var data = try helper.fixture("c3-i0-p8-n0-17x13-noise", ext: "jls")
        data[24] = 0 // SPIFF colour code: opaque interpretation, not RGB.
        let image = try await Decoder().decode(data).image
        #expect(image.descriptor.colour == .unknown)
        #expect(image.metadata.requiredKeys.contains(JPEGLSMetadata.spiffKey))
        let encoded = try await Encoder().encode(image, options: .init(metadataPolicy: .discardAncillary))
        let inspected = try Decoder().inspect(encoded.data)
        #expect(inspected.metadata == image.metadata)
        let mapping = try helper.fixture("map-p16-c1-i0-w2-n0", ext: "jls")
        let destination = try ImageDestination.allocate(descriptor: Decoder().inspect(mapping).descriptor)
        await #expect(throws: CodecError.self) {
            try await Decoder().decode(mapping, into: destination, options: .init(resourceLimits: .init(maximumMetadataBytes: 64)))
        }
        _ = try await Decoder().decode(mapping, into: destination)
        let precision = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, mappingOutputPrecision: 8)))
        #expect(throws: CodecError.self) { try precision.inspect(mapping) }
    }

    @Test func unsignedWireFieldsStayBoundedOnNativeWordSizes() async throws {
        let original = try helper.fixture("p12-17x13-noise", ext: "jls")
        var largeRestart = original
        largeRestart.insert(contentsOf: [255,221,0,6,255,255,255,255], at: 2)
        let decoded = try await Decoder().decode(largeRestart)
        try helper.check(decoded.image, against: helper.fixture("p12-17x13-noise", ext: "u16le"), maximumError: 0, padding: false)

        var spiff = try helper.fixture("c3-i0-p8-n0-17x13-noise", ext: "jls")
        spiff.replaceSubrange(28..<36, with: Array(repeating: UInt8(255), count: 8))
        let image = try await Decoder().decode(spiff).image
        let encoded = try await Encoder().encode(image)
        #expect(try Decoder().inspect(encoded.data).metadata == image.metadata)

        let tables = try JPEGLSMappingTables(tables: [.init(id: 7, entryWidth: 1, entries: [0,1,2,3])], componentTableIDs: [7])
        var archive = try #require(tables.metadata.entries[JPEGLSMappingTables.key])
        archive[5] = 0x80 // UInt32 byte count cannot be represented by a 32-bit Int.
        #expect(throws: CodecError.self) {
            try JPEGLSMappingTables(metadata: .init(entries: [JPEGLSMappingTables.key: archive]))
        }
        var extended = try helper.fixture("extended-p8-65537x2", ext: "jls")
        let marker = try #require(extended.range(of: Data([255,248,0,12,4,4])))
        extended.replaceSubrange(marker.upperBound..<(marker.upperBound+4), with: [255,255,255,255])
        #expect(throws: CodecError.self) { try Decoder().inspect(extended) }
    }

}
