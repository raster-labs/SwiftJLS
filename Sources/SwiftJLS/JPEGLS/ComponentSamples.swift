// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

protocol JPEGSampleReader {
    var count: Int { get }
    subscript(index: Int) -> UInt16 { get }
    func fourEqual(at index: Int, to value: UInt16) -> Bool
}
protocol JPEGSampleWriter {
    var count: Int { get }
    subscript(index: Int) -> UInt16 { get nonmutating set }
    func fill(_ value: UInt16, range: Range<Int>)
}
extension ScalarSampleReader: JPEGSampleReader {}
extension ScalarSampleWriter: JPEGSampleWriter {}

/// Synchronous component views map logical raster indices onto the caller's
/// actual plane, pixel and row strides. They never own or copy sample memory.
struct ComponentSampleReader: JPEGSampleReader {
    let bytes: UnsafeRawBufferPointer
    let width: Int, height: Int, offset: Int, rowBytes: Int, pixelStride: Int, sampleBytes: Int
    let littleEndian: Bool
    var count: Int { width * height }
    subscript(index: Int) -> UInt16 {
        let at = offset + (index / width) * rowBytes + (index % width) * pixelStride
        if sampleBytes == 1 { return UInt16(bytes[at]) }
        let value = bytes.loadUnaligned(fromByteOffset: at, as: UInt16.self)
        return littleEndian ? UInt16(littleEndian: value) : UInt16(bigEndian: value)
    }
    func fourEqual(at index: Int, to value: UInt16) -> Bool {
        self[index] == value && self[index + 1] == value && self[index + 2] == value && self[index + 3] == value
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
    var count: Int { width * height }
    subscript(index: Int) -> UInt16 {
        get {
            let at = offset + (index / width) * rowBytes + (index % width) * pixelStride
            if sampleBytes == 1 { return UInt16(bytes[at]) }
            let value = bytes.loadUnaligned(fromByteOffset: at, as: UInt16.self)
            return littleEndian ? UInt16(littleEndian: value) : UInt16(bigEndian: value)
        }
        nonmutating set {
            let at = offset + (index / width) * rowBytes + (index % width) * pixelStride
            if sampleBytes == 1 { bytes[at] = UInt8(truncatingIfNeeded: newValue) }
            else {
                bytes.storeBytes(of: littleEndian ? newValue.littleEndian : newValue.bigEndian,
                    toByteOffset: at, as: UInt16.self)
            }
        }
    }
    func fill(_ value: UInt16, range: Range<Int>) {
        for index in range { self[index] = value }
    }
    func rows(_ rows: Range<Int>) -> Self {
        Self(bytes: bytes, width: width, height: rows.count, offset: offset + rows.lowerBound * rowBytes,
            rowBytes: rowBytes, pixelStride: pixelStride, sampleBytes: sampleBytes, littleEndian: littleEndian)
    }
}
