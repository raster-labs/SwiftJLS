// SPDX-License-Identifier: Apache-2.0
import Testing
@testable import SwiftJLS

@Suite("Component precision admission")
struct ComponentPrecisionTests {
    @Test func paddingByteOrderAndTailSamples() throws {
        let width = 263, height = 2, offset = 1
        for sampleBytes in [1, 2] {
            for maximum in sampleBytes == 1 ? [127] : [1000, 4095] {
                for littleEndian in [false, true] {
                    for spacing in [1, 3] {
                        for padding in [0, 1, 8] {
                            let pixelStride = sampleBytes * spacing
                            let rowBytes = width * pixelStride + padding
                            var bytes = [UInt8](repeating: 0xff, count: offset + height * rowBytes)
                            func write(_ value: Int, x: Int, y: Int) {
                                let at = offset + y * rowBytes + x * pixelStride
                                if sampleBytes == 1 { bytes[at] = UInt8(value) }
                                else {
                                    bytes[at] = UInt8(truncatingIfNeeded: littleEndian ? value : value >> 8)
                                    bytes[at + 1] = UInt8(truncatingIfNeeded: littleEndian ? value >> 8 : value)
                                }
                            }
                            for y in 0..<height { for x in 0..<width { write(maximum, x: x, y: y) } }
                            func validate() throws {
                                try bytes.withUnsafeBytes { raw in
                                    try ComponentSampleReader(bytes: raw, width: width, height: height,
                                        offset: offset, rowBytes: rowBytes, pixelStride: pixelStride,
                                        sampleBytes: sampleBytes, littleEndian: littleEndian)
                                        .validate(maximum: maximum, checkpoint: {})
                                }
                            }
                            try validate() // Padding deliberately exceeds the sample maximum.
                            for x in [0, 255, 256, 262] {
                                write(maximum + 1, x: x, y: 1)
                                #expect(throws: CodecError.self) { try validate() }
                                write(maximum, x: x, y: 1)
                            }
                        }
                    }
                }
            }
        }
    }

    @Test func validationPropagatesCancellation() throws {
        let bytes = [UInt8](repeating: 0, count: 4096)
        for pixelStride in [2, 6] {
            bytes.withUnsafeBytes { raw in
                let view = ComponentSampleReader(bytes: raw, width: 263, height: 2,
                    offset: 0, rowBytes: 263 * pixelStride, pixelStride: pixelStride,
                    sampleBytes: 2, littleEndian: true)
                var checkpoints = 0
                #expect(throws: CancellationError.self) {
                    try view.validate(maximum: 4095, checkpoint: {
                        checkpoints += 1
                        if checkpoints == 2 { throw CancellationError() }
                    })
                }
                #expect(checkpoints == 2)
            }
        }
    }
}
