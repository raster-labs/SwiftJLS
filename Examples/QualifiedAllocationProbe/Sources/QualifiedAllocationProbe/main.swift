// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS
import AllocationInstrumentation
#if os(Linux)
import Glibc
#else
import Darwin
#endif

private typealias Decoder = QualifiedMonochromeDecoder
private typealias Info = Decoder.MonochromeInfo
private enum ProbeError: Error { case invalid(String) }
private func require(_ condition: Bool, _ message: String) throws {
    if !condition { throw ProbeError.invalid(message) }
}
private func emit(_ object: [String: Any]) throws {
    print(String(decoding: try JSONSerialization.data(withJSONObject: object, options: [.sortedKeys]), as: UTF8.self))
}
private struct Manifest: Decodable { let cases: [Fixture] }
private struct Fixture: Decodable {
    struct Preset: Decodable { let reset: Int }
    let name: String
    let width, height, meaningfulBits: Int
    let near, components, entryWidth: Int?
    let preset: Preset?
}
private enum Expectation { case success, failure(QualifiedFailure.Code?) }
private struct Adaptations: Decodable { let cases: [Adaptation] }
private struct Adaptation: Decodable {
    let name, adaptedFile, originalSha256, adaptedSha256, samplesSha256, reason: String
    let standardThresholds, legacyThresholds: [Int]
}
private struct Case {
    var name: String
    var encoded: Data
    var samples: [UInt16]
    var width, height, bits, near: Int
    var inspection: Expectation = .success
    var decoding: Expectation = .success
    var limits = Decoder.Limits()
    var shortWorkspace = false
    var shortOutput = false
    var cancellation: UInt64 = 0
    var countCancellation = false
    var cancelDuringDecode = false
    var requirePartialWrite = false
    var oracle = "repository independent/reference fixture"
    var adaptation: Adaptation?
}
private func read(_ root: URL, _ name: String) throws -> Data {
    try Data(contentsOf: root.appendingPathComponent(name))
}
private func words(_ data: Data) throws -> [UInt16] {
    try require(data.count % 2 == 0, "Odd sample fixture")
    return stride(from: 0, to: data.count, by: 2).map { UInt16(data[$0]) | UInt16(data[$0 + 1]) << 8 }
}
private func load(_ fixture: Fixture, root: URL, mapped: Bool = false) throws -> Case {
    let decoded = root.appendingPathComponent(fixture.name + ".decoded.u16le")
    let sampleName = mapped ? fixture.name + ".mapped.u16le" :
        (FileManager.default.fileExists(atPath: decoded.path) ? fixture.name + ".decoded.u16le" : fixture.name + ".u16le")
    return Case(name: fixture.name, encoded: try read(root, fixture.name + ".jls"),
        samples: try words(read(root, sampleName)), width: fixture.width, height: fixture.height,
        bits: fixture.meaningfulBits, near: fixture.near ?? 0)
}
private func manifests(_ root: URL, _ name: String) throws -> [Fixture] {
    try JSONDecoder().decode(Manifest.self, from: read(root, name)).cases
}

