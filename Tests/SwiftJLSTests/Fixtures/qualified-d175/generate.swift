// SPDX-License-Identifier: Apache-2.0
// Compile with the exact JLSwift d175452 source files (see provenance.json).
import Foundation
let output = URL(fileURLWithPath: CommandLine.arguments[1], isDirectory: true)
for bits in [2,7,8] {
    let width = 17, height = 13, maximum = bits == 8 ? 100 : (1 << bits) - 1
    let pixels = (0..<height).map { y in (0..<width).map { x in
        (x * 29 + y * 17 + x * y * 3) % (maximum + 1)
    } }
    let image = try MultiComponentImageData.grayscale(pixels: pixels, bitsPerSample: bits)
    let preset = bits == 8 ? try JPEGLSPresetParameters(maxValue: 100, threshold1: 2, threshold2: 5, threshold3: 17, reset: 64) : nil
    var encoded = try JPEGLSEncoder().encode(image, configuration: .init(presetParameters: preset))
    let name = bits == 8 ? "p8-final-preset" : "p\(bits)-noise"
    if bits == 8 {
        guard let start = encoded.range(of: Data([255,248,0,13,1])) else { fatalError("Expected generated preset marker") }
        let range = start.lowerBound..<(start.lowerBound + 15)
        let segment = encoded.subdata(in: range)
        encoded.removeSubrange(range)
        encoded.insert(contentsOf: segment, at: encoded.count - 2)
    }
    let decoded = try JPEGLSDecoder().decode(encoded).components[0].pixels
    guard decoded == pixels else { fatalError("Predecessor round trip mismatch") }
    var expected = Data()
    for row in decoded { for sample in row {
        expected.append(UInt8(sample & 255)); expected.append(UInt8((sample >> 8) & 255))
    } }
    try encoded.write(to: output.appendingPathComponent(name + ".jls"))
    try expected.write(to: output.appendingPathComponent(name + ".u16le"))
    print("\(name) \(width)x\(height) jls=\(encoded.count) samples=\(width*height)")
}
// High-NEAR compatibility oracle: the predecessor's implicit threshold clamp
// differs from standard default thresholds even when precision is at least8.
do {
    let pixels = (0..<13).map { y in (0..<17).map { x in (x * 29 + y * 17 + x * y * 3) & 255 } }
    let image = try MultiComponentImageData.grayscale(pixels: pixels, bitsPerSample: 8)
    let encoded = try JPEGLSEncoder().encode(image, configuration: .init(near: 127))
    let decoded = try JPEGLSDecoder().decode(encoded).components[0].pixels
    var expected = Data()
    for (y, row) in decoded.enumerated() { for (x, sample) in row.enumerated() {
        guard abs(sample - pixels[y][x]) <= 127 else { fatalError("Predecessor NEAR bound") }
        expected.append(UInt8(sample & 255)); expected.append(UInt8((sample >> 8) & 255))
    } }
    try encoded.write(to: output.appendingPathComponent("p8-near127.jls"))
    try expected.write(to: output.appendingPathComponent("p8-near127.u16le"))
    print("p8-near127 17x13 jls=\(encoded.count) samples=221 NEAR=127")
}
