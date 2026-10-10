// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

final class ComponentSentinelStorage: WritableImageStorage {
    let owner: OwnedImageStorage
    init(count: Int) throws { owner = try .init(byteCount: count) }
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    func reserveWrite() throws -> StorageWriteLease { try owner.reserveWrite() }
    func withUnsafeMutableBytes<R>(lease: StorageWriteLease, _ body: (UnsafeMutableRawBufferPointer) throws -> R) throws -> R {
        try owner.withUnsafeMutableBytes(lease: lease) { bytes in
            bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
            return try body(bytes)
        }
    }
    func finishAndSeal(lease: StorageWriteLease) throws -> any ReadOnlyImageStorage { try owner.finishAndSeal(lease: lease) }
    func abortAndInvalidate(lease: StorageWriteLease) throws { try owner.abortAndInvalidate(lease: lease) }
}

@Suite("Independent component JPEG-LS")
struct ComponentCodecTests {
    struct Fixture: Decodable {
        let name: String, width: Int, height: Int, meaningfulBits: Int, near: Int, components: Int, interleave: Int
        let rgb: Bool
        var transform: Int? = nil
    }
    struct Manifest: Decodable { let cases: [Fixture] }
    func fixture(_ name: String, ext: String) throws -> Data {
        let directory = try #require(Bundle.module.resourceURL).appendingPathComponent("Fixtures")
        return try Data(contentsOf: directory.appendingPathComponent(name + "." + ext))
    }
    func descriptor(_ f: Fixture, planar: Bool, storageBits: Int, order: ByteOrder, extra: Int = 0) throws -> ImageDescriptor {
        let sampleBytes = storageBits / 8
        let roles: [ComponentRole] = f.rgb ? [.red, .green, .blue] : (1...f.components).map { .uninterpreted("JPEG-LS:\($0)") }
        let planes: [PlaneDescriptor]
        if planar {
            let row = (f.width + 5 + extra) * sampleBytes
            let capacity = row * f.height + 8 * sampleBytes
            planes = try (0..<f.components).map { c in
                try PlaneDescriptor(width: f.width, height: f.height, components: [c], offset: c * capacity + 2 * sampleBytes,
                    sampleStride: sampleBytes, pixelStride: sampleBytes, rowBytes: row, byteCount: (c + 1) * capacity)
            }
        } else {
            let pixel = (f.components + 1) * sampleBytes
            let row = f.width * pixel + (5 + extra) * sampleBytes
            planes = [try PlaneDescriptor(width: f.width, height: f.height, components: Array((0..<f.components).reversed()),
                offset: 4 * sampleBytes, sampleStride: sampleBytes, pixelStride: pixel, rowBytes: row,
                byteCount: row * f.height + 8 * sampleBytes)]
        }
        return try ImageDescriptor(width: f.width, height: f.height, storageBits: storageBits,
            meaningfulBits: f.meaningfulBits, byteOrder: order, components: roles,
            colour: f.rgb ? .rgb : .unknown, planes: planes)
    }
    func offset(_ d: ImageDescriptor, component: Int, x: Int, y: Int) throws -> Int {
        for plane in d.planes {
            if let slot = plane.components.firstIndex(of: component) {
                return plane.offset + slot * plane.sampleStride + y * plane.rowBytes + x * plane.pixelStride
            }
        }
        throw CodecError(.internalFailure, "Missing test component")
    }
    func check(_ image: Image, against reference: Data, maximumError: Int, padding: Bool) throws {
        let d = image.descriptor
        try image.storage.withUnsafeBytes { bytes in
            var used = Set<Int>()
            for c in d.components.indices { for y in 0..<d.height { for x in 0..<d.width {
                let at = try offset(d, component: c, x: x, y: y)
                let raw = (c * d.width * d.height + y * d.width + x) * 2
                let expected = Int(reference[raw]) | Int(reference[raw + 1]) << 8
                let actual: Int
                if d.storageBits == 8 { actual = Int(bytes[at]); used.insert(at) }
                else {
                    actual = d.byteOrder == .littleEndian ? Int(bytes[at]) | Int(bytes[at + 1]) << 8 : Int(bytes[at]) << 8 | Int(bytes[at + 1])
                    used.formUnion([at, at + 1])
                }
                #expect(abs(actual - expected) <= maximumError)
            } } }
            if padding { for i in bytes.indices where !used.contains(i) { #expect(bytes[i] == 0xa5) } }
        }
    }
    @Test func independentPlanarAndPixelLayouts() async throws {
        let manifest = try JSONDecoder().decode(Manifest.self, from: fixture("components", ext: "json"))
        let published = try JSONDecoder().decode(Manifest.self, from: fixture("components-reference", ext: "json"))
        let hp = try JSONDecoder().decode(Manifest.self, from: fixture("components-hp", ext: "json"))
        for f in manifest.cases + published.cases + hp.cases {
            var baseline: Data?
            let original = try fixture(f.name, ext: "u16le")
            let expected = try fixture(f.name, ext: "decoded.u16le")
            let input = try fixture(f.name, ext: "jls")
            let info = try Decoder().inspect(input)
            #expect(info.descriptor.meaningfulBits == f.meaningfulBits)
            #expect(info.descriptor.colour == (f.rgb ? .rgb : .unknown))
            for planar in [true, false] {
                for order: ByteOrder in [.littleEndian, .bigEndian] {
                    let storageBits = f.meaningfulBits <= 8 && planar ? 8 : 16
                    let d = try descriptor(f, planar: planar, storageBits: storageBits, order: order)
                    let provider = try ComponentSentinelStorage(count: d.requiredByteCount)
                    let destination = try ImageDestination(descriptor: d, storage: provider)
                    let decoded = try await Decoder().decode(input, into: destination)
                    #expect(decoded.image.storage.allocationID == provider.allocationID)
                    #expect(decoded.report.copyEvents.isEmpty && decoded.report.pixelAllocationCount == 0)
                    try check(decoded.image, against: expected, maximumError: 0, padding: true)
                    let source = try ImageDestination.allocate(descriptor: d).write { bytes in
                        bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
                        for c in 0..<f.components { for y in 0..<f.height { for x in 0..<f.width {
                            let at = try offset(d, component: c, x: x, y: y)
                            let raw = (c * f.width * f.height + y * f.width + x) * 2
                            if storageBits == 8 { bytes[at] = original[raw] }
                            else {
                                bytes[at] = original[raw + (order == .littleEndian ? 0 : 1)]
                                bytes[at + 1] = original[raw + (order == .littleEndian ? 1 : 0)]
                            }
                        } } }
                    }
                    let interleave = try #require(CodecOptions.InterleaveMode(rawValue: UInt8(f.interleave)))
                    let encoded = try await Encoder(configuration: .init(mode: f.near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: f.near),
                        codecOptions: .init(restartIntervalLines: 0, interleaveMode: interleave,
                            colourTransform: try #require(CodecOptions.ColourTransform(rawValue: UInt8(f.transform ?? 0)))))).encode(source)
                    if let transform = f.transform {
                        let marker = Data([255, 232, 0, 7, 109, 114, 102, 120, UInt8(transform)])
                        #expect(encoded.data.range(of: marker) != nil)
                    }
                    if let baseline { #expect(encoded.data == baseline) } else { baseline = encoded.data }
                    #expect(encoded.report.copyEvents.isEmpty && encoded.report.pixelAllocationCount == 0)
                    let target = try descriptor(f, planar: !planar, storageBits: 16, order: order, extra: 7)
                    let roundtrip = try await Decoder().decode(encoded.data, into: .allocate(descriptor: target))
                    try check(roundtrip.image, against: original, maximumError: f.near, padding: false)
                }
            }
        }
    }
    @Test func truncatedComponentDirectoryAndMismatchedSPIFFAreRejected() async throws {
        let data = try fixture("c3-i0-p8-n0-17x13-noise", ext: "jls")
        let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        let truncated = data.prefix(header.records[0].ranges[0].upperBound) + Data([255, 217])
        await #expect(throws: CodecError.self) { try await Decoder().decode(truncated) }
        var bad = data
        let start = try #require(bad.range(of: Data([83, 80, 73, 70, 70, 0]))).lowerBound
        bad[start + 14] = 255
        await #expect(throws: CodecError.self) { try await Decoder().decode(bad) }
    }
    // CharLS 2.4.2 cannot decode this profile: these are local invariants,
    // deliberately separate from independent conformance evidence. Published
    // reference fixtures independently cover the line mode with explicit presets.
    @Test func twoComponentInterleaveLocalInvariants() async throws {
        let data = try fixture("c2-i0-p12-n0-17x13-noise", ext: "jls")
        let original = try fixture("c2-i0-p12-n0-17x13-noise", ext: "u16le")
        let image = try await Decoder().decode(data).image
        for mode: CodecOptions.InterleaveMode in [.line, .sample] {
            for near in [0, 3, 255] {
                let encoded = try await Encoder(configuration: .init(
                    mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
                    codecOptions: .init(restartIntervalLines: 0, interleaveMode: mode))).encode(image)
                let result = try await Decoder().decode(encoded.data)
                try check(result.image, against: original, maximumError: near, padding: false)
            }
        }
    }
    @Test func componentLimitsCancellationAndMalformedScans() async throws {
        let data = try fixture("c3-i2-p12-n0-17x13-noise", ext: "jls")
        let image = try await Decoder().decode(data).image
        let configuration = try EncoderConfiguration(codecOptions: .init(restartIntervalLines: 0, interleaveMode: .sample))
        let callback: @Sendable (ProgressUpdate) -> Void = { update in
            if update.phase == .completed { withUnsafeCurrentTask { $0?.cancel() } }
        }
        let decode = Task { try await Decoder().decode(data, options: .init(progress: callback)) }
        await #expect(throws: CancellationError.self) { try await decode.value }
        let encode = Task { try await Encoder(configuration: configuration).encode(image, options: .init(progress: callback)) }
        await #expect(throws: CancellationError.self) { try await encode.value }
        let limits = try ResourceLimits(maximumWorkspaceBytes: 1)
        await #expect(throws: CodecError.self) { try await Encoder(configuration: configuration).encode(image, options: .init(resourceLimits: limits)) }
        await #expect(throws: CodecError.self) { try await Decoder().decode(data, options: .init(resourceLimits: limits)) }
        #expect(throws: CodecError.self) { try EncoderConfiguration(codecOptions: .init(restartIntervalLines: 3, interleaveMode: .line)) }
        var duplicate = data
        let scan = try #require(duplicate.range(of: Data([255, 218]))).lowerBound
        duplicate[scan + 7] = duplicate[scan + 5]
        await #expect(throws: CodecError.self) { try await Decoder().decode(duplicate) }
        let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        let entropy = header.records[0].ranges[0]
        let corrupt = data.prefix(entropy.lowerBound) + Data([0]) + data.suffix(from: entropy.upperBound)
        let destination = try ImageDestination.allocate(descriptor: image.descriptor)
        await #expect(throws: CodecError.self) { try await Decoder().decode(corrupt, into: destination) }
        #expect(throws: CodecError.self) { try destination.storage.reserveWrite() }
    }


}
