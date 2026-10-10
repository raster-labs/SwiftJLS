// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization
import SwiftJ2K
import SwiftJLS

// The adapters retain an immutable owner. Only descriptors and small wrappers
// are constructed; raw pointers are forwarded synchronously and never stored.
final class IntoJLS: SwiftJLS.ReadOnlyImageStorage {
    init(owner: any SwiftJ2K.ReadOnlyImageStorage, cancelOnRead: Int? = nil) {
        self.owner = owner; self.cancelOnRead = cancelOnRead
    }
    let cancelOnRead: Int?
    let owner: any SwiftJ2K.ReadOnlyImageStorage
    let reads: Mutex<Int> = Mutex(0)
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R {
        let ordinal = reads.withLock { $0 += 1; return $0 }
        return try owner.withUnsafeBytes { bytes in
            if ordinal == cancelOnRead { withUnsafeCurrentTask { $0?.cancel() } }
            return try body(bytes)
        }
    }
}
struct IntoJ2K: SwiftJ2K.ReadOnlyImageStorage {
    let owner: any SwiftJLS.ReadOnlyImageStorage
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R {
        try owner.withUnsafeBytes(body)
    }
}

// Instrument the caller-owned destination and initialise padding before the
// decoder runs. The underlying provider remains the lifecycle authority.
final class J2KDestinationStorage: SwiftJ2K.WritableImageStorage {
    let owner: SwiftJ2K.OwnedImageStorage
    let writes = Mutex(0)
    let cancelOnBorrow: Bool
    init(byteCount: Int, cancelOnBorrow: Bool = false) throws {
        owner = try .init(byteCount: byteCount)
        self.cancelOnBorrow = cancelOnBorrow
    }
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    func reserveWrite() throws -> SwiftJ2K.StorageWriteLease { try owner.reserveWrite() }
    func withUnsafeMutableBytes<R>(lease: SwiftJ2K.StorageWriteLease,
        _ body: (UnsafeMutableRawBufferPointer) throws -> R) throws -> R {
        try owner.withUnsafeMutableBytes(lease: lease) { bytes in
            writes.withLock { $0 += 1 }
            bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
            if cancelOnBorrow { withUnsafeCurrentTask { $0?.cancel() } }
            return try body(bytes)
        }
    }
    func finishAndSeal(lease: SwiftJ2K.StorageWriteLease) throws -> any SwiftJ2K.ReadOnlyImageStorage {
        try owner.finishAndSeal(lease: lease)
    }
    func abortAndInvalidate(lease: SwiftJ2K.StorageWriteLease) throws { try owner.abortAndInvalidate(lease: lease) }
}

