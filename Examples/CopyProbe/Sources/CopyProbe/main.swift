// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS
import CopyInstrumentation

// The probe stores only numeric bounds while this synchronous borrow is live;
// it never dereferences them. The retained owner and exclusive test execution
// keep the interval valid, and defer clears it before the borrow returns.
struct ObservedSource: ReadOnlyImageStorage {
    let source: any ReadOnlyImageStorage
    let inject: Bool
    var allocationID: UUID { source.allocationID }
    var byteCount: Int { source.byteCount }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R {
        try source.withUnsafeBytes { bytes in
            sjls_copy_probe_begin(bytes.baseAddress, bytes.count)
            defer { sjls_copy_probe_end() }
            if inject {
                // Deliberately invalid adapter: functional output survives, but
                // this full image copy must be visible to independent telemetry.
                let duplicate = Array(bytes)
                return try duplicate.withUnsafeBytes(body)
            }
            return try body(bytes)
        }
    }
}
guard sjls_copy_probe_self_test() != 0 else { throw CodecError(.internalFailure, "Copy interposition is unavailable or failed its control") }
let directory = URL(fileURLWithPath: CommandLine.arguments[1])
let names = ["p12-17x13-noise", "n3-p12-17x13-noise", "c3-i2-p12-n0-17x13-noise", "hp1-c3-i2-p8-n0-17x13-noise", "map-p8-c3-i2-w2-n0"]
var results: [[String: Any]] = []
for name in names {
    let data = try Data(contentsOf: directory.appendingPathComponent(name + ".jls"))
    let decoded = try await Decoder().decode(data)
    let isHP = name.hasPrefix("hp1")
    let modes: [CodecOptions.InterleaveMode] = decoded.image.descriptor.components.count == 1 ? [.none] : (isHP ? [.line, .sample] : [.none, .line, .sample])
    let near = name.hasPrefix("n3-") ? 3 : 0
    for mode in modes {
    for inject in [false, true] {
        let source = ObservedSource(source: decoded.image.storage, inject: inject)
        let image = try Image(descriptor: decoded.image.descriptor, storage: source, metadata: decoded.image.metadata)
        let options = try CodecOptions(restartIntervalLines: 0, interleaveMode: mode, colourTransform: isHP ? .hp1 : .none)
        sjls_copy_probe_reset()
        let encoded = try await Encoder(configuration: .init(mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near), codecOptions: options)).encode(image)
        let moved = sjls_copy_probe_bytes()
        guard inject ? moved >= image.storage.byteCount : moved == 0 else {
            throw CodecError(.internalFailure, "Unexpected scoped pixel copy count")
        }
        let output = try await Decoder().decode(encoded.data)
        var maximumError = 0
        try image.storage.withUnsafeBytes { original in
            try output.image.storage.withUnsafeBytes { actual in
                guard original.count == actual.count else { throw CodecError(.internalFailure, "Copy probe shape mismatch") }
                for at in stride(from: 0, to: original.count, by: 2) {
                    let a = Int(original[at]) | Int(original[at + 1]) << 8
                    let b = Int(actual[at]) | Int(actual[at + 1]) << 8
                    maximumError = max(maximumError, abs(a - b))
                }
                guard maximumError <= near else { throw CodecError(.internalFailure, "Copy probe fidelity mismatch") }
            }
        }
        results.append(["fixture": name, "injected": inject, "observed_source_copy_bytes": moved,
            "source_capacity": image.storage.byteCount, "maximum_sample_error": maximumError, "near": near, "interleave": mode.rawValue])
    }
    }
}
let report: [String: Any] = ["self_test": true, "cases": results,
    "scope": "Linux ordinary release memcpy/memmove reads from the retained pixel owner during the actual scoped encoder borrow. Inlined copies are not intercepted; allocation mutation and source review are separate evidence."]
try FileHandle.standardOutput.write(contentsOf: JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted, .sortedKeys]))
