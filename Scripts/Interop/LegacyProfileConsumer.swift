// SPDX-License-Identifier: Apache-2.0
// Diagnostic only: link to the pinned predecessor JLSwift, never to SwiftJLS.
import Foundation
import JPEGLS

struct Failure: Error {}
let output = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
var records: [[String: Any]] = []
for bits in [2, 8, 12, 16] {
    let maximum = (1 << bits) - 1
    let red = [[0, maximum, maximum / 2, 1]]
    let green = [[maximum, 0, maximum / 4, maximum / 2]]
    let blue = [[maximum / 2, 1, maximum, 0]]
    let image = try MultiComponentImageData.rgb(redPixels: red, greenPixels: green, bluePixels: blue, bitsPerSample: bits)
    for transform: JPEGLSColorTransformation in [.hp1, .hp2, .hp3] {
        for mode: JPEGLSInterleaveMode in [.none, .line, .sample] {
        let name = "legacy-all-i\(mode.rawValue)-hp\(transform.rawValue)-p\(bits)"
        let encoded = try JPEGLSEncoder().encode(image, configuration: .init(interleaveMode: mode, colorTransformation: transform))
        let decoded = try JPEGLSDecoder().decode(encoded)
        guard decoded.components.map(\.pixels) == [red, green, blue] else { throw Failure() }
        try encoded.write(to: output.appendingPathComponent(name + ".jls"))
        var raw = Data()
        for x in 0..<4 { for plane in [red, green, blue] {
            let value = plane[0][x]
            raw.append(UInt8(value & 255))
            if bits > 8 { raw.append(UInt8(value >> 8)) }
        } }
        try raw.write(to: output.appendingPathComponent(name + ".raw"))
        records.append(["name": name, "bits": bits, "transform": transform.rawValue, "interleave": mode.rawValue, "predecessor_roundtrip": true])
        }
    }
}
try JSONSerialization.data(withJSONObject: records, options: [.prettyPrinted, .sortedKeys])
    .write(to: output.appendingPathComponent("cases.json"))
// Further pinned predecessor compatibility baselines.
for (width, height) in [(65537, 1), (1, 65537)] {
    let pixels = (0..<height).map { y in (0..<width).map { x in (x * 17 + y * 3) & 255 } }
    let image = try MultiComponentImageData.grayscale(pixels: pixels, bitsPerSample: 8)
    let encoded = try JPEGLSEncoder().encode(image, near: 0, interleaveMode: .none)
    guard try JPEGLSDecoder().decode(encoded).components[0].pixels == pixels else { throw Failure() }
    try encoded.write(to: output.appendingPathComponent("legacy-extended-\(width)x\(height).jls"))
}
for width in [1, 2] {
    let pixels = [[0, 1, 32764, 32765, 65535]]
    let table = try JPEGLSMappingTable(id: 7, entryWidth: width,
        entries: (0..<65536).map { ($0 * 271) & (width == 1 ? 255 : 65535) })
    let image = try MultiComponentImageData.grayscale(pixels: pixels, bitsPerSample: 16)
    let encoded = try JPEGLSEncoder().encode(image, configuration: .init(mappingTable: table))
    guard try JPEGLSDecoder().decode(encoded).components[0].pixels == pixels.map({ $0.map { table.map($0) } }) else { throw Failure() }
    try encoded.write(to: output.appendingPathComponent("legacy-mapping-w\(width).jls"))
}
if CommandLine.arguments.count > 2 {
    for near in [0, 3] {
        let url = URL(fileURLWithPath: CommandLine.arguments[2]).appendingPathComponent("subsampled-zero-n\(near).jls")
        let decoded = try JPEGLSDecoder().decode(Data(contentsOf: url))
        guard decoded.components.map({ $0.pixels.count }) == [19, 5, 10],
              decoded.components.map({ $0.pixels[0].count }) == [17, 17, 9],
              decoded.components.allSatisfy({ $0.pixels.allSatisfy({ $0.allSatisfy({ $0 == 0 }) }) }) else { throw Failure() }
    }
    print("Predecessor verified both subsampled zero-run fixtures")
}
