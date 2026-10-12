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
guard CommandLine.arguments.count == 8,
      let width = Int(CommandLine.arguments[1]), let height = Int(CommandLine.arguments[2]),
      let bits = Int(CommandLine.arguments[3]), let warmups = Int(CommandLine.arguments[5]),
      let iterations = Int(CommandLine.arguments[6]), width > 0, height > 0,
      (2...16).contains(bits), warmups >= 0, iterations > 0 else { throw Failure() }
let pattern = CommandLine.arguments[4], label = CommandLine.arguments[7]
let maximum = (1 << bits) - 1
func sample(_ x: Int, _ y: Int) -> Int {
    switch pattern {
    case "flat": return maximum / 2
    case "ramp": return (x * 13 + y * 17) & maximum
    default:
        let index = UInt64(y * width + x)
        var z = index &+ 0x9e3779b97f4a7c15
        z = (z ^ (z >> 30)) &* 0xbf58476d1ce4e5b9
        z = (z ^ (z >> 27)) &* 0x94d049bb133111eb
        return Int((z ^ (z >> 31)) & UInt64(maximum))
    }
}
#if PREDECESSOR
let image = try MultiComponentImageData.grayscale(
    pixels: (0..<height).map { y in (0..<width).map { x in sample(x, y) } }, bitsPerSample: bits)
func encode() async throws -> Data { try JPEGLSEncoder().encode(image, configuration: .init()) }
func decode(_ data: Data, verify: Bool) async throws {
    let image = try JPEGLSDecoder().decode(data)
    guard image.frameHeader.bitsPerSample == bits else { throw Failure() }
    if verify {
        for y in 0..<height { for x in 0..<width {
            guard image.components[0].pixels[y][x] == sample(x, y) else { throw Failure() }
        } }
    }
}
#else
let shape = try ImageDescriptor.greyscale16(width: width, height: height, meaningfulBits: bits)
let image = try ImageDestination.allocate(descriptor: shape).writeUInt16 { x, y in UInt16(sample(x, y)) }
func encode() async throws -> Data { try await Encoder().encode(image, options: .init(executionPolicy: .scalarCPU)).data }
func decode(_ data: Data, verify: Bool) async throws {
    let image = try await Decoder().decode(data, options: .init(executionPolicy: .scalarCPU)).image
    guard image.descriptor.meaningfulBits == bits else { throw Failure() }
    if verify {
        try image.storage.withUnsafeBytes { bytes in
            for y in 0..<height { for x in 0..<width {
                let i = (y * width + x) * 2
                guard Int(bytes[i]) | Int(bytes[i + 1]) << 8 == sample(x, y) else { throw Failure() }
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
    "encode_seconds": encoding, "decode_seconds": decoding,
    "encoded_bytes": reference.count, "peak_process_rss_bytes": peakRSS,
    "pixel_allocations": NSNull(), "copy_bytes": NSNull(), "workspace_peak_bytes": NSNull()]
let result = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
print(String(decoding: result, as: UTF8.self))
