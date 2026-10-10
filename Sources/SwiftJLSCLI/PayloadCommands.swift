// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS

func runPayload(_ options: Options) async throws {
    guard let command = options.command, let input = options.values["--input"] else {
        throw UsageError(message: "This command requires --input PATH (or '-').")
    }
    let values = options.values
    let producing = command == "encode" || command == "decode"
    guard !producing || values["--output"] != nil else { throw UsageError(message: "This command requires --output PATH (or '-').") }
    let shared: Set<String> = ["--input", "--input-format", "--backend", "--copy-policy", "--threads", "--max-memory", "--timeout"]
    let allowed = shared.union(producing ? ["--output", "--output-format"] : []).union(command == "encode" ? ["--mode", "--max-error"] : [])
    guard Set(values.keys).isSubset(of: allowed), producing || !options.overwrite else {
        throw UsageError(message: "An option does not apply to this command.")
    }
    func integer(_ key: String, default fallback: Int) throws -> Int {
        guard let text = values[key] else { return fallback }
        guard let value = Int(text), value > 0 else { throw UsageError(message: "\(key) requires a positive integer.") }
        return value
    }
    let memory = try integer("--max-memory", default: ResourceLimits.default.maximumMemoryBytes)
    let workers = try integer("--threads", default: ResourceLimits.default.maximumWorkers)
    guard workers <= 1024 else { throw UsageError(message: "--threads exceeds 1024.") }
    let timeout = values["--timeout"].flatMap(Double.init) ?? (values["--timeout"] == nil ? 120 : -1)
    guard timeout.isFinite, timeout > 0 else { throw UsageError(message: "--timeout requires positive finite seconds.") }
    guard memory > 262144 else { throw CodecError(.resourceLimitExceeded, "Memory budget is too small for bounded stream buffers.") }
    let codecMemory = memory - 262144
    let limits = try ResourceLimits(maximumCompressedBytes: min(memory, ResourceLimits.default.maximumCompressedBytes),
        maximumDecodedBytes: min(memory, ResourceLimits.default.maximumDecodedBytes),
        maximumWorkspaceBytes: min(memory, ResourceLimits.default.maximumWorkspaceBytes),
        maximumWorkers: workers, deadlineSeconds: timeout, maximumMemoryBytes: codecMemory)
    let execution: ExecutionPolicy
    switch values["--backend", default: "automatic"] {
    case "automatic": execution = .automatic
    case "scalar", "scalar-cpu": execution = .scalarCPU
    case "accelerated": execution = .required(.accelerated)
    default: throw UsageError(message: "Unsupported --backend value.")
    }
    guard values["--backend"] != "accelerated" else { throw CodecError(.backendUnavailable, "Accelerated backend unavailable.") }
    let copy: CopyPolicy
    switch values["--copy-policy", default: "require-sharing"] {
    case "require-sharing": copy = .requireSharedStorage
    case "allow-copy": copy = .allowCopy
    default: throw UsageError(message: "Unsupported --copy-policy value.")
    }
    let expectedInput = command == "encode" ? "nrrd" : "jls"
    guard values["--input-format", default: expectedInput] == expectedInput else {
        throw CodecError(.unsupportedFormat, "Unsupported input format for this command.")
    }
    if producing {
        let expectedOutput = command == "encode" ? "jls" : "nrrd"
        guard values["--output-format", default: expectedOutput] == expectedOutput else {
            throw CodecError(.unsupportedFormat, "Unsupported output format for this command.")
        }
    }
    var mode: CompressionMode = .lossless
    switch values["--mode", default: "lossless"] {
    case "lossless":
        guard values["--max-error"] == nil else { throw UsageError(message: "--max-error requires --mode near-lossless.") }
    case "near-lossless":
        guard values["--max-error"] != nil else { throw UsageError(message: "Near-lossless mode requires --max-error.") }
        mode = .nearLossless(maximumAbsoluteError: try integer("--max-error", default: 0))
    case "lossy": throw CodecError(.unsupportedFeature, "Unbounded lossy JPEG-LS is unsupported.")
    default: throw UsageError(message: "Invalid compression mode.")
    }
    let configuration = try EncoderConfiguration(mode: mode)
    let budget = StreamBudget(limits: limits)
    let stream = try InputStreamReader(path: input, budget: budget)
    var report: [String: Any] = ["command": command, "success": true, "backend": "scalarCPU"]
    if command == "encode" {
        let image = try stream.nrrdImage()
        let encoded = try await Encoder(configuration: configuration).encode(image,
            options: .init(resourceLimits: budget.remainingLimits(), executionPolicy: execution, copyPolicy: copy))
        try publish(path: values["--output", default: "-"], overwrite: options.overwrite, budget: budget) { fd in
            try encoded.data.withUnsafeBytes { try writeBytes($0, fd: fd, budget: budget) }
        }
        report["bytes"] = encoded.data.count
    } else {
        let data = try stream.compressed()
        let decoder = try Decoder()
        let decodeOptions = DecodeOptions(resourceLimits: try budget.remainingLimits(), executionPolicy: execution, copyPolicy: copy)
        let info = try decoder.inspect(data, options: decodeOptions)
        report["format"] = info.format; report["width"] = info.descriptor.width
        report["height"] = info.descriptor.height; report["meaningfulBits"] = info.descriptor.meaningfulBits
        if command == "decode" {
            guard info.descriptor.meaningfulBits == 16 else {
                throw CodecError(.unsupportedFeature, "NRRD output requires 16 meaningful bits; lower precision cannot be silently widened.")
            }
            let decoded = try await decoder.decode(data, options: decodeOptions)
            try publish(path: values["--output", default: "-"], overwrite: options.overwrite, budget: budget) { fd in
                try writeNRRD(decoded.image, fd: fd, budget: budget)
            }
        } else if command == "validate" {
            _ = try await decoder.decode(data, options: decodeOptions)
        }
    }
    try budget.check()
    if options.json || !producing {
        let output = try JSONSerialization.data(withJSONObject: report, options: [.sortedKeys]) + Data([10])
        try (producing ? FileHandle.standardError : FileHandle.standardOutput).write(contentsOf: output)
    }
}
