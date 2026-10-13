// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS

// Development-only bounded workload for ordinary-release allocator observation.
// Four fixed workers; each holds at most one frame transaction at a time.
struct Result: Codable, Sendable {
    let components: Int, near: Int, frames: Int, sourceBytes: Int
    let ownedPixelAllocations: Int, suppliedPixelAllocations: Int, reportedCopyBytes: Int
}
func require(_ condition: Bool) throws {
    if !condition { throw CodecError(.internalFailure, "Resource stress invariant failed") }
}
func worker(components: Int, near: Int) async throws -> Result {
    let width = 512, height = 512, frames = 8
    let size = width * height * components * 2
    let plane = try PlaneDescriptor(width: width, height: height, components: Array(0..<components),
        sampleStride: 2, pixelStride: components * 2, rowBytes: width * components * 2, byteCount: size)
    let descriptor = try ImageDescriptor(width: width, height: height, meaningfulBits: 12,
        components: components == 1 ? [.grey] : [.red, .green, .blue],
        colour: components == 1 ? .greyscale : .rgb, planes: [plane])
    let source = try ImageDestination.allocate(descriptor: descriptor).write { bytes in
        for i in 0..<(size / 2) {
            let sample = (i * 271 + (i / width) * 17) & 4095
            bytes[i * 2] = UInt8(truncatingIfNeeded: sample)
            bytes[i * 2 + 1] = UInt8(sample >> 8)
        }
    }
    let limits = try ResourceLimits(maximumCompressedBytes: 8 << 20, maximumDecodedBytes: 4 << 20,
        maximumWorkspaceBytes: 32 << 20, maximumWorkers: 1, maximumMemoryBytes: 64 << 20)
    let encoder = try Encoder(configuration: .init(mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
        codecOptions: .init(restartIntervalLines: 0, interleaveMode: components == 1 ? .none : .sample)))
    let decoder = try Decoder()
    var owned = 0, supplied = 0, copies = 0
    func check(_ image: Image) throws {
        // Decoder defaults to planar output; use descriptors to compare samples,
        // avoiding a full-frame conversion allocation in the observation harness.
        try image.storage.withUnsafeBytes { bytes in
            for p in image.descriptor.planes {
                for (slot, c) in p.components.enumerated() {
                    for y in 0..<height { for x in 0..<width {
                        let i = (y * width + x) * components + c
                        let expected = (i * 271 + (i / width) * 17) & 4095
                        let at = p.offset + y * p.rowBytes + x * p.pixelStride + slot * p.sampleStride
                        let actual = Int(bytes[at]) | Int(bytes[at + 1]) << 8
                        try require(abs(actual - expected) <= near)
                    } }
                }
            }
        }
    }
    for _ in 0..<frames {
        let encoded = try await encoder.encode(source, options: .init(resourceLimits: limits))
        let decoded = try await decoder.decode(encoded.data, options: .init(resourceLimits: limits))
        try check(decoded.image)
        owned += try decoded.report.pixelAllocationCount ?? { throw CodecError(.internalFailure, "Missing pixel allocation count") }()
        let destination = try ImageDestination.allocate(descriptor: decoded.image.descriptor)
        let into = try await decoder.decode(encoded.data, into: destination, options: .init(resourceLimits: limits))
        try require(into.image.storage.allocationID == destination.storage.allocationID)
        try check(into.image)
        supplied += try into.report.pixelAllocationCount ?? { throw CodecError(.internalFailure, "Missing pixel allocation count") }()
        copies += (encoded.report.copyEvents + decoded.report.copyEvents + into.report.copyEvents).reduce(0) { $0 + $1.bytesMoved }
    }
    try require(owned == frames && supplied == 0 && copies == 0)
    return Result(components: components, near: near, frames: frames, sourceBytes: size,
        ownedPixelAllocations: owned, suppliedPixelAllocations: supplied, reportedCopyBytes: copies)
}
let results = try await withThrowingTaskGroup(of: Result.self) { group in
    for components in [1, 3] { for near in [0, 3] {
        group.addTask { try await worker(components: components, near: near) }
    } }
    var results: [Result] = []
    for try await result in group { results.append(result) }
    return results.sorted { ($0.components, $0.near) < ($1.components, $1.near) }
}
let encoder = JSONEncoder(); encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
try FileHandle.standardOutput.write(contentsOf: encoder.encode(results))
