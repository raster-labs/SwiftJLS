// SPDX-License-Identifier: Apache-2.0
// Compile as an independent executable depending only on SwiftJLS.
import Foundation
import SwiftJLS
struct Fixture: Decodable { let name: String, width: Int, height: Int, meaningfulBits: Int, near: Int, components: Int, interleave: Int }
struct Manifest: Decodable { let cases: [Fixture] }
let root = URL(fileURLWithPath: CommandLine.arguments[1])
let manifest = try JSONDecoder().decode(Manifest.self, from: Data(contentsOf: root.appendingPathComponent("components.json")))
var candidates: [[String: Any]] = []
for f in manifest.cases where f.components == 2 && f.interleave == 0 {
    let samples = try Data(contentsOf: root.appendingPathComponent(f.name + ".u16le"))
    let planeBytes = f.width * f.height * 2
    let planes = try (0..<2).map { c in
        try PlaneDescriptor(width: f.width, height: f.height, components: [c], offset: c * planeBytes,
            rowBytes: f.width * 2, byteCount: (c + 1) * planeBytes)
    }
    let descriptor = try ImageDescriptor(width: f.width, height: f.height, meaningfulBits: f.meaningfulBits,
        components: [.uninterpreted("JPEG-LS:1"), .uninterpreted("JPEG-LS:2")], colour: .unknown, planes: planes)
    let image = try ImageDestination.allocate(descriptor: descriptor).write { bytes in samples.withUnsafeBytes { bytes.copyMemory(from: $0) } }
    let encoded = try await Encoder(configuration: .init(mode: f.near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: f.near),
        codecOptions: .init(restartIntervalLines: 0, interleaveMode: .line))).encode(image)
    candidates.append(["name": f.name.replacingOccurrences(of: "-i0-", with: "-i1-"),
        "source_fixture": f.name, "width": f.width, "height": f.height, "meaningfulBits": f.meaningfulBits,
        "near": f.near, "components": 2, "interleave": 1, "rgb": false,
        "samples": samples.base64EncodedString(), "encoded": encoded.data.base64EncodedString()])
}
let report: [String: Any] = ["licence": "Apache-2.0 original synthetic samples", "encoder_revision": "9ca35c57c6f355af547f48a6598ad4efa7f9f492", "cases": candidates]
try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]).write(to: URL(fileURLWithPath: CommandLine.arguments[2]))
print("Exported \(candidates.count) two-component line candidates.")
