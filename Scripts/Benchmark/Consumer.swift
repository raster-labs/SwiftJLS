// SPDX-License-Identifier: Apache-2.0
import Foundation
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif
#if PREDECESSOR
import JPEGLS
#else
import SwiftJLS
#endif
struct Failure: Error {}
guard [8, 11].contains(CommandLine.arguments.count),
      let width = Int(CommandLine.arguments[1]), let height = Int(CommandLine.arguments[2]),
      let bits = Int(CommandLine.arguments[3]), let warmups = Int(CommandLine.arguments[5]),
      let iterations = Int(CommandLine.arguments[6]), width > 0, height > 0,
      (2...16).contains(bits), warmups >= 0, iterations > 0 else { throw Failure() }
let pattern = CommandLine.arguments[4], label = CommandLine.arguments[7]
let components = CommandLine.arguments.count == 11 ? Int(CommandLine.arguments[8]) ?? 0 : 1
let near = CommandLine.arguments.count == 11 ? Int(CommandLine.arguments[9]) ?? -1 : 0
let interleave = CommandLine.arguments.count == 11 ? Int(CommandLine.arguments[10]) ?? -1 : 0
guard [1, 3].contains(components), (0...255).contains(near), (0...2).contains(interleave),
      components > 1 || interleave == 0 else { throw Failure() }
let maximum = (1 << bits) - 1
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
#if PREDECESSOR
func plane(_ c: Int) -> [[Int]] { (0..<height).map { y in (0..<width).map { x in sample(x, y, c) } } }
let image = try components == 1
    ? MultiComponentImageData.grayscale(pixels: plane(0), bitsPerSample: bits)
    : MultiComponentImageData.rgb(redPixels: plane(0), greenPixels: plane(1), bluePixels: plane(2), bitsPerSample: bits)
guard let mode = JPEGLSInterleaveMode(rawValue: UInt8(interleave)) else { throw Failure() }
func encode() async throws -> Data { try JPEGLSEncoder().encode(image, configuration: .init(near: near, interleaveMode: mode)) }
func decode(_ data: Data, verify: Bool) async throws {
    let image = try JPEGLSDecoder().decode(data)
    guard image.frameHeader.bitsPerSample == bits else { throw Failure() }
    if verify {
        guard image.components.count == components else { throw Failure() }
        for c in 0..<components { for y in 0..<height { for x in 0..<width {
            guard abs(image.components[c].pixels[y][x] - sample(x, y, c)) <= near else { throw Failure() }
        } } }
    }
}
#else
let capacity = width * height * 2
let planes = try (0..<components).map { c in
    try PlaneDescriptor(width: width, height: height, components: [c], offset: c * capacity,
        rowBytes: width * 2, byteCount: (c + 1) * capacity)
}
let shape = try ImageDescriptor(width: width, height: height, meaningfulBits: bits,
    components: components == 1 ? [.grey] : [.red, .green, .blue],
    colour: components == 1 ? .greyscale : .rgb, planes: planes)
let image = try ImageDestination.allocate(descriptor: shape).write { bytes in
    for c in 0..<components { for y in 0..<height { for x in 0..<width {
        let at = c * capacity + (y * width + x) * 2, value = sample(x, y, c)
        bytes[at] = UInt8(truncatingIfNeeded: value); bytes[at + 1] = UInt8(value >> 8)
    } } }
}
guard let mode = CodecOptions.InterleaveMode(rawValue: UInt8(interleave)) else { throw Failure() }
func encode() async throws -> Data {
    try await Encoder(configuration: .init(mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
        codecOptions: .init(restartIntervalLines: 0, interleaveMode: mode))).encode(image, options: .init(executionPolicy: .scalarCPU)).data
}
func decode(_ data: Data, verify: Bool) async throws {
    let image = try await Decoder().decode(data, options: .init(executionPolicy: .scalarCPU)).image
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
#endif
if let path = ProcessInfo.processInfo.environment["SWIFTJLS_BENCHMARK_DECODE"] {
    try await decode(Data(contentsOf: URL(fileURLWithPath: path)), verify: true)
}
let reference = try await encode()
try await decode(reference, verify: true)
// Optional export is for a separate oracle experiment, never a timed benchmark.
if let path = ProcessInfo.processInfo.environment["SWIFTJLS_BENCHMARK_EXPORT"] {
    try reference.write(to: URL(fileURLWithPath: path))
}
for _ in 0..<warmups { _ = try await encode(); try await decode(reference, verify: false) }
var encoding: [Double] = [], decoding: [Double] = []
for _ in 0..<iterations {
    var start = ProcessInfo.processInfo.systemUptime
    let encoded = try await encode()
    encoding.append(ProcessInfo.processInfo.systemUptime - start)
    guard encoded == reference else { throw Failure() }
    start = ProcessInfo.processInfo.systemUptime
    try await decode(reference, verify: false)
    decoding.append(ProcessInfo.processInfo.systemUptime - start)
}
var usage = rusage()
#if canImport(Darwin)
getrusage(RUSAGE_SELF, &usage)
let peakRSS = usage.ru_maxrss
#else
getrusage(Int32(RUSAGE_SELF.rawValue), &usage)
let peakRSS = usage.ru_maxrss * 1024
#endif
let record: [String: Any] = ["label": label, "width": width, "height": height, "bits": bits,
    "pattern": pattern, "warmups": warmups, "iterations": iterations,
    "components": components, "near": near, "interleave": interleave,
    "encode_seconds": encoding, "decode_seconds": decoding,
    "encoded_bytes": reference.count, "peak_process_rss_bytes": peakRSS,
    "pixel_allocations": NSNull(), "copy_bytes": NSNull(), "workspace_peak_bytes": NSNull()]
let result = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
print(String(decoding: result, as: UTF8.self))
