// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization
import Testing
@testable import SwiftJLS

@Suite("Lossless precision admission")
struct LosslessPrecisionValidationTests {
    private let width = 519, height = 4

    private func image(bits: Int, storageBits: Int, order: ByteOrder, maximum: Int,
                       ramp: Bool, invalidIndex: Int? = nil) throws -> Image {
        let sampleBytes = storageBits / 8
        let offset = sampleBytes
        let rowBytes = (width + 5) * sampleBytes
        let plane = try PlaneDescriptor(width: width, height: height, offset: offset,
            sampleStride: sampleBytes, pixelStride: sampleBytes, rowBytes: rowBytes,
            byteCount: offset + rowBytes * height)
        let shape = try ImageDescriptor(width: width, height: height, storageBits: storageBits,
            meaningfulBits: bits, byteOrder: order, planes: [plane])
        return try ImageDestination.allocate(descriptor: shape).write { bytes in
            // Padding exceeds every narrow sample maximum and must be ignored.
            bytes.initializeMemory(as: UInt8.self, repeating: 0xff)
            for y in 0..<height { for x in 0..<width {
                let value = y * width + x == invalidIndex ? maximum + 1
                    : (ramp ? (x * 13 + y * 17) % (maximum + 1) : 0)
                let at = offset + y * rowBytes + x * sampleBytes
                bytes[at] = UInt8(truncatingIfNeeded: sampleBytes == 1 || order == .littleEndian ? value : value >> 8)
                if sampleBytes == 2 {
                    bytes[at + 1] = UInt8(truncatingIfNeeded: order == .littleEndian ? value >> 8 : value)
                }
            } }
        }
    }

    private func expectInvalid(_ source: Image, encoder: Encoder) async throws {
        let completed = Mutex(false)
        do {
            _ = try await encoder.encode(source, options: .init(progress: { update in
                if update.phase == .completed { completed.withLock { $0 = true } }
            }))
            Issue.record("Out-of-range lossless sample was accepted.")
        } catch let error as CodecError {
            #expect(error.category == .invalidArgument)
        }
        #expect(!completed.withLock { $0 })
    }

    @Test func invalidRunSamplesAndInterruptionsCannotEscapeValidation() async throws {
        for (bits, storageBits) in [(7, 8), (12, 16)] {
            let maximum = (1 << bits) - 1
            for order: ByteOrder in [.littleEndian, .bigEndian] {
                for interval in [0, 2] {
                    let encoder = try Encoder(configuration: .init(codecOptions: .init(restartIntervalLines: interval)))
                    // Include both explicit run starts and interruptions after
                    // SIMD/chunk boundaries, the restart row and the final sample.
                    for index in [0, 1, 15, 16, 255, 256, width - 1, width * 2, width * height - 1] {
                        let source = try image(bits: bits, storageBits: storageBits, order: order,
                            maximum: maximum, ramp: false, invalidIndex: index)
                        try await expectInvalid(source, encoder: encoder)
                    }
                }
            }
        }
    }

    @Test func customMaximumChecksRegularSamplesAndRestartRows() async throws {
        let maximum = 1000
        let preset = try CodecOptions.Preset(maximumSampleValue: maximum,
            threshold1: 3, threshold2: 7, threshold3: 21, reset: 64)
        let encoder = try Encoder(configuration: .init(codecOptions: .init(restartIntervalLines: 2, preset: preset)))
        for order: ByteOrder in [.littleEndian, .bigEndian] {
            for index in [17, width + 17, width * 2, width * 2 + 258, width * height - 1] {
                // A full-width descriptor still needs the stricter preset bound.
                let source = try image(bits: 16, storageBits: 16, order: order,
                    maximum: maximum, ramp: true, invalidIndex: index)
                try await expectInvalid(source, encoder: encoder)
            }
            let source = try image(bits: 16, storageBits: 16, order: order, maximum: maximum, ramp: true)
            let encoded = try await encoder.encode(source)
            let decoded = try await Decoder().decode(encoded.data)
            for y in 0..<height { for x in 0..<width {
                #expect(try decoded.image.sampleUInt16(x: x, y: y) == source.sampleUInt16(x: x, y: y))
            } }
        }
    }

