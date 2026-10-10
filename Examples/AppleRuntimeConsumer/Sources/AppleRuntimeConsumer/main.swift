// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS

let descriptor = try SwiftJLS.ImageDescriptor.greyscale16(width: 3, height: 2, meaningfulBits: 12, rowBytes: 8)
let destination = try SwiftJLS.ImageDestination.allocate(descriptor: descriptor)
let allocationID = destination.storage.allocationID
let image = try destination.writeUInt16 { x, y in x == 2 ? 4095 : UInt16(x + y * 3) }
guard image.storage.allocationID == allocationID,
      try image.sampleUInt16(x: 2, y: 1) == 4095,
      image.descriptor.meaningfulBits == 12 else {
    throw SwiftJLS.CodecError(.internalFailure, "Independent sample preservation failed.")
}
let encoder = try SwiftJLS.Encoder()
let decoder = try SwiftJLS.Decoder()
guard encoder.capabilities.canEncode, decoder.capabilities.canDecode else {
    throw SwiftJLS.CodecError(.internalFailure, "Native scalar codec is unavailable.")
}
let encoded = try await encoder.encode(image)
let output = try SwiftJLS.ImageDestination.allocate(descriptor: descriptor)
let outputID = output.storage.allocationID
let decoded = try await decoder.decode(encoded.data, into: output)
guard decoded.image.storage.allocationID == outputID,
      encoded.report.copyEvents.isEmpty, decoded.report.copyEvents.isEmpty,
      encoded.report.pixelAllocationCount == 0, decoded.report.pixelAllocationCount == 0 else {
    throw SwiftJLS.CodecError(.internalFailure, "Shared-storage codec hand-off failed.")
}
for y in 0..<descriptor.height {
    for x in 0..<descriptor.width {
        guard try decoded.image.sampleUInt16(x: x, y: y) == image.sampleUInt16(x: x, y: y) else {
            throw SwiftJLS.CodecError(.internalFailure, "Native sample preservation failed.")
        }
    }
}
print("Independent consumer passed: native lossless coding preserves padded 12-bit samples and destination identity.")
let bounded = DecodeOptions(resourceLimits: .watch)
let fixtureDirectory = URL(fileURLWithPath: CommandLine.arguments[1])
for name in ["c3-i2-p12-n0-17x13-noise", "hp3-c3-i1-p16-n0-1x19-edge", "map-p8-c3-i2-w2-n0"] {
    let data = try Data(contentsOf: fixtureDirectory.appendingPathComponent(name + ".jls"))
    let result = try await decoder.decode(data, options: bounded)
    let reencoded = try await encoder.encode(result.image, options: .init(resourceLimits: .watch))
    let roundtrip = try await decoder.decode(reencoded.data, options: bounded)
    guard result.image.descriptor == roundtrip.image.descriptor,
          result.image.metadata == roundtrip.image.metadata else {
        throw CodecError(.internalFailure, "Runtime interpretation or metadata mismatch")
    }
    try result.image.storage.withUnsafeBytes { first in
        try roundtrip.image.storage.withUnsafeBytes { second in
            guard first.elementsEqual(second) else { throw CodecError(.internalFailure, "Runtime sample mismatch") }
        }
    }
}
let mappedDecoder = try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, mappingOutputPrecision: 16)))
let palette = try Data(contentsOf: fixtureDirectory.appendingPathComponent("map-p8-c1-i0-w2-n0.jls"))
let mapped = try await mappedDecoder.decode(palette, options: bounded)
guard mapped.image.descriptor.meaningfulBits == 16, mapped.image.metadata.entries[JPEGLSMappingTables.key] == nil else {
    throw CodecError(.internalFailure, "Runtime mapping interpretation failed")
}
do {
    _ = try decoder.inspect(encoded.data, options: .init(resourceLimits: .init(maximumDecodedBytes: 1)))
    throw CodecError(.internalFailure, "Runtime resource limit was ignored")
} catch let error as CodecError {
    guard error.category == .resourceLimitExceeded else { throw error }
}
let cancelled = Task {
    try await decoder.decode(encoded.data, options: .init(resourceLimits: .watch, progress: { progress in
        if progress.phase == .processing { withUnsafeCurrentTask { $0?.cancel() } }
    }))
}
do {
    _ = try await cancelled.value
    throw CodecError(.internalFailure, "Runtime cancellation was ignored")
} catch is CancellationError {}
print("Apple runtime passed: direct storage, RGB/HP, mapping, metadata, Watch limits and cancellation.")
