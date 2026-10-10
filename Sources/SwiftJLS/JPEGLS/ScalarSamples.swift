// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

// These views exist only inside their owner's synchronous scoped borrow. They
// are deliberately not Sendable and cannot be retained by a codec operation.
// Byte-wise access supports providers whose physical address is not aligned.
struct ScalarSampleReader {
    let bytes: UnsafeRawBufferPointer
    let littleEndian: Bool
    var sampleBytes: Int = 2
    var count: Int { bytes.count / sampleBytes }
    subscript(index: Int) -> UInt16 {
        if sampleBytes == 1 { return UInt16(bytes[index]) }
        let lo = UInt16(bytes[index * 2]), hi = UInt16(bytes[index * 2 + 1])
        return littleEndian ? lo | hi << 8 : lo << 8 | hi
    }
}

struct ScalarSampleWriter {
    let bytes: UnsafeMutableRawBufferPointer
    let littleEndian: Bool
    var sampleBytes: Int = 2
    var count: Int { bytes.count / sampleBytes }
    subscript(index: Int) -> UInt16 {
        get {
            if sampleBytes == 1 { return UInt16(bytes[index]) }
            let lo = UInt16(bytes[index * 2]), hi = UInt16(bytes[index * 2 + 1])
            return littleEndian ? lo | hi << 8 : lo << 8 | hi
        }
        nonmutating set {
            if sampleBytes == 1 { bytes[index] = UInt8(truncatingIfNeeded: newValue); return }
            let lo = UInt8(truncatingIfNeeded: newValue), hi = UInt8(newValue >> 8)
            bytes[index * 2] = littleEndian ? lo : hi
            bytes[index * 2 + 1] = littleEndian ? hi : lo
        }
    }
}