    private func rgbImage(bits: Int, maximum: Int, planar: Bool, order: ByteOrder,
                          ramp: Bool, invalidComponent: Int? = nil,
                          invalidIndex: Int? = nil) throws -> (Image, Data) {
        let helper = ComponentCodecTests()
        let f = ComponentCodecTests.Fixture(name: "precision-admission", width: 263, height: 3,
            meaningfulBits: bits, near: 0, components: 3, interleave: 0, rgb: true)
        let shape = try helper.descriptor(f, planar: planar, storageBits: 16, order: order)
        var reference = Data()
        for c in 0..<3 { for y in 0..<f.height { for x in 0..<f.width {
            let value = c == invalidComponent && y * f.width + x == invalidIndex ? maximum + 1
                : (ramp ? (x * 13 + y * 17 + c * 31) % (maximum + 1) : 0)
            reference.append(UInt8(truncatingIfNeeded: value))
            reference.append(UInt8(truncatingIfNeeded: value >> 8))
        } } }
        let image = try ImageDestination.allocate(descriptor: shape).write { bytes in
            bytes.initializeMemory(as: UInt8.self, repeating: 0xff)
            for c in 0..<3 { for y in 0..<f.height { for x in 0..<f.width {
                let at = try helper.offset(shape, component: c, x: x, y: y)
                let from = ((c * f.height + y) * f.width + x) * 2
                bytes[at] = reference[from + (order == .littleEndian ? 0 : 1)]
                bytes[at + 1] = reference[from + (order == .littleEndian ? 1 : 0)]
            } } }
        }
        return (image, reference)
    }

    @Test func componentRunsCheckEveryLaneAndInterleave() async throws {
        for mode: CodecOptions.InterleaveMode in [.none, .line, .sample] {
            let encoder = try Encoder(configuration: .init(codecOptions: .init(
                restartIntervalLines: mode == .none ? 2 : 0, interleaveMode: mode)))
            for planar in [false, true] { for order: ByteOrder in [.littleEndian, .bigEndian] {
                for component in 0..<3 { for index in [0, 256, 263 * 3 - 1] {
                    let (source, _) = try rgbImage(bits: 12, maximum: 4095, planar: planar,
                        order: order, ramp: false, invalidComponent: component, invalidIndex: index)
                    try await expectInvalid(source, encoder: encoder)
                } }
            } }
        }
    }

    @Test func componentCustomMaximumChecksRegularSamplesAndPreservesLayouts() async throws {
        let preset = try CodecOptions.Preset(maximumSampleValue: 1000,
            threshold1: 3, threshold2: 7, threshold3: 21, reset: 64)
        for mode: CodecOptions.InterleaveMode in [.none, .line, .sample] {
            let encoder = try Encoder(configuration: .init(codecOptions: .init(
                restartIntervalLines: mode == .none ? 2 : 0, preset: preset, interleaveMode: mode)))
            for planar in [false, true] { for order: ByteOrder in [.littleEndian, .bigEndian] {
                for component in 0..<3 {
                    let (source, _) = try rgbImage(bits: 16, maximum: 1000, planar: planar,
                        order: order, ramp: true, invalidComponent: component, invalidIndex: 263 * 2 + 17)
                    try await expectInvalid(source, encoder: encoder)
                }
                let (source, reference) = try rgbImage(bits: 16, maximum: 1000, planar: planar,
                    order: order, ramp: true)
                let encoded = try await encoder.encode(source)
                let decoded = try await Decoder().decode(encoded.data)
                try ComponentCodecTests().check(decoded.image, against: reference, maximumError: 0, padding: false)
            } }
        }
    }

    @Test func nearLosslessAndHPStillValidateOriginalComponentSamples() async throws {
        for mode: CodecOptions.InterleaveMode in [.none, .line, .sample] {
            let encoder = try Encoder(configuration: .init(mode: .nearLossless(maximumAbsoluteError: 3),
                codecOptions: .init(restartIntervalLines: 0, interleaveMode: mode)))
            let (source, _) = try rgbImage(bits: 12, maximum: 4095, planar: false,
                order: .bigEndian, ramp: false, invalidComponent: 2, invalidIndex: 263 * 3 - 1)
            try await expectInvalid(source, encoder: encoder)
        }
        for mode: CodecOptions.InterleaveMode in [.line, .sample] {
            for transform: CodecOptions.ColourTransform in [.hp1, .hp2, .hp3] {
                let encoder = try Encoder(configuration: .init(codecOptions: .init(
                    restartIntervalLines: 0, interleaveMode: mode, colourTransform: transform)))
                // HP modular arithmetic could hide 256 in an 8-bit image if
                // validation of the original 16-bit container were removed.
                let (source, _) = try rgbImage(bits: 8, maximum: 255, planar: true,
                    order: .littleEndian, ramp: false, invalidComponent: 0, invalidIndex: 263 * 3 - 1)
                try await expectInvalid(source, encoder: encoder)
            }
        }
    }
}
