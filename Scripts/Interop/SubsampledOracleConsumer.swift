// SPDX-License-Identifier: Apache-2.0
// Fixture-only producer linked to the isolated scheduler-adapted predecessor.
// Its decoder and entropy kernels remain at the pinned predecessor revision.
import Foundation
import JPEGLS
struct Failure: Error {}
let output = URL(fileURLWithPath: CommandLine.arguments[1])
try FileManager.default.createDirectory(at: output, withIntermediateDirectories: true)
var cases: [[String: Any]] = []
for bits in [8,12,16] {
 for near in [0,3] {
  for pattern in ["blocks","noise"] {
   let maximum = (1 << bits) - 1
   let widths = [17,17,9], heights = [19,5,10]
   let planes = (0..<3).map { c in (0..<heights[c]).map { y in (0..<widths[c]).map { x in
       pattern == "blocks" ? ((x/4)*19 + (y/3)*37 + c*73) & maximum : (x*1733 + y*251 + c*991 + x*y*107) & maximum
   } } }
   let frame = try JPEGLSFrameHeader(bitsPerSample: bits, height: 19, width: 17, componentCount: 3,
       components: [.init(id: 1, horizontalSamplingFactor: 2, verticalSamplingFactor: 4),
                    .init(id: 2, horizontalSamplingFactor: 2, verticalSamplingFactor: 1),
                    .init(id: 3, horizontalSamplingFactor: 1, verticalSamplingFactor: 2)])
   let image = try MultiComponentImageData(components: (0..<3).map { .init(id: UInt8($0+1), pixels: planes[$0]) }, frameHeader: frame)
   let encoded = try JPEGLSEncoder().encode(image, configuration: .init(near: near, interleaveMode: .line))
   let decoded = try JPEGLSDecoder().decode(encoded)
   var raw = Data(), maximumError = 0
   for c in 0..<3 { for y in 0..<heights[c] { for x in 0..<widths[c] {
       let value = decoded.components[c].pixels[y][x]
       maximumError = max(maximumError, abs(value - planes[c][y][x]))
       raw.append(UInt8(value & 255)); raw.append(UInt8(value >> 8))
   } } }
   guard maximumError <= near else { throw Failure() }
   let name = "subsampled-p\(bits)-n\(near)-\(pattern)"
   try encoded.write(to: output.appendingPathComponent(name + ".jls"))
   try raw.write(to: output.appendingPathComponent(name + ".u16le"))
   cases.append(["name": name, "width": 17, "height": 19, "widths": widths, "heights": heights,
       "meaningfulBits": bits, "near": near, "components": 3, "interleave": 1, "rgb": false,
       "pattern": pattern, "predecessor_maximum_error": maximumError])
  }
 }
}
try JSONSerialization.data(withJSONObject: ["cases": cases], options: [.prettyPrinted,.sortedKeys]).write(to: output.appendingPathComponent("subsampled-nonzero.json"))
print("12 nonzero subsampled fixtures checked with unchanged predecessor decoder")
