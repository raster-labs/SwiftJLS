// SPDX-License-Identifier: Apache-2.0
import Foundation
import Dispatch
import Synchronization
import SwiftJLS
import PhaseMarkers

func require(_ condition: Bool) throws {
    if !condition { throw CodecError(.internalFailure, "Workspace probe invariant failed") }
}
// A synchronous driver keeps the main pthread alive while the same public
// asynchronous APIs execute on the generic executor. This avoids Valgrind's
// internal crash in libdispatch's async-main thread teardown path.
func runProbe() async throws {
    let args = CommandLine.arguments
    try require(args.count == 6)
    let operation = args[1]
    guard let width = Int(args[2]), let height = Int(args[3]), let components = Int(args[4]), let near = Int(args[5]),
          (1...4096).contains(width), (1...4096).contains(height), [1,3].contains(components), [0,3].contains(near),
          ["encode", "owned", "into", "inspect"].contains(operation) else {
        throw CodecError(.invalidArgument, "Expected operation width height components near")
    }
    let capacity = width * height * components * 2
    let plane = try PlaneDescriptor(width: width, height: height, components: Array(0..<components),
        sampleStride: 2, pixelStride: components * 2, rowBytes: width * components * 2, byteCount: capacity)
    let descriptor = try ImageDescriptor(width: width, height: height, meaningfulBits: 12,
        components: components == 1 ? [.grey] : [.red, .green, .blue], colour: components == 1 ? .greyscale : .rgb, planes: [plane])
    let source = try ImageDestination.allocate(descriptor: descriptor).write { bytes in
        for i in 0..<(capacity / 2) {
            let value = (i * 271 + i / width * 17) & 4095
            bytes[i * 2] = UInt8(truncatingIfNeeded: value); bytes[i * 2 + 1] = UInt8(value >> 8)
        }
    }
    let encoder = try Encoder(configuration: .init(mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
        codecOptions: .init(restartIntervalLines: 0, interleaveMode: components == 1 ? .none : .sample)))
    let decoder = try Decoder()
    let reference = try await encoder.encode(source)
    let info = try decoder.inspect(reference.data)
    let destination = try ImageDestination.allocate(descriptor: info.descriptor)
    // Setup, expected values and destination allocation precede the measured phase.
    // Result ownership remains live through the end marker; verification follows it.
    let begin = swiftjls_workspace_begin()
    try require(begin != nil)
    var encoded: EncodedImage?
    var decoded: DecodedImage?
    var inspected: ImageInfo?
    switch operation {
    case "encode": encoded = try await encoder.encode(source)
    case "owned": decoded = try await decoder.decode(reference.data)
    case "into": decoded = try await decoder.decode(reference.data, into: destination)
    default: inspected = try decoder.inspect(reference.data)
    }
    let end = swiftjls_workspace_end()
    try require(end != nil)
    withExtendedLifetime((source, destination, reference, info, encoder, decoder, encoded, decoded, inspected)) {}
    swiftjls_workspace_release(end); swiftjls_workspace_release(begin)
    if let encoded { try require(encoded.data == reference.data) }
    if let inspected { try require(inspected.descriptor == info.descriptor) }
    if let decoded {
        if operation == "into" { try require(decoded.image.storage.allocationID == destination.storage.allocationID) }
        try decoded.image.storage.withUnsafeBytes { bytes in
            for p in decoded.image.descriptor.planes { for (slot, c) in p.components.enumerated() {
                for y in 0..<height { for x in 0..<width {
                    let i = (y * width + x) * components + c
                    let expected = (i * 271 + i / width * 17) & 4095
                    let at = p.offset + y * p.rowBytes + x * p.pixelStride + slot * p.sampleStride
                    let actual = Int(bytes[at]) | Int(bytes[at + 1]) << 8
                    try require(abs(actual - expected) <= near)
                } }
            } }
        }
    }
    let report: [String: Any] = ["operation": operation, "width": width, "height": height,
        "components": components, "near": near, "samples_verified": true,
        "source_bytes": capacity, "compressed_bytes": reference.data.count,
        "scope": "One marked public API operation; setup and post-operation sample checks excluded. Result remains live at end."]
    print(String(decoding: try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]), as: UTF8.self))
}

private final class ProbeCompletion: Sendable {
    let result = Mutex<Result<Void, any Error>?>(nil)
    let done = DispatchSemaphore(value: 0)
}
private let completion = ProbeCompletion()
Task.detached { [completion] in
    do {
        try await runProbe()
        completion.result.withLock { $0 = .success(()) }
    } catch {
        completion.result.withLock { $0 = .failure(error) }
    }
    completion.done.signal()
}
completion.done.wait()
guard let result = completion.result.withLock({ $0 }) else {
    throw CodecError(.internalFailure, "Workspace probe did not finish")
}
try result.get()
