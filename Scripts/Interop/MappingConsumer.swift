// SPDX-License-Identifier: Apache-2.0
// Append to the existing successor interop consumer.
struct MappingFixture: Decodable { let name: String; let interleave: UInt8 }
struct MappingManifest: Decodable { let cases: [MappingFixture] }
for manifestName in ["mapping", "extended"] {
let mappingManifest = try JSONDecoder().decode(MappingManifest.self,
    from: Data(contentsOf: directory.appendingPathComponent(manifestName + ".json")))
for item in mappingManifest.cases {
    let source = try Data(contentsOf: directory.appendingPathComponent(item.name + ".jls"))
    let decoded = try await Decoder().decode(source)
    guard let mode = CodecOptions.InterleaveMode(rawValue: item.interleave) else { throw CodecError(.invalidArgument, "Invalid mapping fixture interleave") }
    let encoded = try await Encoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, interleaveMode: mode))).encode(decoded.image)
    try encoded.data.write(to: output.appendingPathComponent(item.name + ".jls"))
}
}
