// SPDX-License-Identifier: Apache-2.0
// Separate same-process diagnostic. Original public-call wrappers retain their
// async signatures and timing boundaries; no extra adapter function is inserted.
import Foundation
import Darwin
import struct JPEGLS.MultiComponentImageData
import struct JPEGLS.JPEGLSEncoder
import struct JPEGLS.JPEGLSDecoder
import enum JPEGLS.JPEGLSInterleaveMode
import SwiftJLS
struct Failure: Error {}

guard CommandLine.arguments.count == 8,
      let width = Int(CommandLine.arguments[1]), let height = Int(CommandLine.arguments[2]),
      let bits = Int(CommandLine.arguments[3]), let warmups = Int(CommandLine.arguments[5]),
      let iterations = Int(CommandLine.arguments[6]), width == 37, height == 23,
      [12, 16].contains(bits), warmups >= 0, iterations > 0 else { throw Failure() }
let pattern = CommandLine.arguments[4], label = CommandLine.arguments[7]
guard pattern == "flat" else { throw Failure() }
let components = CommandLine.arguments.count == 11 ? Int(CommandLine.arguments[8]) ?? 0 : 1
let near = CommandLine.arguments.count == 11 ? Int(CommandLine.arguments[9]) ?? -1 : 0
let interleave = CommandLine.arguments.count == 11 ? Int(CommandLine.arguments[10]) ?? -1 : 0
guard [1, 3].contains(components), (0...255).contains(near), (0...2).contains(interleave),
      components > 1 || interleave == 0 else { throw Failure() }
let maximum = (1 << bits) - 1
let endToEnd = ProcessInfo.processInfo.environment["SWIFTJLS_BENCHMARK_END_TO_END"] == "1"
guard endToEnd else { throw Failure() }
let predecessorFirst = ProcessInfo.processInfo.environment["SWIFTJLS_SAME_PROCESS_FIRST"] != "successor"
func sample(_ x: Int, _ y: Int, _ component: Int = 0) -> Int {
    switch pattern {
    case "flat": return (maximum / 2 + component * 17) & maximum
    case "ramp": return (x * 13 + y * 17 + component * 31) & maximum
    default:
        let index = UInt64((component * height + y) * width + x)
        var z = index &+ 0x9e3779b97f4a7c15
        z = (z ^ (z >> 30)) &* 0xbf58476d1ce4e5b9
        z = (z ^ (z >> 27)) &* 0x94d049bb133111eb
        return Int((z ^ (z >> 31)) & UInt64(maximum))
    }
}
// The same canonical UInt16 samples feed both public APIs. Fixture generation
// is outside timing; preparation includes each API's allocation/conversion and
// input validation. This extra caller buffer is included in process RSS.
let canonical: [UInt16] = endToEnd ? (0..<(components * height * width)).map { i in
    UInt16(sample(i % width, (i / width) % height, i / (width * height)))
} : []
func inputSample(_ x: Int, _ y: Int, _ c: Int) -> Int {
    endToEnd ? Int(canonical[(c * height + y) * width + x]) : sample(x, y, c)
}

func makePredecessorImage() throws -> MultiComponentImageData {
    func plane(_ c: Int) -> [[Int]] { (0..<height).map { y in (0..<width).map { x in inputSample(x, y, c) } } }
    return try components == 1
        ? MultiComponentImageData.grayscale(pixels: plane(0), bitsPerSample: bits)
        : MultiComponentImageData.rgb(redPixels: plane(0), greenPixels: plane(1), bluePixels: plane(2), bitsPerSample: bits)
}
guard let predecessorMode = JPEGLSInterleaveMode(rawValue: UInt8(interleave)) else { throw Failure() }
func encodePredecessor(_ image: MultiComponentImageData) async throws -> Data { try JPEGLSEncoder().encode(image, configuration: .init(near: near, interleaveMode: predecessorMode)) }
func decodePredecessor(_ data: Data, verify: Bool) async throws {
    let image = try JPEGLSDecoder().decode(data)
    guard image.frameHeader.bitsPerSample == bits else { throw Failure() }
    if verify {
        guard image.components.count == components else { throw Failure() }
        for c in 0..<components { for y in 0..<height { for x in 0..<width {
            guard abs(image.components[c].pixels[y][x] - sample(x, y, c)) <= near else { throw Failure() }
        } } }
    }
}

