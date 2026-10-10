// SPDX-License-Identifier: Apache-2.0
// Append after Consumer.swift and ComponentConsumer.swift in the isolated consumer.
let legacyManifest = try JSONDecoder().decode(ComponentManifest.self,
    from: Data(contentsOf: directory.appendingPathComponent("components-legacy-hp.json")))
let legacyDecoder = try Decoder(configuration: .init(codecOptions:
    .init(restartIntervalLines: 0, hpInterpretation: .legacyJLSwift)))
for f in legacyManifest.cases {
    let data = try Data(contentsOf: directory.appendingPathComponent(f.name + ".jls"))
    let image = try await legacyDecoder.decode(data).image
    guard let rawTransform = f.transform, let value = UInt8(exactly: rawTransform),
          let transform = CodecOptions.ColourTransform(rawValue: value) else {
        throw CodecError(.invalidArgument, "Missing legacy fixture transform")
    }
    let encoded = try await Encoder(configuration: .init(codecOptions:
        .init(restartIntervalLines: 0, interleaveMode: .sample, colourTransform: transform))).encode(image)
    try encoded.data.write(to: output.appendingPathComponent(f.name + ".jls"))
}
print("Wrote six explicitly decoded legacy HP migrations for independent sample verification.")
