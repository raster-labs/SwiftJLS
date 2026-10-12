// SPDX-License-Identifier: Apache-2.0
// Diagnostic only: link to the pinned predecessor JLSwift, never to SwiftJLS.
import Foundation
import JPEGLS

struct Failure: Error {}
let output = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
var records: [[String: Any]] = []
for bits in [8, 16] {
    let maximum = (1 << bits) - 1
    let red = [[0, maximum, maximum / 2, 1]]
    let green = [[maximum, 0, maximum / 4, maximum / 2]]
    let blue = [[maximum / 2, 1, maximum, 0]]
    let image = try MultiComponentImageData.rgb(redPixels: red, greenPixels: green, bluePixels: blue, bitsPerSample: bits)
    for transform: JPEGLSColorTransformation in [.hp1, .hp2, .hp3] {
        let name = "legacy-hp\(transform.rawValue)-p\(bits)"
        let encoded = try JPEGLSEncoder().encode(image, configuration: .init(interleaveMode: .sample, colorTransformation: transform))
        let decoded = try JPEGLSDecoder().decode(encoded)
        guard decoded.components.map(\.pixels) == [red, green, blue] else { throw Failure() }
        try encoded.write(to: output.appendingPathComponent(name + ".jls"))
        var raw = Data()
        for x in 0..<4 { for plane in [red, green, blue] {
            let value = plane[0][x]
            raw.append(UInt8(value & 255))
            if bits == 16 { raw.append(UInt8(value >> 8)) }
        } }
        try raw.write(to: output.appendingPathComponent(name + ".raw"))
        records.append(["name": name, "bits": bits, "transform": transform.rawValue, "predecessor_roundtrip": true])
    }
}
try JSONSerialization.data(withJSONObject: records, options: [.prettyPrinted, .sortedKeys])
    .write(to: output.appendingPathComponent("cases.json"))
