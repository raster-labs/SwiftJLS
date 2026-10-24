// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

protocol JPEGSampleReader {
    var count: Int { get }
    var scalarLayout: (view: ScalarSampleReader, rowStride: Int)? { get }
    var nativeLayout: NativeUInt16Reader? { get }
    subscript(index: Int) -> UInt16 { get }
    func fourEqual(at index: Int, to value: UInt16) -> Bool
    func matchingPrefix(in range: Range<Int>, to value: UInt16) -> Int
}
extension JPEGSampleReader {
    var scalarLayout: (view: ScalarSampleReader, rowStride: Int)? { nil }
    var nativeLayout: NativeUInt16Reader? { nil }
    func matchingPrefix(in range: Range<Int>, to value: UInt16) -> Int {
        scalarMatchingPrefix(self, in: range, to: value)
    }
}
private func scalarMatchingPrefix<R: JPEGSampleReader>(_ view: R, in range: Range<Int>, to value: UInt16) -> Int {
    var i = range.lowerBound
    while i + 4 <= range.upperBound && view.fourEqual(at: i, to: value) { i += 4 }
    while i < range.upperBound && view[i] == value { i += 1 }
    return i - range.lowerBound
}
protocol JPEGSampleWriter {
    var count: Int { get }
    var nativeLayout: NativeUInt16Writer? { get }
    subscript(index: Int) -> UInt16 { get nonmutating set }
    func fill(_ value: UInt16, range: Range<Int>)
}
extension JPEGSampleWriter {
    var nativeLayout: NativeUInt16Writer? { nil }
}
extension ScalarSampleReader: JPEGSampleReader {}
extension ScalarSampleWriter: JPEGSampleWriter {}

