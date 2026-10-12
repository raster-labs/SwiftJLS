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
        let value = bytes.loadUnaligned(fromByteOffset: index * 2, as: UInt16.self)
        return littleEndian ? UInt16(littleEndian: value) : UInt16(bigEndian: value)
    }
    /// Four adjacent samples, loaded without an alignment precondition. The
    /// caller proves the four-sample extent before entering this fast path.
    @inline(__always)
    func fourEqual(at index: Int, to value: UInt16) -> Bool {
        if sampleBytes == 1 {
            let packed = UInt32(UInt8(truncatingIfNeeded: value)) * 0x01010101
            return bytes.loadUnaligned(fromByteOffset: index, as: UInt32.self) == packed
        }
        let ordered = littleEndian ? value.littleEndian : value.bigEndian
        let packed = UInt64(ordered) * 0x0001000100010001
        return bytes.loadUnaligned(fromByteOffset: index * 2, as: UInt64.self) == packed
    }

    /// No padding is included. Full-width samples cannot exceed their storage
    /// range; narrower power-of-two alphabets can be checked four at a time.
    func validate(width: Int, height: Int, rowStride: Int, maximum: Int,
                  checkpoint: () throws -> Void) throws {
        guard maximum < (sampleBytes == 1 ? 255 : 65535) else { return }
        let maskable = sampleBytes == 2 && maximum & (maximum + 1) == 0
        let mask = UInt16(truncatingIfNeeded: ~maximum)
        let orderedMask = littleEndian ? mask.littleEndian : mask.bigEndian
        let packedMask = UInt64(orderedMask) * 0x0001000100010001
        for y in 0..<height {
            let base = y * rowStride
            for first in stride(from: 0, to: width, by: 256) {
                try checkpoint()
                let end = min(width, first + 256)
                var x = first
                if maskable {
                    while x + 4 <= end {
                        guard bytes.loadUnaligned(fromByteOffset: (base + x) * 2, as: UInt64.self) & packedMask == 0 else {
                            throw CodecError(.invalidArgument, "Sample exceeds declared meaningful precision.")
                        }
                        x += 4
                    }
                }
                while x < end {
                    guard self[base + x] <= maximum else {
                        throw CodecError(.invalidArgument, "Sample exceeds declared meaningful precision.")
                    }
                    x += 1
                }
            }
        }
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
            let value = bytes.loadUnaligned(fromByteOffset: index * 2, as: UInt16.self)
            return littleEndian ? UInt16(littleEndian: value) : UInt16(bigEndian: value)
        }
        nonmutating set {
            if sampleBytes == 1 { bytes[index] = UInt8(truncatingIfNeeded: newValue); return }
            let ordered = littleEndian ? newValue.littleEndian : newValue.bigEndian
            // SE-0349 (Swift 5.7) permits unaligned trivial stores as well as
            // unaligned loads. Extents are proved at kernel admission.
            bytes.storeBytes(of: ordered, toByteOffset: index * 2, as: UInt16.self)
        }
    }
    /// Bounded run fill. The caller checks cancellation between <=256-sample
    /// groups and proves that the range contains only this row's sample bytes.
    func fill(_ value: UInt16, range: Range<Int>) {
        var i = range.lowerBound
        if sampleBytes == 1 {
            let packed = UInt32(UInt8(truncatingIfNeeded: value)) * 0x01010101
            while i + 4 <= range.upperBound {
                bytes.storeBytes(of: packed, toByteOffset: i, as: UInt32.self)
                i += 4
            }
        } else {
            let ordered = littleEndian ? value.littleEndian : value.bigEndian
            let packed = UInt64(ordered) * 0x0001000100010001
            while i + 4 <= range.upperBound {
                bytes.storeBytes(of: packed, toByteOffset: i * 2, as: UInt64.self)
                i += 4
            }
        }
        while i < range.upperBound { self[i] = value; i += 1 }
    }

}
