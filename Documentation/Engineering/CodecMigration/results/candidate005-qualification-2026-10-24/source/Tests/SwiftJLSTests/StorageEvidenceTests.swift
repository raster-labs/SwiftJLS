// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

/// Small aggregate expectations keep intentional mutation reports countable.
/// Full independent fixture coverage remains in the scalar/component suites.
@Suite("Load-bearing shared layout expectations")
struct StorageEvidenceTests {
    @Test func scalarEncoderRespectsStrideAndOrder() async throws {
        let packed = try ImageDescriptor.greyscale16(width: 17, height: 13)
        let plane = try PlaneDescriptor(width: 17, height: 13, offset: 4, rowBytes: 42, byteCount: 550)
        let padded = try ImageDescriptor(width: 17, height: 13, byteOrder: .bigEndian, planes: [plane])
        let fixtures = ComponentCodecTests()
        let samples = try fixtures.fixture("p16-17x13-noise", ext: "u16le")
        let expected = try fixtures.fixture("storage-golden-scalar", ext: "jls")
        func source(_ d: ImageDescriptor) throws -> Image {
            try ImageDestination.allocate(descriptor: d).writeUInt16 { x, y in
                let at = (y * 17 + x) * 2
                return UInt16(samples[at]) | UInt16(samples[at + 1]) << 8
            }
        }
        let baseline = try await Encoder().encode(source(packed))
        let actual = try await Encoder().encode(source(padded))
        #expect(actual.data == baseline.data)
        #expect(actual.data == expected)
    }
    @Test func scalarDecoderRespectsStrideAndOrder() async throws {
        let fixtures = ComponentCodecTests()
        let input = try fixtures.fixture("p16-17x13-noise", ext: "jls")
        let expected = try fixtures.fixture("p16-17x13-noise", ext: "u16le")
        let plane = try PlaneDescriptor(width: 17, height: 13, offset: 4, rowBytes: 42, byteCount: 550)
        let shape = try ImageDescriptor(width: 17, height: 13, byteOrder: .bigEndian, planes: [plane])
        let result = try await Decoder().decode(input, into: .allocate(descriptor: shape))
        var mismatches = 0
        for y in 0..<13 { for x in 0..<17 {
            let at = (y * 17 + x) * 2
            let reference = UInt16(expected[at]) | UInt16(expected[at + 1]) << 8
            if try result.image.sampleUInt16(x: x, y: y) != reference { mismatches += 1 }
        } }
        #expect(mismatches == 0)
    }
    @Test func componentEncoderRespectsStrideAndOrder() async throws {
        let helper = ComponentCodecTests()
        let f = ComponentCodecTests.Fixture(name: "c3-i2-p16-n0-17x13-noise", width: 17, height: 13,
            meaningfulBits: 16, near: 0, components: 3, interleave: 2, rgb: true)
        let samples = try helper.fixture(f.name, ext: "u16le")
        func source(planar: Bool, order: ByteOrder) throws -> Image {
            let d = try helper.descriptor(f, planar: planar, storageBits: 16, order: order)
            return try ImageDestination.allocate(descriptor: d).write { bytes in
                bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
                for c in 0..<3 { for y in 0..<13 { for x in 0..<17 {
                    let input = (c * 221 + y * 17 + x) * 2
                    let at = try helper.offset(d, component: c, x: x, y: y)
                    bytes[at] = samples[input + (order == .littleEndian ? 0 : 1)]
                    bytes[at + 1] = samples[input + (order == .littleEndian ? 1 : 0)]
                } } }
            }
        }
        let encoder = try Encoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, interleaveMode: .sample)))
        let baseline = try await encoder.encode(source(planar: true, order: .littleEndian))
        let actual = try await encoder.encode(source(planar: false, order: .bigEndian))
        #expect(actual.data == baseline.data)
        #expect(actual.data == (try helper.fixture("storage-golden-components", ext: "jls")))
    }
    @Test func componentDecoderRespectsStrideAndOrder() async throws {
        let helper = ComponentCodecTests()
        let f = ComponentCodecTests.Fixture(name: "c3-i2-p16-n0-17x13-noise", width: 17, height: 13,
            meaningfulBits: 16, near: 0, components: 3, interleave: 2, rgb: true)
        let input = try helper.fixture(f.name, ext: "jls")
        let expected = try helper.fixture(f.name, ext: "decoded.u16le")
        let d = try helper.descriptor(f, planar: false, storageBits: 16, order: .bigEndian)
        let image = try await Decoder().decode(input, into: .allocate(descriptor: d)).image
        let mismatches = try image.storage.withUnsafeBytes { bytes in
            var count = 0
            for c in 0..<3 { for y in 0..<13 { for x in 0..<17 {
                let raw = (c * 221 + y * 17 + x) * 2
                let at = try helper.offset(d, component: c, x: x, y: y)
                if bytes[at] != expected[raw + 1] || bytes[at + 1] != expected[raw] { count += 1 }
            } } }
            return count
        }
        #expect(mismatches == 0)
    }
}
