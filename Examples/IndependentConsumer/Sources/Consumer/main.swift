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