// Convert standard continuation Wt to the explicitly selected predecessor
// profile's omitted-Wt syntax. No entropy/sample bytes change. Setup is unmeasured.
private func legacyContinuations(_ original: Data) throws -> Data {
    var result = original, cursor = 2
    while cursor + 4 <= result.count {
        try require(result[cursor] == 255, "Expected header marker")
        if result[cursor + 1] == 218 { break }
        let length = Int(result[cursor + 2]) << 8 | Int(result[cursor + 3])
        try require(length >= 2 && cursor + 2 + length <= result.count, "Invalid fixture segment")
        if result[cursor + 1] == 248 && result[cursor + 4] == 3 {
            try require(length >= 5, "Short continuation fixture")
            result.remove(at: cursor + 6)
            result[cursor + 2] = UInt8((length - 1) >> 8)
            result[cursor + 3] = UInt8((length - 1) & 255)
            cursor += length + 1
        } else { cursor += length + 2 }
    }
    return result
}
private func entropyStart(_ data: Data) throws -> Int {
    var cursor = 2
    while cursor + 4 <= data.count {
        try require(data[cursor] == 255, "Expected fixture marker")
        let length = Int(data[cursor + 2]) << 8 | Int(data[cursor + 3])
        try require(length >= 2 && cursor + 2 + length <= data.count, "Invalid fixture segment")
        if data[cursor + 1] == 218 { return cursor + 2 + length }
        cursor += length + 2
    }
    throw ProbeError.invalid("Missing fixture SOS")
}
private func makeCases(root: URL, cold: Bool, adaptationManifest: URL?) throws -> [Case] {
    let fixtures = try manifests(root, "manifest.json")
    guard let oneFixture = fixtures.first(where: { $0.name == "p8-1x1-max" }),
          let noiseFixture = fixtures.first(where: { $0.name == "p8-17x13-noise" }) else {
        throw ProbeError.invalid("Missing control fixtures")
    }
    let one = try load(oneFixture, root: root)
    if cold { return [one] }
    let adapters = try adaptationManifest.map { try JSONDecoder().decode(Adaptations.self, from: Data(contentsOf: $0)).cases } ?? []
    try require(Set(adapters.map(\.name)).count == adapters.count, "Duplicate adapter name")
    var result: [Case] = [], excluded: [String] = []
    for f in fixtures {
        // This is an independent-standard-oracle subset of an explicitly legacy
        // profile. Low-MAXVAL default differences are NOT silently passed.
        let lowFlat = (f.near ?? 0) == 0 && (f.name.hasSuffix("1x1-max") || f.name.hasSuffix("33x9-zero"))
        guard f.meaningfulBits >= 8 || f.preset != nil || lowFlat else { excluded.append(f.name); continue }
        var c = try load(f, root: root)
        if let adapter = adapters.first(where: { $0.name == f.name }), let adaptationManifest {
            c.encoded = try Data(contentsOf: adaptationManifest.deletingLastPathComponent().appendingPathComponent(adapter.adaptedFile))
            c.name += "-explicit-standard-defaults"
            c.oracle += "; explicit standard LSE adapter, original entropy and sample oracle unchanged"
            c.adaptation = adapter
        }
        if let preset = f.preset, preset.reset > 255 {
            c.inspection = .failure(.reset); c.decoding = .failure(.reset)
        }
        result.append(c)
    }
    try emit(["kind": "scope", "excluded_standard_fixtures": excluded,
              "reason": "Low-MAXVAL default thresholds intentionally differ in jlswift0101. Low-precision flat and explicit-preset cases remain covered; legacy unit oracles cover the other semantics."])
    for (name, bits, near) in [("p2-noise", 2, 0), ("p7-noise", 7, 0), ("p8-final-preset", 8, 0), ("p8-near127", 8, 127)] {
        let path = "qualified-d175/" + name
        var c = Case(name: path, encoded: try read(root, path + ".jls"),
                     samples: try words(read(root, path + ".u16le")), width: 17, height: 13, bits: bits, near: near)
        c.oracle = "exact JLSwift d175452 predecessor compatibility; qualified-d175/provenance.json"
        result.append(c)
    }
    for f in try manifests(root, "mapping.json") where f.components == 1 {
        var c = try load(f, root: root, mapped: true)
        c.encoded = try legacyContinuations(c.encoded)
        c.name += "-legacy-continuations"
        if f.entryWidth == 3 {
            c.inspection = .failure(.mappingWidth); c.decoding = .failure(.mappingWidth)
        } else if c.samples.contains(where: { Int($0) >= 1 << c.bits }) {
            c.decoding = .failure(.mappedPrecision)
        }
        result.append(c)
    }
    guard let mapFixture = try manifests(root, "mapping.json").first(where: { $0.name == "map-p8-c1-i0-w1-n0" }) else {
        throw ProbeError.invalid("Missing mapping rejection fixture")
    }
    var missingMap = try load(mapFixture, root: root, mapped: true)
    missingMap.name = "missing-selected-mapping-table"
    let scanStart = try entropyStart(missingMap.encoded)
    // A one-component SOS is ten bytes including its marker and length.
    missingMap.encoded[scanStart - 4] = 99
    missingMap.inspection = .failure(.missingMappingTable); missingMap.decoding = .failure(.missingMappingTable)
    result.append(missingMap)
    var shortMap = try load(mapFixture, root: root, mapped: true)
    shortMap.name = "short-selected-mapping-table"
    guard let marker = shortMap.encoded.range(of: Data([255, 248, 1, 5, 2, 7, 1])) else {
        throw ProbeError.invalid("Missing 256-entry mapping fixture segment")
    }
    shortMap.encoded.removeSubrange((marker.lowerBound + 8)..<(marker.lowerBound + 263))
    shortMap.encoded[marker.lowerBound + 2] = 0; shortMap.encoded[marker.lowerBound + 3] = 6
    shortMap.decoding = .failure(.mappingIndex); shortMap.requirePartialWrite = true
    result.append(shortMap)
    // Existing predecessor fixtures have independently specified sample formulas
    // in PredecessorProfileTests; their legacy manifest intentionally has no shape.
    for (width, height) in [(65_537, 1), (1, 65_537)] {
        let name = "legacy-extended-\(width)x\(height)"
        let samples = (0..<(width * height)).map { UInt16((($0 % width) * 17 + ($0 / width) * 3) & 255) }
        result.append(Case(name: name, encoded: try read(root, name + ".jls"), samples: samples,
                           width: width, height: height, bits: 8, near: 0,
                           oracle: "legacy fixture; PredecessorProfileTests exact sample formula"))
    }
    for width in [1, 2] {
        let name = "legacy-mapping-w\(width)"
        let samples = [0, 1, 32_764, 32_765, 65_535].map { UInt16(($0 * 271) & (width == 1 ? 255 : 65_535)) }
        result.append(Case(name: name, encoded: try read(root, name + ".jls"), samples: samples,
                           width: 5, height: 1, bits: 16, near: 0,
                           oracle: "legacy fixture; PredecessorProfileTests exact sample formula"))
    }
    var metadata = one
    metadata.name = "opaque-app-comment"
    metadata.encoded.insert(contentsOf: [255, 226, 0, 6, 73, 67, 67, 0, 255, 254, 0, 5, 1, 2, 3], at: 2)
    result.append(metadata)
    for count in [1, 2, 4097] {
        var c = one; c.name = "leading-fill-\(count)"; c.encoded = Data(repeating: 255, count: count) + one.encoded
        result.append(c)
        var padded = c; padded.name += "-dicom-zero"; padded.encoded.append(0)
        if c.encoded.count % 2 == 0 { padded.inspection = .failure(.trailingBytes); padded.decoding = .failure(.trailingBytes) }
        result.append(padded)
    }
    for length in 0..<one.encoded.count {
        var c = one; c.name = "truncated-prefix-\(length)"; c.encoded = Data(one.encoded.prefix(length))
        c.inspection = .failure(nil); c.decoding = .failure(nil); result.append(c)
    }
    var late = try load(noiseFixture, root: root)
    late.name = "late-entropy-truncation"
    let start = try entropyStart(late.encoded)
    // Retain half the noisy entropy, enough to reconstruct real pixels before
    // the value-only failure. The complete marker envelope still inspects.
    late.encoded = Data(late.encoded.prefix(start + (late.encoded.count - start - 2) / 2)) + Data([255, 217])
    late.decoding = .failure(nil); late.requirePartialWrite = true; result.append(late)
    var small = one; small.name = "short-workspace"; small.shortWorkspace = true
    small.inspection = .failure(.invalidCallerSpans); small.decoding = .failure(.invalidCallerSpans); result.append(small)
    small = one; small.name = "short-output"; small.shortOutput = true; small.decoding = .failure(.destinationTooSmall); result.append(small)
    small = one; small.name = "compressed-limit"; small.limits = .init(maximumEncodedBytes: one.encoded.count - 1)
    small.inspection = .failure(.invalidCallerSpans); small.decoding = .failure(.invalidCallerSpans); result.append(small)
    small = one; small.name = "decoded-limit"; small.limits = .init(maximumDecodedBytes: 1)
    small.inspection = .failure(.decodedLimit); small.decoding = .failure(.decodedLimit); result.append(small)
    small = one; small.name = "immediate-cancellation"; small.cancellation = 1
    small.inspection = .failure(.cancelled); small.decoding = .failure(.cancelled); result.append(small)
    small = try load(noiseFixture, root: root); small.name = "cancellation-count-baseline"; small.countCancellation = true
    result.append(small)
    small = try load(noiseFixture, root: root); small.name = "cancellation-during-decode"; small.cancelDuringDecode = true
    small.decoding = .failure(.cancelled); small.requirePartialWrite = true; result.append(small)
    return result
}

