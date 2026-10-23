import Foundation
import SwiftJLS
struct Preset: Decodable {
    let maximumSampleValue: Int, threshold1: Int, threshold2: Int, threshold3: Int, reset: Int
    var options: CodecOptions.Preset { get throws {
        try .init(maximumSampleValue: maximumSampleValue, threshold1: threshold1,
                  threshold2: threshold2, threshold3: threshold3, reset: reset)
    } }
}
struct Fixture: Decodable { let name: String; let width: Int; let height: Int; let meaningfulBits: Int; let near: Int?; let restartInterval: Int?; let preset: Preset? }
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
    let encoded = try await Encoder(configuration: .init(mode: mode, codecOptions: .init(restartIntervalLines: f.restartInterval ?? 0, preset: f.preset?.options))).encode(image)
    try encoded.data.write(to: output.appendingPathComponent(f.name + ".jls"))
}
print("Wrote \(manifest.cases.count) SwiftJLS outputs for independent decoding.")

// SPDX-License-Identifier: Apache-2.0
// Append to Consumer.swift in the isolated oracle consumer package.
struct ComponentFixture: Decodable {
    let transform: Int?
    let name: String, width: Int, height: Int, meaningfulBits: Int, near: Int, components: Int, interleave: Int
}
struct ComponentManifest: Decodable { let cases: [ComponentFixture] }
let componentManifest = try JSONDecoder().decode(ComponentManifest.self, from: Data(contentsOf: directory.appendingPathComponent("components.json")))
let hpManifest = try JSONDecoder().decode(ComponentManifest.self, from: Data(contentsOf: directory.appendingPathComponent("components-hp.json")))
for f in componentManifest.cases + hpManifest.cases {
    let raw = try Data(contentsOf: directory.appendingPathComponent(f.name + ".u16le"))
    let info = try Decoder().inspect(Data(contentsOf: directory.appendingPathComponent(f.name + ".jls")))
    let row = f.width * 2 + 14, planeSize = row * f.height + 8
    let planes = try (0..<f.components).map { c in
        try PlaneDescriptor(width: f.width, height: f.height, components: [c], offset: c * planeSize + 2,
            rowBytes: row, byteCount: (c + 1) * planeSize)
    }
    let shape = try ImageDescriptor(width: f.width, height: f.height, meaningfulBits: f.meaningfulBits,
        components: info.descriptor.components, colour: info.descriptor.colour, planes: planes)
    let image = try ImageDestination.allocate(descriptor: shape).write { bytes in
        for c in 0..<f.components { for y in 0..<f.height { for x in 0..<f.width {
            let input = (c * f.width * f.height + y * f.width + x) * 2
            let output = planes[c].offset + y * row + x * 2
            bytes[output] = raw[input]; bytes[output + 1] = raw[input + 1]
        } } }
    }
    guard let interleave = CodecOptions.InterleaveMode(rawValue: UInt8(f.interleave)) else {
        throw CodecError(.invalidArgument, "Unknown fixture interleave mode")
    }
    for restart in (f.interleave == 0 ? [0, 3] : [0]) {
        let options = try CodecOptions(restartIntervalLines: restart, interleaveMode: interleave, colourTransform: CodecOptions.ColourTransform(rawValue: UInt8(f.transform ?? 0)) ?? .none)
        let encoded = try await Encoder(configuration: .init(mode: f.near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: f.near), codecOptions: options)).encode(image)
        let name = f.name + (restart == 0 ? "" : "-r3")
        try encoded.data.write(to: output.appendingPathComponent(name + ".jls"))
    }
}
print("Wrote component and component-restart outputs for independent decoding.")

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

for manifestName in ["legacy-profiles", "legacy-combined"] {
let legacyProfiles = try JSONDecoder().decode(ComponentManifest.self,
    from: Data(contentsOf: directory.appendingPathComponent(manifestName + ".json")))
for f in legacyProfiles.cases {
    let data = try Data(contentsOf: directory.appendingPathComponent(f.name + ".jls"))
    let image = try await legacyDecoder.decode(data).image
    let encoded = try await Encoder().encode(image)
    try encoded.data.write(to: output.appendingPathComponent(f.name + ".jls"))
}
}

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

