// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

@Suite("Sample-interleaved native destination views")
struct SampleNativeDecodeTests {
    private enum Layout: CaseIterable { case native, padded, sparse, oppositeEndian }
    private struct Observation {
        let samples: [UInt16]
        let checkpoints: Int
        let cancelled: Bool
    }

    private func codestream(width: Int, height: Int, bits: Int, near: Int,
                            zero: Bool = false) async throws -> (Data, [UInt16]) {
        let helper = ComponentCodecTests()
        let fixture = ComponentCodecTests.Fixture(name: "native-sample-view", width: width, height: height,
            meaningfulBits: bits, near: near, components: 3, interleave: 2, rgb: true)
        let descriptor = try helper.descriptor(fixture, planar: true, storageBits: 16, order: .littleEndian)
        let maximum = (1 << bits) - 1
        var samples: [UInt16] = []
        for component in 0..<3 { for y in 0..<height { for x in 0..<width {
            // Zero prefixes cause real runs/interruption; following rows mix
            // constant, ramp and irregular gradients. Width one also changes
            // between rows, exercising both causal left-edge conventions.
            let value: Int
            if zero || (y < 2 && x < max(1, width / 2)) { value = 0 }
            else if y == 2 { value = maximum / 3 + component * 17 }
            else { value = ((x * 73 + y * 41 + component * 151) * 257) & maximum }
            samples.append(UInt16(value))
        } } }
        let image = try ImageDestination.allocate(descriptor: descriptor).write { bytes in
            bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
            for component in 0..<3 { for y in 0..<height { for x in 0..<width {
                let at = try helper.offset(descriptor, component: component, x: x, y: y)
                let value = samples[(component * height + y) * width + x]
                bytes[at] = UInt8(truncatingIfNeeded: value)
                bytes[at + 1] = UInt8(truncatingIfNeeded: value >> 8)
            } } }
        }
        let encoder = try Encoder(configuration: .init(
            mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
            codecOptions: .init(restartIntervalLines: 0, interleaveMode: .sample)))
        return (try await encoder.encode(image).data, samples)
    }

    private func decode(_ data: Data, layout: Layout, cancelAt: Int? = nil) throws -> Observation {
        let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        let width = header.width, height = header.height
        let pixelStride = layout == .sparse ? 6 : 2
        let rowBytes = width * pixelStride + (layout == .padded ? 6 : 0)
        let planeStride = rowBytes * height + 8
        let capacity = 3 * planeStride + 16
        let nativeLittle = UInt16(littleEndian: 1) == 1
        let little = layout == .oppositeEndian ? !nativeLittle : nativeLittle

        // Alignment two and rebasing by one prove an odd physical origin;
        // all four layouts retain guard bytes, plane gaps and a trailing guard.
        // No raw address escapes this synchronous test helper.
        let allocation = UnsafeMutableRawPointer.allocate(byteCount: capacity + 2, alignment: 2)
        defer { allocation.deallocate() }
        let allBytes = UnsafeMutableRawBufferPointer(start: allocation, count: capacity + 2)
        allBytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
        let bytes = UnsafeMutableRawBufferPointer(start: allocation.advanced(by: 1), count: capacity)
        let views = (0..<3).map { component in
            ComponentSampleWriter(bytes: bytes, width: width, height: height,
                offset: 8 + component * planeStride, rowBytes: rowBytes, pixelStride: pixelStride,
                sampleBytes: 2, littleEndian: little)
        }
        let scan = try #require(header.scans.first)
        let reader = JPEGLSBitstreamReader(data: data[scan])
        var checkpoints = 0
        var cancelled = false
        do {
            try JPEGLSScalarKernel().decodeInterleaved(views: views, width: width, height: height,
                mode: .sample, near: header.near, parameters: header.parameters, bits: header.bits,
                reader: reader, checkpoint: {
                    checkpoints += 1
                    if let cancelAt, checkpoints == cancelAt { throw CancellationError() }
                })
            try reader.validateEndOfScan()
        } catch is CancellationError {
            cancelled = true
        }
        var samples: [UInt16] = []
        var used = Set<Int>()
        for component in 0..<3 { for y in 0..<height { for x in 0..<width {
            let at = 8 + component * planeStride + y * rowBytes + x * pixelStride
            let first = UInt16(bytes[at]), second = UInt16(bytes[at + 1])
            samples.append(little ? first | second << 8 : first << 8 | second)
            used.insert(at); used.insert(at + 1)
        } } }
        for i in bytes.indices where !used.contains(i) { #expect(bytes[i] == 0xa5) }
        #expect(allBytes[0] == 0xa5 && allBytes[capacity + 1] == 0xa5)
        return Observation(samples: samples, checkpoints: checkpoints, cancelled: cancelled)
    }

    @Test func oddNativePlanesMatchGeneralLayoutsAcrossCodingTransitions() async throws {
        for width in [1, 17, 65] { for bits in [12, 16] { for near in [0, 3] {
            let (data, original) = try await codestream(width: width, height: 4, bits: bits, near: near)
            let native = try decode(data, layout: .native)
            #expect(!native.cancelled)
            #expect(native.samples.count == original.count)
            for (actual, expected) in zip(native.samples, original) {
                #expect(abs(Int(actual) - Int(expected)) <= near)
            }
            for layout in [Layout.padded, .sparse, .oppositeEndian] {
                let fallback = try decode(data, layout: layout)
                #expect(!fallback.cancelled)
                #expect(fallback.samples == native.samples)
                #expect(fallback.checkpoints == native.checkpoints)
            }
        } } }
    }

    @Test func cancellationPreservesUnwrittenRowsAndLongRunTail() async throws {
        for width in [1, 17, 65] { for (bits, near) in [(12, 0), (16, 3)] {
            let (data, _) = try await codestream(width: width, height: 2, bits: bits, near: near, zero: true)
            for layout in Layout.allCases {
                for (cancelAt, writtenPerComponent) in [(1, 0), (4, min(width, 64))] {
                    let result = try decode(data, layout: layout, cancelAt: cancelAt)
                    #expect(result.cancelled && result.checkpoints == cancelAt)
                    for component in 0..<3 { for index in 0..<(width * 2) {
                        // Callback four precedes row two for short runs, or
                        // the second 64-sample fill for width 65. Observe real
                        // writes: no later sample may change from its sentinel.
                        let expected: UInt16 = index < writtenPerComponent ? 0 : 0xa5a5
                        #expect(result.samples[component * width * 2 + index] == expected)
                    } }
                }
            }
        } }
    }
}
