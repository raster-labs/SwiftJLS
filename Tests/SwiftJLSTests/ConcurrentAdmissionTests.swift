// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
import SwiftJLS

@Suite("Concurrent resource admission")
struct ConcurrentAdmissionTests {
    @Test func boundedColourAndNearLosslessWorkers() async throws {
        // Four fixed workers, eight frames each: the harness provides back-pressure.
        // ResourceLimits applies per operation, not as a process-wide scheduler.
        let names = ["p12-17x13-noise", "n3-p12-17x13-noise",
                     "c3-i1-p12-n0-17x13-noise", "c3-i2-p12-n3-17x13-noise"]
        let inputs = try names.map { try ComponentCodecTests().fixture($0, ext: "jls") }
        let limits = try ResourceLimits(maximumCompressedBytes: 1 << 20,
            maximumDecodedBytes: 1 << 20, maximumWorkspaceBytes: 4 << 20,
            maximumWorkers: 1, maximumMemoryBytes: 8 << 20)
        let rejected = try ResourceLimits(maximumWorkspaceBytes: 1, maximumWorkers: 1)
        let expired = try ResourceLimits(deadlineSeconds: Double.leastNonzeroMagnitude)
        try await withThrowingTaskGroup(of: Void.self) { group in
            for (worker, data) in inputs.enumerated() {
                group.addTask {
                    let helper = ComponentCodecTests()
                    let expected = try helper.fixture(names[worker], ext: worker == 0 ? "u16le" : "decoded.u16le")
                    let decoder = try Decoder()
                    let descriptor = try decoder.inspect(data).descriptor
                    let encoder = try Encoder(configuration: .init(
                        mode: worker == 1 || worker == 3 ? .nearLossless(maximumAbsoluteError: 3) : .lossless,
                        codecOptions: .init(restartIntervalLines: 0, interleaveMode: worker < 2 ? .none : .sample)))
                    for _ in 0..<8 {
                        let destination = try ImageDestination.allocate(descriptor: descriptor)
                        await #expect(throws: CodecError.self) {
                            try await decoder.decode(data, into: destination, options: .init(resourceLimits: rejected))
                        }
                        await #expect(throws: CodecError.self) {
                            try await decoder.decode(data, into: destination, options: .init(resourceLimits: expired))
                        }
                        let decoded = try await decoder.decode(data, into: destination, options: .init(resourceLimits: limits))
                        #expect(decoded.image.storage.allocationID == destination.storage.allocationID)
                        #expect(decoded.report.pixelAllocationCount == 0 && decoded.report.copyEvents.isEmpty)
                        try helper.check(decoded.image, against: expected, maximumError: 0, padding: false)
                        let encoded = try await encoder.encode(decoded.image, options: .init(resourceLimits: limits))
                        let roundtrip = try await decoder.decode(encoded.data, options: .init(resourceLimits: limits))
                        try helper.check(roundtrip.image, against: expected, maximumError: worker == 1 || worker == 3 ? 3 : 0, padding: false)
                        let cancelled = Task {
                            withUnsafeCurrentTask { $0?.cancel() }
                            return try await decoder.decode(data, options: .init(resourceLimits: limits))
                        }
                        await #expect(throws: CancellationError.self) { try await cancelled.value }
                    }
                }
            }
            try await group.waitForAll()
        }
    }
}