private func total(_ c: SJLSAllocationCounts) -> UInt64 {
    c.malloc_calls + c.calloc_calls + c.realloc_calls + c.memalign_calls + c.posix_memalign_calls +
    c.aligned_alloc_calls + c.valloc_calls + c.pvalloc_calls + c.reallocarray_calls
}
private func counters(_ c: SJLSAllocationCounts) -> [String: Any] {
    ["malloc": c.malloc_calls, "calloc": c.calloc_calls, "realloc": c.realloc_calls,
     "memalign": c.memalign_calls, "posix_memalign": c.posix_memalign_calls,
     "aligned_alloc": c.aligned_alloc_calls, "valloc": c.valloc_calls, "pvalloc": c.pvalloc_calls,
     "reallocarray": c.reallocarray_calls, "free": c.free_calls, "requested_bytes": c.requested_bytes,
     "overflow": c.overflow, "allocation_calls": total(c)]
}

// No closure construction, throwing conversion, JSON, hashing, array access or
// printing occurs between begin/end. All owners and spans are prepared first.
@inline(never)
private func measure(_ decoder: Decoder, input: UnsafeRawBufferPointer,
                     output: UnsafeMutableBufferPointer<UInt16>, workspace: UnsafeMutableRawBufferPointer,
                     cancellation: QualifiedCancellation, inspect: Bool)
    -> (QualifiedOutcome<Info>, SJLSAllocationCounts) {
    precondition(sjls_allocation_begin() == 1)
    let outcome: QualifiedOutcome<Info>
    if inspect { outcome = decoder.inspect(input, workspace: workspace, cancellation: cancellation) }
    else { outcome = decoder.decode(input, into: output, workspace: workspace, cancellation: cancellation) }
    let counts = sjls_allocation_end()
    return (outcome, counts)
}

