// SPDX-License-Identifier: MIT
import Foundation
import Testing
@testable import SwiftJLS

@Suite("JPEG-LS Parallel & Accelerated Backend Parity")
struct ParallelAccelerationTests {
    @Test func monochromeRestartStripsAndBitStuffingParity() throws {
        let width = 131
        let height = 97
        let descriptor = try ImageDescriptor.greyscale16(width: width, height: height, meaningfulBits: 16)
        let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { x, y in
            if y % 11 == 0 {
                // Flat run row
                return UInt16((y * 257) & 0xFFFF)
            } else if y % 7 == 0 && x >= 16 && x < 80 {
                // Mid-row flat run
                return 0xFF00
            } else {
                // High-entropy / 0xFF-heavy pattern exercising SWAR + stuffing paths
                let raw = (x * 7919 + y * 65521) ^ 0xFF7F
                return UInt16(truncatingIfNeeded: raw)
            }
        }

        for interval in [0, 8, 16] {
            for mode: CompressionMode in [.lossless, .nearLossless(maximumAbsoluteError: 3)] {
                let config = try EncoderConfiguration(
                    mode: mode,
                    codecOptions: try CodecOptions(restartIntervalLines: interval)
                )
                let encoder = try SwiftJLS.Encoder(configuration: config)
                let decoder = try SwiftJLS.Decoder()

                let scalarLimits = try ResourceLimits(maximumWorkers: 1)
                let parallelLimits = try ResourceLimits(maximumWorkers: 8)

                let encScalar = try encoder.encodeSynchronously(
                    image,
                    options: EncodeOptions(resourceLimits: scalarLimits, executionPolicy: .scalarCPU)
                )
                let encAccel = try encoder.encodeSynchronously(
                    image,
                    options: EncodeOptions(resourceLimits: parallelLimits, executionPolicy: .required(.accelerated))
                )

                #expect(encScalar.report.backend == .scalarCPU)
                #expect(encAccel.report.backend == .accelerated)
                #expect(encScalar.data == encAccel.data)

                let info = try decoder.inspectSynchronously(encAccel.data)
                #expect(info.descriptor.width == width && info.descriptor.height == height)

                let decScalar = try decoder.decodeSynchronously(
                    encAccel.data,
                    options: DecodeOptions(resourceLimits: scalarLimits, executionPolicy: .scalarCPU)
                )
                let destination = try ImageDestination.allocate(descriptor: descriptor)
                let decAccel = try decoder.decodeSynchronously(
                    encAccel.data,
                    into: destination,
                    options: DecodeOptions(resourceLimits: parallelLimits, executionPolicy: .required(.accelerated))
                )

                #expect(decScalar.report.backend == .scalarCPU)
                #expect(decAccel.report.backend == .accelerated)

                for y in 0..<height {
                    for x in 0..<width {
                        let s0 = try decScalar.image.sampleUInt16(x: x, y: y)
                        let s1 = try decAccel.image.sampleUInt16(x: x, y: y)
                        #expect(s0 == s1)
                        let orig = try image.sampleUInt16(x: x, y: y)
                        if mode == .lossless {
                            #expect(s1 == orig)
                        } else {
                            #expect(abs(Int(s1) - Int(orig)) <= 3)
                        }
                    }
                }
            }
        }
    }

