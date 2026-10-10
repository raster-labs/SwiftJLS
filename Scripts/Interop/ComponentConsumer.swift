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