// The largest RGB fixture's conservative admission exceeds the general
// workspace ceiling. This development profile is explicit and host-bounded;
// production defaults and all precision/cancellation checks are unchanged.
let benchmarkLimits = try SwiftJLS.ResourceLimits(maximumWorkspaceBytes: 1024 * 1024 * 1024,
    maximumMemoryBytes: 2 * 1024 * 1024 * 1024)
func makeSuccessorImage() throws -> SwiftJLS.Image {
    let capacity = width * height * 2
    let planes = try (0..<components).map { c in
        try SwiftJLS.PlaneDescriptor(width: width, height: height, components: [c], offset: c * capacity,
            rowBytes: width * 2, byteCount: (c + 1) * capacity)
    }
    let shape = try SwiftJLS.ImageDescriptor(width: width, height: height, meaningfulBits: bits,
        components: components == 1 ? [.grey] : [.red, .green, .blue],
        colour: components == 1 ? .greyscale : .rgb, planes: planes)
    return try SwiftJLS.ImageDestination.allocate(descriptor: shape).write { bytes in
        for c in 0..<components { for y in 0..<height { for x in 0..<width {
            let at = c * capacity + (y * width + x) * 2, value = inputSample(x, y, c)
            bytes[at] = UInt8(truncatingIfNeeded: value); bytes[at + 1] = UInt8(value >> 8)
        } } }
    }
}
guard let successorMode = SwiftJLS.CodecOptions.InterleaveMode(rawValue: UInt8(interleave)) else { throw Failure() }
func encodeSuccessor(_ image: SwiftJLS.Image) async throws -> Data {
    try await SwiftJLS.Encoder(configuration: .init(mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
        codecOptions: .init(restartIntervalLines: 0, interleaveMode: successorMode))).encode(image, options: .init(resourceLimits: benchmarkLimits, executionPolicy: .scalarCPU)).data
}
func decodeSuccessor(_ data: Data, verify: Bool) async throws {
    let image = try await SwiftJLS.Decoder().decode(data, options: .init(resourceLimits: benchmarkLimits, executionPolicy: .scalarCPU)).image
    guard image.descriptor.meaningfulBits == bits else { throw Failure() }
    if verify {
        try image.storage.withUnsafeBytes { bytes in
            guard image.descriptor.components.count == components else { throw Failure() }
            for p in image.descriptor.planes { for (slot, c) in p.components.enumerated() {
                for y in 0..<height { for x in 0..<width {
                    let i = p.offset + y * p.rowBytes + x * p.pixelStride + slot * p.sampleStride
                    let actual = Int(bytes[i]) | Int(bytes[i + 1]) << 8
                    guard abs(actual - sample(x, y, c)) <= near else { throw Failure() }
                } }
            } }
        }
    }
}

