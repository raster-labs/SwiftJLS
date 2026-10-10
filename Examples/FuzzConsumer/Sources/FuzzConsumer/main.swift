// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS

// Deterministic mutation campaign. Given the same sorted seed corpus and seed,
// the ordinal identifies the failing input; --last-input is written before every
// operation so watchdog/crash jobs retain the exact last candidate.
struct Generator {
    var state: UInt64 = 0x4a4c5301
    mutating func next(_ bound: Int) -> Int {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return Int((state >> 16) % UInt64(bound))
    }
}
struct CampaignFailure: Error { let reason: String }
guard CommandLine.arguments.count == 5,
      let seconds = Double(CommandLine.arguments[3]), seconds > 0,
      ["owned", "into", "inspect"].contains(CommandLine.arguments[2]) else {
    throw CampaignFailure(reason: "Usage: FuzzConsumer FIXTURES owned|into|inspect SECONDS LAST_INPUT")
}
let directory = URL(fileURLWithPath: CommandLine.arguments[1])
let entry = CommandLine.arguments[2]
let lastInput = URL(fileURLWithPath: CommandLine.arguments[4])
let seeds = try FileManager.default.contentsOfDirectory(at: directory, includingPropertiesForKeys: nil)
    .filter { $0.pathExtension == "jls" }.sorted { $0.lastPathComponent < $1.lastPathComponent }
    .map { try Data(contentsOf: $0) }
guard !seeds.isEmpty else { throw CampaignFailure(reason: "No seeds") }
let limits = try ResourceLimits(maximumCompressedBytes: 1024 * 1024, maximumDecodedBytes: 2 * 1024 * 1024,
    maximumWorkspaceBytes: 32 * 1024 * 1024, maximumPixels: 262144, maximumDimension: 70000,
    maximumMetadataBytes: 1024 * 1024, maximumICCBytes: 1024, maximumWorkers: 1,
    deadlineSeconds: 0.1, maximumMemoryBytes: 64 * 1024 * 1024)
let options = DecodeOptions(resourceLimits: limits)
let decoders = [try Decoder(), try Decoder(configuration: .init(codecOptions:
    .init(restartIntervalLines: 0, hpInterpretation: .legacyJLSwift, legacyMappingContinuations: true,
          legacyExtendedDimensions: true, legacyPresetDefaults: true))),
    try Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, mappingOutputPrecision: 16)))]
var generator = Generator()
var iterations = 0, accepted = 0, rejected = 0, decodeCalls = 0
let start = ProcessInfo.processInfo.systemUptime
var reported = start
while ProcessInfo.processInfo.systemUptime - start < seconds {
    var candidate = seeds[generator.next(seeds.count)]
    // Keep conformant seeds in the campaign; most mutations retain a valid
    // header so entropy and direct-output paths receive substantial exercise.
    switch iterations % 8 {
    case 0: break
    case 1:
        candidate = candidate.prefix(generator.next(candidate.count + 1))
    case 2:
        let start = min(25, candidate.count - 1)
        let at = start + generator.next(candidate.count - start)
        candidate[at] ^= UInt8(1 << generator.next(8))
    case 3:
        for _ in 0..<1 + generator.next(8) {
            candidate[generator.next(candidate.count)] = UInt8(generator.next(256))
        }
    case 4:
        let at = generator.next(candidate.count)
        candidate.insert(contentsOf: [255, UInt8(generator.next(256)), 255, 255], at: at)
    case 5:
        let at = generator.next(candidate.count)
        let length = generator.next(min(64, candidate.count - at) + 1)
        candidate.replaceSubrange(at..<(at + length), with: repeatElement(UInt8(0), count: length))
    case 6:
        candidate.append(contentsOf: [255, 217, 0])
    default:
        let at = generator.next(candidate.count)
        candidate.removeSubrange(at..<candidate.count)
        candidate.append(contentsOf: [255, 217])
    }
    try candidate.write(to: lastInput)
    do {
        let decoder = decoders[(iterations / 8) % decoders.count]
        switch entry {
        case "inspect": _ = try decoder.inspect(candidate, options: options)
        case "owned":
            decodeCalls += 1
            _ = try await decoder.decode(candidate, options: options)
        default:
            let info = try decoder.inspect(candidate, options: options)
            let destination = try ImageDestination.allocate(descriptor: info.descriptor, limits: limits)
            decodeCalls += 1
            let result = try await decoder.decode(candidate, into: destination, options: options)
            guard result.image.storage.allocationID == destination.storage.allocationID else {
                throw CampaignFailure(reason: "Destination allocation identity changed")
            }
        }
        accepted += 1
    } catch is CodecError { rejected += 1 }
    iterations += 1
    let now = ProcessInfo.processInfo.systemUptime
    if now - reported >= 5 {
        let record: [String: Any] = ["entry": entry, "seconds": now - start,
            "iterations": iterations, "decodeCalls": decodeCalls, "accepted": accepted, "rejected": rejected]
        let output = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
        try FileHandle.standardOutput.write(contentsOf: output + Data([10]))
        reported = now
    }
}
let record: [String: Any] = ["complete": true, "entry": entry,
    "seconds": ProcessInfo.processInfo.systemUptime - start, "iterations": iterations,
    "decodeCalls": decodeCalls, "accepted": accepted, "rejected": rejected,
    "generatorSeed": "0x4a4c5301", "seedCount": seeds.count]
let output = try JSONSerialization.data(withJSONObject: record, options: [.sortedKeys])
try FileHandle.standardOutput.write(contentsOf: output + Data([10]))
