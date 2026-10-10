import Foundation
import SwiftJLS
struct Fixture: Decodable { let name: String; let width: Int; let height: Int; let meaningfulBits: Int; let near: Int? }
struct Manifest: Decodable { let cases: [Fixture] }
let directory = URL(fileURLWithPath: CommandLine.arguments[1])
let output = URL(fileURLWithPath: CommandLine.arguments[2])
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: directory.appendingPathComponent("manifest.json")))
for f in manifest.cases {
    let raw = try Data(contentsOf: directory.appendingPathComponent(f.name + ".u16le"))
    let shape = try ImageDescriptor.greyscale16(width: f.width, height: f.height, meaningfulBits: f.meaningfulBits, rowBytes: f.width * 2 + 6)
    let image = try ImageDestination.allocate(descriptor: shape).writeUInt16 { x, y in
        let index = (y * f.width + x) * 2
        return UInt16(raw[index]) | UInt16(raw[index + 1]) << 8
    }
    let mode: CompressionMode = (f.near ?? 0) == 0 ? .lossless : .nearLossless(maximumAbsoluteError: f.near ?? 0)
    let encoded = try await Encoder(configuration: .init(mode: mode)).encode(image)
    try encoded.data.write(to: output.appendingPathComponent(f.name + ".jls"))
}
print("Wrote \(manifest.cases.count) SwiftJLS outputs for independent decoding.")