private func run(_ c: Case, inspect: Bool, first: Bool) throws -> (passed: Bool, callbackCount: UInt64) {
    let guardBytes = 64, guardSamples = 32, sentinel: UInt16 = 0xa55a
    let inputMemory = UnsafeMutableRawPointer.allocate(byteCount: c.encoded.count + 2 * guardBytes, alignment: 16)
    inputMemory.initializeMemory(as: UInt8.self, repeating: 0xa5, count: c.encoded.count + 2 * guardBytes)
    let inputBase = inputMemory.advanced(by: guardBytes)
    c.encoded.withUnsafeBytes { bytes in if let base = bytes.baseAddress { inputBase.copyMemory(from: base, byteCount: bytes.count) } }
    let workspaceBytes = Decoder.workspaceByteCount
    let scratch = UnsafeMutableRawPointer.allocate(byteCount: workspaceBytes + 2 * guardBytes, alignment: Decoder.workspaceAlignment)
    scratch.initializeMemory(as: UInt8.self, repeating: 0xa5, count: workspaceBytes + 2 * guardBytes)
    let sampleCount = c.width * c.height
    let pixels = UnsafeMutablePointer<UInt16>.allocate(capacity: sampleCount + 2 * guardSamples)
    pixels.initialize(repeating: sentinel, count: sampleCount + 2 * guardSamples)
    defer { inputMemory.deallocate(); scratch.deallocate(); pixels.deinitialize(count: sampleCount + 2 * guardSamples); pixels.deallocate() }
    let input = UnsafeRawBufferPointer(start: inputBase, count: c.encoded.count)
    let workspace = UnsafeMutableRawBufferPointer(start: scratch.advanced(by: guardBytes), count: workspaceBytes - (c.shortWorkspace ? 1 : 0))
    let output = UnsafeMutableBufferPointer(start: pixels.advanced(by: guardSamples), count: sampleCount - (c.shortOutput ? 1 : 0))
    var state = SJLSCancellationState(calls: 0, cancel_after: c.cancellation)
    let decoder = Decoder(profile: .jlswift0101, limits: c.limits)
    let (outcome, counts) = withUnsafeMutablePointer(to: &state) { pointer in
        let cancellation = c.cancellation != 0 || c.countCancellation ?
            QualifiedCancellation(check: sjls_probe_cancel, context: pointer) : QualifiedCancellation()
        return measure(decoder, input: input, output: output, workspace: workspace, cancellation: cancellation, inspect: inspect)
    }
    var correct = true, failureCode: String? = nil, mismatch: Int? = nil
    let expected = inspect ? c.inspection : c.decoding
    switch (outcome, expected) {
    case (.success(let info), .success):
        correct = info.width == c.width && info.height == c.height && info.bitsPerSample == c.bits && info.near == c.near
        if !inspect {
            correct = correct && c.samples.count == sampleCount
            for i in 0..<min(c.samples.count, output.count) where output[i] != c.samples[i] { mismatch = i; correct = false; break }
        }
    case (.failure(let failure), .failure(let expectedCode)):
        failureCode = String(describing: failure.code)
        correct = expectedCode == nil || failure.code == expectedCode
    case (.failure(let failure), .success): failureCode = String(describing: failure.code); correct = false
    case (.success, .failure): correct = false
    }
    var canaries = true
    for i in 0..<guardBytes {
        canaries = canaries && inputMemory.load(fromByteOffset: i, as: UInt8.self) == 0xa5 &&
            inputMemory.load(fromByteOffset: guardBytes + c.encoded.count + i, as: UInt8.self) == 0xa5 &&
            scratch.load(fromByteOffset: i, as: UInt8.self) == 0xa5 &&
            scratch.load(fromByteOffset: guardBytes + workspaceBytes + i, as: UInt8.self) == 0xa5
    }
    for i in 0..<guardSamples { canaries = canaries && pixels[i] == sentinel && pixels[guardSamples + sampleCount + i] == sentinel }
    if c.shortWorkspace { canaries = canaries && scratch.load(fromByteOffset: guardBytes + workspaceBytes - 1, as: UInt8.self) == 0xa5 }
    for i in c.encoded.indices { canaries = canaries && input[i] == c.encoded[i] }
    let changed = output.contains { $0 != sentinel }
    if inspect { correct = correct && !changed }
    if !inspect && c.requirePartialWrite { correct = correct && changed }
    // Read borrowed output only after the operation returns, never in callback.
    if !inspect && c.cancelDuringDecode { correct = correct && output.contains { $0 == sentinel } }
    if c.shortOutput { correct = correct && pixels[guardSamples + sampleCount - 1] == sentinel }
    var report: [String: Any] = ["kind": "operation", "case": c.name, "operation": inspect ? "inspect" : "decode",
        "first_qualified_api_call_in_process": first, "counts": counters(counts), "correctness_passed": correct,
        "canaries_and_input_unchanged": canaries, "output_changed": changed, "cancellation_calls": state.calls,
        "cancel_after_callback": state.cancel_after, "input_bytes": input.count, "output_samples": output.count,
        "workspace_bytes": workspace.count, "oracle": c.oracle,
        "allocation_observation_passed": total(counts) == 0 && counts.overflow == 0]
    if let failureCode { report["failure_code"] = failureCode }
    if let a = c.adaptation {
        report["input_adapter"] = ["original_case": a.name, "original_sha256": a.originalSha256,
            "adapted_sha256": a.adaptedSha256, "unchanged_samples_sha256": a.samplesSha256,
            "standard_thresholds": a.standardThresholds, "legacy_thresholds": a.legacyThresholds, "reason": a.reason]
    }
    if let mismatch { report["first_sample_mismatch"] = mismatch; report["actual_sample"] = output[mismatch]; report["expected_sample"] = c.samples[mismatch] }
    try emit(report)
    return (correct && canaries && total(counts) == 0 && counts.overflow == 0, state.calls)
}