/// Synchronous component views map logical raster indices onto the caller's
/// actual plane, pixel and row strides. They never own or copy sample memory.
struct ComponentSampleReader: JPEGSampleReader {
    let bytes: UnsafeRawBufferPointer
    let width: Int, height: Int, offset: Int, rowBytes: Int, pixelStride: Int, sampleBytes: Int
    let littleEndian: Bool
    private let packedRows: Bool
    init(bytes: UnsafeRawBufferPointer, width: Int, height: Int, offset: Int,
         rowBytes: Int, pixelStride: Int, sampleBytes: Int, littleEndian: Bool) {
        self.bytes = bytes; self.width = width; self.height = height; self.offset = offset
        self.rowBytes = rowBytes; self.pixelStride = pixelStride
        self.sampleBytes = sampleBytes; self.littleEndian = littleEndian
        // Division avoids overflowing width * pixelStride for sparse layouts.
        self.packedRows = pixelStride > 0 && rowBytes / pixelStride == width && rowBytes % pixelStride == 0
    }
    @inline(__always)
    private func byteOffset(_ index: Int) -> Int {
        // Checked descriptor admission proves each nonnegative term and the
        // final sample end fit the borrowed buffer. Kernel row/range bounds
        // keep index inside that extent, so these operations cannot wrap.
        if packedRows { return offset &+ (index &* pixelStride) }
        return offset &+ ((index / width) &* rowBytes) &+ ((index % width) &* pixelStride)
    }
    var scalarLayout: (view: ScalarSampleReader, rowStride: Int)? {
        guard pixelStride == sampleBytes, rowBytes % sampleBytes == 0 else { return nil }
        return (ScalarSampleReader(bytes: .init(rebasing: bytes[offset...]),
            littleEndian: littleEndian, sampleBytes: sampleBytes), rowBytes / sampleBytes)
    }
    var count: Int { width * height }
    subscript(index: Int) -> UInt16 {
        let at = byteOffset(index)
        if sampleBytes == 1 { return UInt16(bytes[at]) }
        let value = bytes.loadUnaligned(fromByteOffset: at, as: UInt16.self)
        return littleEndian ? UInt16(littleEndian: value) : UInt16(bigEndian: value)
    }
    @inline(__always)
    func fourEqual(at index: Int, to value: UInt16) -> Bool {
        // The kernel proves all four samples are in the same logical row.
        if pixelStride == sampleBytes {
            let at = byteOffset(index)
            if sampleBytes == 1 {
                return bytes.loadUnaligned(fromByteOffset: at, as: UInt32.self)
                    == UInt32(UInt8(truncatingIfNeeded: value)) * 0x01010101
            }
            let ordered = littleEndian ? value.littleEndian : value.bigEndian
            return bytes.loadUnaligned(fromByteOffset: at, as: UInt64.self)
                == UInt64(ordered) * 0x0001000100010001
        }
        return self[index] == value && self[index + 1] == value && self[index + 2] == value && self[index + 3] == value
    }
    func matchingPrefix(in range: Range<Int>, to value: UInt16) -> Int {
        if pixelStride == sampleBytes {
            let at = byteOffset(range.lowerBound)
            let view = ScalarSampleReader(bytes: .init(rebasing: bytes[at...]),
                littleEndian: littleEndian, sampleBytes: sampleBytes)
            return view.matchingPrefix(in: 0..<range.count, to: value)
        }
        return scalarMatchingPrefix(self, in: range, to: value)
    }
    /// Reuse the bounded scalar precision check when samples are contiguous
    /// within each row. Odd byte strides and interleaved samples retain the
    /// general path; neither path reads row padding or creates sample storage.
    func validate(maximum: Int, checkpoint: () throws -> Void) throws {
        guard maximum < (sampleBytes == 1 ? 255 : 65535) else { return }
        if pixelStride == sampleBytes && rowBytes % sampleBytes == 0 {
            let view = ScalarSampleReader(bytes: .init(rebasing: bytes[offset...]),
                littleEndian: littleEndian, sampleBytes: sampleBytes)
            try view.validate(width: width, height: height, rowStride: rowBytes / sampleBytes,
                maximum: maximum, checkpoint: checkpoint)
            return
        }
        for index in 0..<count {
            if index & 255 == 0 { try checkpoint() }
            guard self[index] <= maximum else {
                throw CodecError(.invalidArgument, "Sample exceeds declared precision.")
            }
        }
    }
    func rows(_ rows: Range<Int>) -> Self {
        Self(bytes: bytes, width: width, height: rows.count, offset: offset + rows.lowerBound * rowBytes,
            rowBytes: rowBytes, pixelStride: pixelStride, sampleBytes: sampleBytes, littleEndian: littleEndian)
    }
}
struct ComponentSampleWriter: JPEGSampleWriter {
    let bytes: UnsafeMutableRawBufferPointer
    let width: Int, height: Int, offset: Int, rowBytes: Int, pixelStride: Int, sampleBytes: Int
    let littleEndian: Bool
    private let packedRows: Bool
    init(bytes: UnsafeMutableRawBufferPointer, width: Int, height: Int, offset: Int,
         rowBytes: Int, pixelStride: Int, sampleBytes: Int, littleEndian: Bool) {
        self.bytes = bytes; self.width = width; self.height = height; self.offset = offset
        self.rowBytes = rowBytes; self.pixelStride = pixelStride
        self.sampleBytes = sampleBytes; self.littleEndian = littleEndian
        // Division avoids overflowing width * pixelStride for sparse layouts.
        self.packedRows = pixelStride > 0 && rowBytes / pixelStride == width && rowBytes % pixelStride == 0
    }
    @inline(__always)
    private func byteOffset(_ index: Int) -> Int {
        // Checked descriptor admission proves each nonnegative term and the
        // final sample end fit the borrowed buffer. Kernel row/range bounds
        // keep index inside that extent, so these operations cannot wrap.
        if packedRows { return offset &+ (index &* pixelStride) }
        return offset &+ ((index / width) &* rowBytes) &+ ((index % width) &* pixelStride)
    }
    var count: Int { width * height }
    @inline(__always)
    subscript(index: Int) -> UInt16 {
        get {
            let at = byteOffset(index)
            if sampleBytes == 1 { return UInt16(bytes[at]) }
            let value = bytes.loadUnaligned(fromByteOffset: at, as: UInt16.self)
            return littleEndian ? UInt16(littleEndian: value) : UInt16(bigEndian: value)
        }
        nonmutating set {
            let at = byteOffset(index)
            if sampleBytes == 1 { bytes[at] = UInt8(truncatingIfNeeded: newValue) }
            else {
                bytes.storeBytes(of: littleEndian ? newValue.littleEndian : newValue.bigEndian,
                    toByteOffset: at, as: UInt16.self)
            }
        }
    }
    func fill(_ value: UInt16, range: Range<Int>) {
        if pixelStride == sampleBytes, !range.isEmpty,
           range.lowerBound / width == (range.upperBound - 1) / width {
            let start = byteOffset(range.lowerBound)
            let view = ScalarSampleWriter(bytes: .init(rebasing: bytes[start...]),
                littleEndian: littleEndian, sampleBytes: sampleBytes)
            view.fill(value, range: 0..<range.count)
            return
        }
        for index in range { self[index] = value }
    }
    func rows(_ rows: Range<Int>) -> Self {
        Self(bytes: bytes, width: width, height: rows.count, offset: offset + rows.lowerBound * rowBytes,
            rowBytes: rowBytes, pixelStride: pixelStride, sampleBytes: sampleBytes, littleEndian: littleEndian)
    }
}