    @Test(arguments: [true, false])
    func rgbNonInterleavedAndInterleavedParity(planar: Bool) throws {
        let width = 73
        let height = 55
        let planes: [PlaneDescriptor]
        if planar {
            let row = width
            let planeBytes = row * height
            planes = try (0..<3).map { c in
                try PlaneDescriptor(
                    width: width, height: height, components: [c],
                    offset: c * planeBytes, sampleStride: 1, pixelStride: 1,
                    rowBytes: row, byteCount: (c + 1) * planeBytes
                )
            }
        } else {
            let row = width * 3
            planes = [
                try PlaneDescriptor(
                    width: width, height: height, components: [0, 1, 2],
                    offset: 0, sampleStride: 1, pixelStride: 3,
                    rowBytes: row, byteCount: row * height
                )
            ]
        }
        let descriptor = try ImageDescriptor(
            width: width, height: height, storageBits: 8, meaningfulBits: 8,
            components: [.red, .green, .blue], colour: .rgb, planes: planes
        )
        let image = try ImageDestination.allocate(descriptor: descriptor).write { bytes in
            for y in 0..<height {
                for x in 0..<width {
                    for c in 0..<3 {
                        let val: UInt8 = (y % 9 == 0)
                            ? UInt8((c * 77 + y) & 0xFF)
                            : UInt8((x * 13 + y * 29 + c * 97) & 0xFF)
                        let off = planar
                            ? (c * width * height + y * width + x)
                            : ((y * width + x) * 3 + c)
                        bytes[off] = val
                    }
                }
            }
        }

        let configurations: [(CodecOptions.InterleaveMode, Int)] = [
            (.none, 0),
            (.none, 12),
            (.line, 0),
            (.sample, 0),
        ]

        for (ilv, interval) in configurations {
            let config = try EncoderConfiguration(
                mode: .lossless,
                codecOptions: try CodecOptions(restartIntervalLines: interval, interleaveMode: ilv)
            )
            let encoder = try SwiftJLS.Encoder(configuration: config)
            let decoder = try SwiftJLS.Decoder()

            let encScalar = try encoder.encodeSynchronously(
                image,
                options: EncodeOptions(resourceLimits: try ResourceLimits(maximumWorkers: 1), executionPolicy: .scalarCPU)
            )
            let encAccel = try encoder.encodeSynchronously(
                image,
                options: EncodeOptions(resourceLimits: try ResourceLimits(maximumWorkers: 6), executionPolicy: .required(.accelerated))
            )
            #expect(encScalar.data == encAccel.data)

            let dstScalar = try ImageDestination.allocate(descriptor: descriptor)
            let dstAccel = try ImageDestination.allocate(descriptor: descriptor)
            let decScalar = try decoder.decodeSynchronously(
                encAccel.data, into: dstScalar,
                options: DecodeOptions(resourceLimits: try ResourceLimits(maximumWorkers: 1), executionPolicy: .scalarCPU)
            )
            let decAccel = try decoder.decodeSynchronously(
                encAccel.data, into: dstAccel,
                options: DecodeOptions(resourceLimits: try ResourceLimits(maximumWorkers: 6), executionPolicy: .required(.accelerated))
            )
            #expect(decAccel.report.backend == .accelerated)

            try image.storage.withUnsafeBytes { expected in
                try decScalar.image.storage.withUnsafeBytes { b0 in
                    try decAccel.image.storage.withUnsafeBytes { b1 in
                        #expect(Array(b0) == Array(expected))
                        #expect(Array(b1) == Array(expected))
                    }
                }
            }
        }
    }

    @Test func simulatedUnavailableFallbackIsTruthful() throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 8, height: 8, meaningfulBits: 12)
        let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { x, y in
            UInt16((x * 17 + y * 31) & 0x0FFF)
        }
        let encoder = try SwiftJLS.Encoder()
        let decoder = try SwiftJLS.Decoder()

        try AccelerationRuntime.withSimulatedUnavailable {
            let encoded = try encoder.encodeSynchronously(
                image,
                options: EncodeOptions(executionPolicy: .preferred(.accelerated))
            )
            #expect(encoded.report.backend == .scalarCPU)
            #expect(encoded.report.fallbackReason == "Acceleration unavailable; scalar CPU selected.")

            let decoded = try decoder.decodeSynchronously(
                encoded.data,
                options: DecodeOptions(executionPolicy: .preferred(.accelerated))
            )
            #expect(decoded.report.backend == .scalarCPU)
            #expect(decoded.report.fallbackReason == "Acceleration unavailable; scalar CPU selected.")
        }
    }
}