private func main() throws {
    let args = CommandLine.arguments
    try require((args.count == 3 || args.count == 4) && ["--matrix", "--cold-inspect", "--cold-decode"].contains(args[1]),
                "Usage: QualifiedAllocationProbe --matrix|--cold-inspect|--cold-decode FIXTURE_DIRECTORY [ADAPTATION_MANIFEST]")
    guard sjls_allocation_supported() == 1 else {
        try emit(["kind": "unsupported", "reason": "Allocation interposition requires Linux with glibc; no observations claimed."])
        exit(2)
    }
    let controls = sjls_allocation_self_test()
    try emit(["kind": "allocator_positive_controls", "observed_mask": controls, "required_mask": 511, "passed": controls == 511])
    try require(controls == 511, "Allocator positive controls failed")
    // A Swift-runtime allocation also must cross the executable interposer.
    try require(sjls_allocation_begin() == 1, "Nested measurement")
    let swiftControl = UnsafeMutableRawPointer.allocate(byteCount: 4096, alignment: 16)
    let swiftCounts = sjls_allocation_end()
    swiftControl.storeBytes(of: UInt8(7), as: UInt8.self); swiftControl.deallocate()
    try emit(["kind": "swift_runtime_positive_control", "counts": counters(swiftCounts), "passed": total(swiftCounts) > 0])
    try require(total(swiftCounts) > 0 && swiftCounts.overflow == 0, "Swift allocation was not observed")
    let cold = args[1] != "--matrix"
    let cases = try makeCases(root: URL(fileURLWithPath: args[2]), cold: cold,
                             adaptationManifest: args.count == 4 ? URL(fileURLWithPath: args[3]) : nil)
    var failures = 0, operations = 0
    var baselineCallbackCount: UInt64 = 0
    for c in cases {
        let modes = cold ? [args[1] == "--cold-inspect"] : [true, false]
        for inspect in modes {
            var configured = c
            if c.cancelDuringDecode && !inspect {
                // The successful baseline uses the same fixture and independent
                // count-only callback. Three checkpoints before completion fall
                // before the final row; verify that premise after return.
                try require(baselineCallbackCount > 3, "Missing cancellation baseline")
                configured.cancellation = baselineCallbackCount - 3
            }
            let result = try run(configured, inspect: inspect, first: operations == 0)
            if c.countCancellation && !inspect { baselineCallbackCount = result.callbackCount }
            if !result.passed { failures += 1 }
            operations += 1
        }
    }
    try emit(["kind": "summary", "cases": cases.count, "operations": operations, "failed_operations": failures,
        "scope": "Synchronous current-thread public qualified calls only. All observed allocator entries, including runtime/callback allocations on that thread, count. Preparation, owner destruction and reporting excluded; other threads, hidden libc allocations, direct mappings and stack storage unobserved."])
    if failures != 0 { exit(1) }
}
do { try main() }
catch { FileHandle.standardError.write(Data("QualifiedAllocationProbe failed: \(error)\n".utf8)); exit(1) }