let predecessorImage = try makePredecessorImage()
let successorImage = try makeSuccessorImage()
let predecessorReference = try await encodePredecessor(predecessorImage)
let successorReference = try await encodeSuccessor(successorImage)
try await decodePredecessor(predecessorReference, verify: true)
try await decodeSuccessor(successorReference, verify: true)
// Cross-decoding is untimed and verifies the same canonical pixels.
try await decodePredecessor(successorReference, verify: true)
try await decodeSuccessor(predecessorReference, verify: true)
for observation in 0..<warmups {
    let order = (observation % 2 == 0) == predecessorFirst ? [0, 1] : [1, 0]
    for producer in order {
        if producer == 0 {
            _ = try await encodePredecessor(predecessorImage)
            try await decodePredecessor(predecessorReference, verify: false)
            _ = try await encodePredecessor(makePredecessorImage())
        } else {
            _ = try await encodeSuccessor(successorImage)
            try await decodeSuccessor(successorReference, verify: false)
            _ = try await encodeSuccessor(makeSuccessorImage())
        }
    }
}
var predecessorEncoding: [Double] = [], predecessorDecoding: [Double] = []
var predecessorPreparation: [Double] = [], predecessorPreparedEncoding: [Double] = []
var successorEncoding: [Double] = [], successorDecoding: [Double] = []
var successorPreparation: [Double] = [], successorPreparedEncoding: [Double] = []
for observation in 0..<iterations {
    let order = (observation % 2 == 0) == predecessorFirst ? [0, 1] : [1, 0]
    for producer in order {
        if producer == 0 {
            var start = ProcessInfo.processInfo.systemUptime
            let encoded = try await encodePredecessor(predecessorImage)
            predecessorEncoding.append(ProcessInfo.processInfo.systemUptime - start)
            guard encoded == predecessorReference else { throw Failure() }
            start = ProcessInfo.processInfo.systemUptime
            try await decodePredecessor(predecessorReference, verify: false)
            predecessorDecoding.append(ProcessInfo.processInfo.systemUptime - start)
            let preparationStart = ProcessInfo.processInfo.systemUptime
            let fresh = try makePredecessorImage()
            let prepared = ProcessInfo.processInfo.systemUptime
            let freshEncoded = try await encodePredecessor(fresh)
            let finished = ProcessInfo.processInfo.systemUptime
            predecessorPreparation.append(prepared - preparationStart)
            predecessorPreparedEncoding.append(finished - preparationStart)
            guard freshEncoded == predecessorReference else { throw Failure() }
        }
        else {
            var start = ProcessInfo.processInfo.systemUptime
            let encoded = try await encodeSuccessor(successorImage)
            successorEncoding.append(ProcessInfo.processInfo.systemUptime - start)
            guard encoded == successorReference else { throw Failure() }
            start = ProcessInfo.processInfo.systemUptime
            try await decodeSuccessor(successorReference, verify: false)
            successorDecoding.append(ProcessInfo.processInfo.systemUptime - start)
            let preparationStart = ProcessInfo.processInfo.systemUptime
            let fresh = try makeSuccessorImage()
            let prepared = ProcessInfo.processInfo.systemUptime
            let freshEncoded = try await encodeSuccessor(fresh)
            let finished = ProcessInfo.processInfo.systemUptime
            successorPreparation.append(prepared - preparationStart)
            successorPreparedEncoding.append(finished - preparationStart)
            guard freshEncoded == successorReference else { throw Failure() }
        }
    }
}
var usage = rusage()
getrusage(RUSAGE_SELF, &usage)
let record: [String: Any] = [
    "label": label, "width": width, "height": height, "bits": bits,
    "pattern": pattern, "warmups": warmups, "iterations": iterations,
    "components": components, "near": near, "interleave": interleave,
    "end_to_end": endToEnd, "first_producer": predecessorFirst ? "predecessor" : "successor",
    "resource_profile": "successor-workspace-1GiB-memory-2GiB-v1",
    "order": "Alternates first producer per observation, same order for warmups.",
    "predecessor": ["encode_seconds": predecessorEncoding, "decode_seconds": predecessorDecoding,
        "prepare_seconds": predecessorPreparation, "prepare_encode_seconds": predecessorPreparedEncoding,
        "encoded_bytes": predecessorReference.count],
    "successor": ["encode_seconds": successorEncoding, "decode_seconds": successorDecoding,
        "prepare_seconds": successorPreparation, "prepare_encode_seconds": successorPreparedEncoding,
        "encoded_bytes": successorReference.count],
    "combined_process_peak_rss_bytes": usage.ru_maxrss,
    "rss_scope": "Combined process only; does not provide per-producer workspace/RSS."
]
let result = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
print(String(decoding: result, as: UTF8.self))