// Instrument the caller-owned destination and initialise padding before the
// decoder runs. The underlying provider remains the lifecycle authority.
final class JLSDestinationStorage: SwiftJLS.WritableImageStorage {
    let owner: SwiftJLS.OwnedImageStorage
    let writes = Mutex(0)
    let cancelOnBorrow: Bool
    init(byteCount: Int, cancelOnBorrow: Bool = false) throws {
        owner = try .init(byteCount: byteCount)
        self.cancelOnBorrow = cancelOnBorrow
    }
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    func reserveWrite() throws -> SwiftJLS.StorageWriteLease { try owner.reserveWrite() }
    func withUnsafeMutableBytes<R>(lease: SwiftJLS.StorageWriteLease,
        _ body: (UnsafeMutableRawBufferPointer) throws -> R) throws -> R {
        try owner.withUnsafeMutableBytes(lease: lease) { bytes in
            writes.withLock { $0 += 1 }
            bytes.initializeMemory(as: UInt8.self, repeating: 0xa5)
            if cancelOnBorrow { withUnsafeCurrentTask { $0?.cancel() } }
            return try body(bytes)
        }
    }
    func finishAndSeal(lease: SwiftJLS.StorageWriteLease) throws -> any SwiftJLS.ReadOnlyImageStorage {
        try owner.finishAndSeal(lease: lease)
    }
    func abortAndInvalidate(lease: SwiftJLS.StorageWriteLease) throws { try owner.abortAndInvalidate(lease: lease) }
}
struct CheckFailure: Error { let message: String }
func check(_ value: Bool, _ message: String) throws {
    if !value { throw CheckFailure(message: message) }
}
func sample(_ x: Int, _ y: Int, bits: Int) -> UInt16 {
    UInt16(((x * 1733) ^ (y * 7919) ^ ((x + y) * 31)) & ((1 << bits) - 1))
}
let width = 37, height = 23
var results: [[String: Int]] = []
for bits in [12, 16] {
    // strace evidence delimits API work from optional exported validation files.
    try FileHandle.standardError.write(contentsOf: Data("STORAGE_BEGIN_\(bits)\n".utf8))
    let j2kShape = try SwiftJ2K.ImageDescriptor.greyscale16(width: width, height: height,
        meaningfulBits: bits, rowBytes: width * 2 + 14, offset: 2)
    let original = try SwiftJ2K.ImageDestination.allocate(descriptor: j2kShape)
        .writeUInt16 { x, y in sample(x, y, bits: bits) }
    let j2k = try await SwiftJ2K.Encoder().encode(original)
    let j2kProvider = try J2KDestinationStorage(byteCount: j2kShape.requiredByteCount)
    let j2kDestination = try SwiftJ2K.ImageDestination(descriptor: j2kShape, storage: j2kProvider)
    let firstID = j2kDestination.storage.allocationID
    let first = try await SwiftJ2K.Decoder().decode(j2k.data, into: j2kDestination)
    try check(first.image.storage.allocationID == firstID, "J2K decode changed allocation")
    let jlsShape = try SwiftJLS.ImageDescriptor.greyscale16(width: width, height: height,
        meaningfulBits: bits, rowBytes: width * 2 + 14, offset: 2)
    let bridge = IntoJLS(owner: first.image.storage)
    let shared = try SwiftJLS.Image(descriptor: jlsShape, storage: bridge)
    try check(shared.storage.allocationID == firstID, "J2K to JLS adapter copied storage")
    async let one = SwiftJLS.Encoder().encode(shared)
    async let two = SwiftJLS.Encoder().encode(shared)
    let (jls, concurrent) = try await (one, two)
    try check(jls.data == concurrent.data, "Concurrent reader codestreams differ")
    // Different padding must leave the entire encoded stream unchanged.
    let packed = try SwiftJLS.ImageDestination.allocate(descriptor: .greyscale16(
        width: width, height: height, meaningfulBits: bits)).writeUInt16 { x, y in sample(x, y, bits: bits) }
    let packedEncoded = try await SwiftJLS.Encoder().encode(packed)
    try check(jls.data == packedEncoded.data, "Input padding affected codestream")
    let secondShape = try SwiftJLS.ImageDescriptor.greyscale16(width: width, height: height,
        meaningfulBits: bits, rowBytes: width * 2 + 22, offset: 4)
    let jlsProvider = try JLSDestinationStorage(byteCount: secondShape.requiredByteCount)
    let jlsDestination = try SwiftJLS.ImageDestination(descriptor: secondShape, storage: jlsProvider)
    let secondID = jlsDestination.storage.allocationID
    let second = try await SwiftJLS.Decoder().decode(jls.data, into: jlsDestination)
    try check(second.image.storage.allocationID == secondID, "JLS decode changed allocation")
    let reverseShape = try SwiftJ2K.ImageDescriptor.greyscale16(width: width, height: height,
        meaningfulBits: bits, rowBytes: width * 2 + 22, offset: 4)
    let reverse = try SwiftJ2K.Image(descriptor: reverseShape, storage: IntoJ2K(owner: second.image.storage))
    try check(reverse.storage.allocationID == secondID, "JLS to J2K adapter copied storage")
    let reverseEncoded = try await SwiftJ2K.Encoder().encode(reverse)
    try check(reverseEncoded.data == j2k.data, "Reverse shared encode differs from original J2K")
    let final = try await SwiftJ2K.Decoder().decode(reverseEncoded.data)
    for y in 0..<height { for x in 0..<width {
        let expected = sample(x, y, bits: bits)
        try check(try first.image.sampleUInt16(x: x, y: y) == expected, "J2K sample mismatch")
        try check(try second.image.sampleUInt16(x: x, y: y) == expected, "JLS sample mismatch")
        try check(try final.image.sampleUInt16(x: x, y: y) == expected, "Reverse sample mismatch")
    } }
    try check(first.report.pixelAllocationCount == 0 && second.report.pixelAllocationCount == 0,
              "Caller-destination decode reported an extra pixel allocation")
    try check(jls.report.pixelAllocationCount == 0 && jls.report.copyEvents.isEmpty &&
              reverseEncoded.report.pixelAllocationCount == 0 && reverseEncoded.report.copyEvents.isEmpty,
              "Shared encode reported a pixel allocation or copy")
    try check(j2kProvider.writes.withLock { $0 } == 1 && jlsProvider.writes.withLock { $0 } == 1,
              "Decode did not use exactly one caller-storage write")
    try check(bridge.reads.withLock { $0 } >= 3, "Adapter reads were not observed")
    func padding(_ bytes: UnsafeRawBufferPointer, offset: Int, row: Int) throws {
        for index in 0..<bytes.count {
            let relative = index - offset
            if relative < 0 || relative % row >= width * 2 {
                try check(bytes[index] == 0xa5, "Decode overwrote sentinel padding")
            }
        }
    }
    try first.image.storage.withUnsafeBytes { try padding($0, offset: 2, row: width * 2 + 14) }
    try second.image.storage.withUnsafeBytes { try padding($0, offset: 4, row: width * 2 + 22) }
    do {
        _ = try jlsProvider.reserveWrite()
        throw CheckFailure(message: "Sealed destination accepted another writer")
    } catch is SwiftJLS.CodecError { }
    // Cancellation at the provider boundary happens after admission. The
    // destination must become unusable and no decoded image may be published.
    let cancelledProvider = try JLSDestinationStorage(byteCount: secondShape.requiredByteCount, cancelOnBorrow: true)
    let cancelledDestination = try SwiftJLS.ImageDestination(descriptor: secondShape, storage: cancelledProvider)
    let cancellation = Task {
        try await SwiftJLS.Decoder().decode(jls.data, into: cancelledDestination)
    }
    do {
        _ = try await cancellation.value
        throw CheckFailure(message: "Cancelled decode published an image")
    } catch is CancellationError { }
    do {
        _ = try cancelledProvider.reserveWrite()
        throw CheckFailure(message: "Cancelled destination was reusable")
    } catch is SwiftJLS.CodecError { }
    // Cancel after encode admission, inside the actual owner borrow. Constructing
    // Image performs read 1; the encoder's sample borrow is read 2.
    let encodeCancelledBridge = IntoJLS(owner: first.image.storage, cancelOnRead: 2)
    let encodeCancelledImage = try SwiftJLS.Image(descriptor: jlsShape, storage: encodeCancelledBridge)
    let encodeCancellation = Task { try await SwiftJLS.Encoder().encode(encodeCancelledImage) }
    do {
        _ = try await encodeCancellation.value
        throw CheckFailure(message: "Cancelled encode published a codestream")
    } catch is CancellationError { }
    // Compatible allowCopy must remain direct; the option is not permission to
    // insert an unnecessary frame conversion.
    let allowed = try await SwiftJLS.Encoder().encode(shared, options: .init(copyPolicy: .allowCopy))
    try check(allowed.data == jls.data && allowed.report.copyEvents.isEmpty,
              "Compatible allowCopy changed shared coding")
    try FileHandle.standardError.write(contentsOf: Data("STORAGE_END_\(bits)\n".utf8))
    // Optional output is validation material written only after both in-memory
    // routes finish. No intermediate file participates in the codec hand-off.
    if CommandLine.arguments.count == 2 {
        let directory = URL(fileURLWithPath: CommandLine.arguments[1])
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try j2k.data.write(to: directory.appendingPathComponent("pair-p\(bits).j2k"))
        try jls.data.write(to: directory.appendingPathComponent("pair-p\(bits).jls"))
    }
    results.append(["bits": bits, "width": width, "height": height,
                    "samplesChecked": width * height * 3, "j2kBytes": j2k.data.count, "jlsBytes": jls.data.count])
}
let report = try JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted, .sortedKeys])
print(String(decoding: report, as: UTF8.self))
