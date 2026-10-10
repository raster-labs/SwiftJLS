// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization
import Testing
@testable import SwiftJLS

@Suite("Migrated scalar JPEG-LS")
struct ScalarCodecTests {
    static let fixtures: [String] = [
        "p2-1x1-max",
        "p2-1x19-noise",
        "p2-23x1-ramp",
        "p2-17x13-noise",
        "p2-33x9-zero",
        "p2-33x9-max",
        "p3-1x1-max",
        "p3-1x19-noise",
        "p3-23x1-ramp",
        "p3-17x13-noise",
        "p3-33x9-zero",
        "p3-33x9-max",
        "p4-1x1-max",
        "p4-1x19-noise",
        "p4-23x1-ramp",
        "p4-17x13-noise",
        "p4-33x9-zero",
        "p4-33x9-max",
        "p5-1x1-max",
        "p5-1x19-noise",
        "p5-23x1-ramp",
        "p5-17x13-noise",
        "p5-33x9-zero",
        "p5-33x9-max",
        "p6-1x1-max",
        "p6-1x19-noise",
        "p6-23x1-ramp",
        "p6-17x13-noise",
        "p6-33x9-zero",
        "p6-33x9-max",
        "p7-1x1-max",
        "p7-1x19-noise",
        "p7-23x1-ramp",
        "p7-17x13-noise",
        "p7-33x9-zero",
        "p7-33x9-max",
        "p8-1x1-max",
        "p8-1x19-noise",
        "p8-23x1-ramp",
        "p8-17x13-noise",
        "p8-33x9-zero",
        "p8-33x9-max",
        "p9-1x1-max",
        "p9-1x19-noise",
        "p9-23x1-ramp",
        "p9-17x13-noise",
        "p9-33x9-zero",
        "p9-33x9-max",
        "p10-1x1-max",
        "p10-1x19-noise",
        "p10-23x1-ramp",
        "p10-17x13-noise",
        "p10-33x9-zero",
        "p10-33x9-max",
        "p11-1x1-max",
        "p11-1x19-noise",
        "p11-23x1-ramp",
        "p11-17x13-noise",
        "p11-33x9-zero",
        "p11-33x9-max",
        "p12-1x1-max",
        "p12-1x19-noise",
        "p12-23x1-ramp",
        "p12-17x13-noise",
        "p12-33x9-zero",
        "p12-33x9-max",
        "p13-1x1-max",
        "p13-1x19-noise",
        "p13-23x1-ramp",
        "p13-17x13-noise",
        "p13-33x9-zero",
        "p13-33x9-max",
        "p14-1x1-max",
        "p14-1x19-noise",
        "p14-23x1-ramp",
        "p14-17x13-noise",
        "p14-33x9-zero",
        "p14-33x9-max",
        "p15-1x1-max",
        "p15-1x19-noise",
        "p15-23x1-ramp",
        "p15-17x13-noise",
        "p15-33x9-zero",
        "p15-33x9-max",
        "p16-1x1-max",
        "p16-1x19-noise",
        "p16-23x1-ramp",
        "p16-17x13-noise",
        "p16-33x9-zero",
        "p16-33x9-max"
    ]
    struct Fixture: Decodable, Sendable {
        let name: String, width: Int, height: Int, meaningfulBits: Int
        let near: Int?
    }
    struct Manifest: Decodable { let cases: [Fixture] }
    @Test func independentlyEncodedNearLosslessSamples() async throws {
        let manifest = try JSONDecoder().decode(Manifest.self, from: fixture("manifest", ext: "json"))
        for f in manifest.cases where (f.near ?? 0) > 0 {
            let near = try #require(f.near)
            let reference = try fixture(f.name, ext: "decoded.u16le")
            let source = try fixture(f.name, ext: "u16le")
            let decoded = try await Decoder().decode(fixture(f.name, ext: "jls"))
            let shape = try ImageDescriptor.greyscale16(width: f.width, height: f.height,
                meaningfulBits: f.meaningfulBits, rowBytes: f.width * 2 + 6)
            let image = try ImageDestination.allocate(descriptor: shape).writeUInt16 { x, y in
                let i = (y * f.width + x) * 2
                return UInt16(source[i]) | UInt16(source[i + 1]) << 8
            }
            let encoded = try await Encoder(configuration: .init(mode: .nearLossless(maximumAbsoluteError: near))).encode(image)
            let roundTrip = try await Decoder().decode(encoded.data)
            #expect(encoded.report.fidelity == .boundedError(near))
            #expect(decoded.report.fidelity == .boundedError(near))
            for y in 0..<f.height {
                for x in 0..<f.width {
                    let i = (y * f.width + x) * 2
                    let expected = UInt16(reference[i]) | UInt16(reference[i + 1]) << 8
                    #expect(try decoded.image.sampleUInt16(x: x, y: y) == expected, "\(f.name) [\(x),\(y)]")
                    let error = try abs(Int(roundTrip.image.sampleUInt16(x: x, y: y)) - Int(image.sampleUInt16(x: x, y: y)))
                    #expect(error <= near, "\(f.name) [\(x),\(y)]")
                }
            }
        }
    }
    private func fixture(_ name: String, ext: String) throws -> Data {
        let directory = try #require(Bundle.module.resourceURL).appendingPathComponent("Fixtures")
        return try Data(contentsOf: directory.appendingPathComponent(name + "." + ext))
    }
    @Test(arguments: fixtures)
    func independentlyEncodedSamplesDecodeExactly(_ name: String) async throws {
        let data = try fixture(name, ext: "jls")
        let expected = try fixture(name, ext: "u16le")
        let decoder = try Decoder()
        let info = try decoder.inspect(data)
        let d = info.descriptor
        let padded = try ImageDescriptor.greyscale16(width: d.width, height: d.height,
            meaningfulBits: d.meaningfulBits, rowBytes: d.width * 2 + 6, offset: 2)
        let destination = try ImageDestination.allocate(descriptor: padded)
        let identity = destination.storage.allocationID
        let result = try await decoder.decode(data, into: destination)
        #expect(result.image.storage.allocationID == identity)
        #expect(result.report.pixelAllocationCount == 0 && result.report.copyEvents.isEmpty)
        for y in 0..<d.height {
            for x in 0..<d.width {
                let i = (y * d.width + x) * 2
                let sample = UInt16(expected[i]) | UInt16(expected[i + 1]) << 8
                #expect(try result.image.sampleUInt16(x: x, y: y) == sample)
            }
        }
        // Exercise both directions over nontrivial independently specified samples.
        let encoded = try await Encoder().encode(result.image)
        let decoded = try await decoder.decode(encoded.data)
        #expect(decoded.image.descriptor.meaningfulBits == d.meaningfulBits)
        for y in 0..<d.height {
            for x in 0..<d.width {
                #expect(try decoded.image.sampleUInt16(x: x, y: y) == result.image.sampleUInt16(x: x, y: y))
            }
        }
    }
    @Test func sampleOrderAndPaddingDoNotChangeCodestream() async throws {
        let little = try ImageDescriptor.greyscale16(width: 17, height: 13, meaningfulBits: 12)
        let plane = try PlaneDescriptor(width: 17, height: 13, rowBytes: 42, byteCount: 546)
        let big = try ImageDescriptor(width: 17, height: 13, meaningfulBits: 12, byteOrder: .bigEndian, planes: [plane])
        let first = try ImageDestination.allocate(descriptor: little).writeUInt16 { x, y in UInt16((x * 251 + y * 131) & 4095) }
        let second = try ImageDestination.allocate(descriptor: big).writeUInt16 { x, y in UInt16((x * 251 + y * 131) & 4095) }
        let encoded = try await Encoder().encode(first)
        #expect(try await Encoder().encode(second).data == encoded.data)
        let destination = try ImageDestination.allocate(descriptor: big)
        let decoded = try await Decoder().decode(encoded.data, into: destination)
        #expect(try decoded.image.sampleUInt16(x: 16, y: 12) == second.sampleUInt16(x: 16, y: 12))
    }
    @Test func slicedInputUsesRelativeOffsets() async throws {
        let original = try fixture("p16-17x13-noise", ext: "jls")
        let slice = (Data(repeating: 7, count: 19) + original).dropFirst(19)
        let decoded = try await Decoder().decode(slice)
        #expect(decoded.image.descriptor.meaningfulBits == 16)
        #expect(try await Encoder().encode(decoded.image).data.count > 0)
    }
    @Test func truncationAndUnaryBombFailWithoutPublishing() async throws {
        let original = try fixture("p12-17x13-noise", ext: "jls")
        for end in 0..<original.count {
            await #expect(throws: CodecError.self) { try await Decoder().decode(original.prefix(end)) }
        }
        let header = try JPEGLSHeader.parse(original, budget: CodecBudget(limits: .default))
        let corrupt = original.prefix(header.scan.lowerBound) + Data(repeating: 0, count: 10000) + Data([255, 217])
        let shape = try ImageDescriptor.greyscale16(width: 17, height: 13, meaningfulBits: 12)
        let destination = try ImageDestination.allocate(descriptor: shape)
        await #expect(throws: CodecError.self) { try await Decoder().decode(corrupt, into: destination) }
        #expect(throws: CodecError.self) { try destination.writeUInt16 { _, _ in 0 } }
    }
    @Test func surplusEntropyAndNonzeroPaddingAreRejected() async throws {
        let original = try fixture("p8-1x1-max", ext: "jls")
        let surplus = original.dropLast(2) + Data([0, 0]) + original.suffix(2)
        await #expect(throws: CodecError.self) { try await Decoder().decode(surplus) }
        let reader = JPEGLSBitstreamReader(data: Data([0b10100001]))
        _ = try reader.readBits(3)
        #expect(throws: CodecError.self) { try reader.validateEndOfScan() }
    }
    @Test func customPresetTablesAreAdmittedBeforeAllocation() async throws {
        let original = try fixture("p16-33x9-zero", ext: "jls")
        // Valid LSE with maximum thresholds/reset; zero runs are independent
        // of the nonzero-gradient tables and context reset interval.
        let lse = Data([255, 248, 0, 13, 1, 255, 255, 0, 1, 0, 1, 255, 255, 255, 255])
        let input = original.prefix(15) + lse + original.dropFirst(30)
        let limits = try ResourceLimits(maximumWorkspaceBytes: 128 * 1024)
        await #expect(throws: CodecError.self) {
            try await Decoder().decode(input, options: .init(resourceLimits: limits))
        }
        let decoded = try await Decoder().decode(input)
        #expect(try decoded.image.sampleUInt16(x: 32, y: 8) == 0)
    }
    @Test func cancellationFromCompletionCallbackIsPropagated() async throws {
        let data = try fixture("p12-17x13-noise", ext: "jls")
        let callback: @Sendable (ProgressUpdate) -> Void = { update in
            if update.phase == .completed { withUnsafeCurrentTask { $0?.cancel() } }
        }
        let decode = Task { try await Decoder().decode(data, options: .init(progress: callback)) }
        await #expect(throws: CancellationError.self) { try await decode.value }
        let image = try await Decoder().decode(data).image
        let encode = Task { try await Encoder().encode(image, options: .init(progress: callback)) }
        await #expect(throws: CancellationError.self) { try await encode.value }
    }
    @Test func limitsAndCancellationPrecedePublication() async throws {
        let shape = try ImageDescriptor.greyscale16(width: 17, height: 13, meaningfulBits: 12)
        let image = try ImageDestination.allocate(descriptor: shape).writeUInt16 { x, y in UInt16(x + y) }
        let limits = try ResourceLimits(maximumWorkspaceBytes: 1)
        await #expect(throws: CodecError.self) { try await Encoder().encode(image, options: .init(resourceLimits: limits)) }
        let cancelled = Task {
            try await Encoder().encode(image, options: .init(progress: { update in
                if update.phase == .processing { withUnsafeCurrentTask { $0?.cancel() } }
            }))
        }
        await #expect(throws: CancellationError.self) { try await cancelled.value }
        let short = try ResourceLimits(deadlineSeconds: .leastNonzeroMagnitude)
        await #expect(throws: CodecError.self) { try await Encoder().encode(image, options: .init(resourceLimits: short)) }
    }
}
