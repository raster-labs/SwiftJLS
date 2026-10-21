// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization
import Testing
import SwiftJLS

private enum LifecycleTestFailure: Error, Equatable { case fill, abort, validation }
private enum LifecycleSealAction: Sendable { case normal, failValidation, cancel }

private final class CountedLifecycleProvider: WritableImageStorage {
    private struct Counts: Sendable { var seals = 0; var aborts = 0 }
    private let counts = Mutex(Counts())
    private let owner: OwnedImageStorage
    private let failFirstAbort: Bool
    private let sealAction: LifecycleSealAction
    init(failFirstAbort: Bool = false, sealAction: LifecycleSealAction = .normal) throws {
        owner = try OwnedImageStorage(byteCount: 2)
        self.failFirstAbort = failFirstAbort; self.sealAction = sealAction
    }
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    var sealCount: Int { counts.withLock { $0.seals } }
    var abortCount: Int { counts.withLock { $0.aborts } }
    func reserveWrite() throws -> StorageWriteLease { try owner.reserveWrite() }
    func withUnsafeMutableBytes<R>(lease: StorageWriteLease,
        _ body: (UnsafeMutableRawBufferPointer) throws -> R) throws -> R {
        try owner.withUnsafeMutableBytes(lease: lease, body)
    }
    func finishAndSeal(lease: StorageWriteLease) throws -> any ReadOnlyImageStorage {
        counts.withLock { $0.seals += 1 }
        let sealed = try owner.finishAndSeal(lease: lease)
        switch sealAction {
        case .normal: return sealed
        case .failValidation: return FailingLifecycleReader(owner: sealed)
        case .cancel:
            withUnsafeCurrentTask { $0?.cancel() }
            return sealed
        }
    }
    func abortAndInvalidate(lease: StorageWriteLease) throws {
        let attempt = counts.withLock { $0.aborts += 1; return $0.aborts }
        if failFirstAbort && attempt == 1 { throw LifecycleTestFailure.abort }
        try owner.abortAndInvalidate(lease: lease)
    }
}

private struct FailingLifecycleReader: ReadOnlyImageStorage {
    let owner: any ReadOnlyImageStorage
    var byteCount: Int { owner.byteCount }
    var allocationID: UUID { owner.allocationID }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R {
        throw LifecycleTestFailure.validation
    }
}

@Suite("Destination lease completion")
struct DestinationLifecycleTests {
    @Test func successfulPublicationDoesNotAbortSealedOwner() throws {
        let provider = try CountedLifecycleProvider()
        let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1)
        var destination: ImageDestination? = try .init(descriptor: descriptor, storage: provider)
        let image = try #require(destination).writeUInt16 { _, _ in 65535 }
        #expect(throws: CodecError.self) { try destination?.writeUInt16 { _, _ in 0 } }
        destination = nil
        #expect(provider.sealCount == 1)
        #expect(provider.abortCount == 0)
        #expect(try image.sampleUInt16(x: 0, y: 0) == 65535)
    }

    @Test func abandonedDestinationAbortsReservation() throws {
        let provider = try CountedLifecycleProvider()
        let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1)
        var destination: ImageDestination? = try .init(descriptor: descriptor, storage: provider)
        #expect(destination != nil)
        destination = nil
        #expect(provider.sealCount == 0)
        #expect(provider.abortCount == 1)
        #expect(throws: CodecError.self) { try provider.reserveWrite() }
    }

    @Test(arguments: [false, true])
    func failedFillCleansUpAndRetriesOnlyFailedAbort(_ failFirstAbort: Bool) throws {
        let provider = try CountedLifecycleProvider(failFirstAbort: failFirstAbort)
        let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1)
        var destination: ImageDestination? = try .init(descriptor: descriptor, storage: provider)
        #expect(throws: LifecycleTestFailure.fill) {
            try destination?.write { _ in throw LifecycleTestFailure.fill }
        }
        #expect(provider.abortCount == 1)
        destination = nil
        #expect(provider.sealCount == 0)
        #expect(provider.abortCount == (failFirstAbort ? 2 : 1))
        #expect(throws: CodecError.self) { try provider.reserveWrite() }
    }

    @Test func failedSealedValidationStillAttemptsCleanup() throws {
        let provider = try CountedLifecycleProvider(sealAction: .failValidation)
        let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1)
        var destination: ImageDestination? = try .init(descriptor: descriptor, storage: provider)
        #expect(throws: LifecycleTestFailure.validation) { try destination?.writeUInt16 { _, _ in 1 } }
        #expect(provider.abortCount == 1)
        destination = nil
        #expect(provider.sealCount == 1)
        // The underlying owner rejects abort after sealing. Release must retry
        // rather than treating finishAndSeal alone as successful publication.
        #expect(provider.abortCount == 2)
    }

    @Test func cancellationDuringSealingStillAttemptsCleanup() async throws {
        let provider = try CountedLifecycleProvider(sealAction: .cancel)
        let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1)
        let operation = Task {
            let destination = try ImageDestination(descriptor: descriptor, storage: provider)
            return try destination.writeUInt16 { _, _ in 1 }
        }
        await #expect(throws: CancellationError.self) { try await operation.value }
        #expect(provider.sealCount == 1)
        #expect(provider.abortCount == 2)
    }
}
