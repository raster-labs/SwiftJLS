// SPDX-License-Identifier: Apache-2.0
import Foundation
import Synchronization

/// An opaque lease value. Providers create a fresh token for each reservation and
/// compare it to their active token; allocation identity alone never grants access.
/// A token is Sendable but does not permit two simultaneous mutable borrows.
public struct StorageWriteLease: Sendable, Equatable, Hashable {
    private let nonce: UUID
    public init() { nonce = UUID() }
}

/// Implementers must retain sealed immutable storage for the full borrow lifetime.
/// Unsafe pointers must never escape the synchronous closure (including as its result).
/// Returning an escaped pointer is a caller error which Swift cannot prevent here.
public protocol ReadOnlyImageStorage: Sendable {
    var byteCount: Int { get }
    var allocationID: UUID { get }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R
}

/// Advanced providers own allocation retention and the shared lifecycle across all
/// wrappers/modules. Reject double reservation, overlapping/reentrant mutation,
/// forged/stale leases, read before seal and every write after seal/abort.
/// No pointer returned by an Array/Data borrow may be adopted as a storage owner.
public protocol WritableImageStorage: Sendable {
    var byteCount: Int { get }
    var allocationID: UUID { get }
    func reserveWrite() throws -> StorageWriteLease
    /// Pointer must not escape, be shared with concurrent work, or span `await`.
    func withUnsafeMutableBytes<R>(lease: StorageWriteLease,
        _ body: (UnsafeMutableRawBufferPointer) throws -> R) throws -> R
    func finishAndSeal(lease: StorageWriteLease) throws -> any ReadOnlyImageStorage
    func abortAndInvalidate(lease: StorageWriteLease) throws
}

/// A zero-initialised, independently owned allocation. The mutex protects the
/// array and lifecycle; no unsafe pointer is stored or marked Sendable.
/// An atomic admission gate rejects competing/reentrant access before the mutex.
/// A mutable borrow holds both until its synchronous closure returns or throws.
/// Sealing transfers the array reference to immutable storage without mutating or
/// cloning its contents. Sealed readers borrow concurrently from that immutable owner.
public final class OwnedImageStorage: WritableImageStorage, Sendable {
    public let byteCount: Int
    public let allocationID: UUID
    private enum Phase { case available, writing, sealed, invalid }
    private struct State: Sendable {
        var bytes: [UInt8]
        var phase: Phase = .available
        var lease: StorageWriteLease?
    }
    private let state: Mutex<State>
    private let operationActive = Atomic<Bool>(false)

    public init(byteCount: Int, limits: ResourceLimits = .default) throws {
        try Task.checkCancellation()
        guard byteCount > 0 else { throw CodecError(.invalidArgument, "Storage capacity must be positive.") }
        guard byteCount <= limits.maximumDecodedBytes, byteCount <= limits.maximumMemoryBytes else {
            throw CodecError(.resourceLimitExceeded, "Storage allocation exceeds the admission budget.")
        }
        self.byteCount = byteCount; self.allocationID = UUID()
        self.state = Mutex(State(bytes: [UInt8](repeating: 0, count: byteCount)))
    }

    private init(reservedByteCount byteCount: Int, allocationID: UUID, lease: StorageWriteLease) {
        self.byteCount = byteCount; self.allocationID = allocationID
        self.state = Mutex(State(
            bytes: [UInt8](repeating: 0, count: byteCount),
            phase: .writing,
            lease: lease
        ))
    }

    // Internal fresh-reserved constructor for `ImageDestination.allocate`.
    // Preserves pre-allocation cancellation and byteCount limit checks, creates
    // fresh allocation and lease UUIDs, and initialises the private state in
    // `.writing` before the storage reference can escape to any caller.
    static func allocateReserved(
        byteCount: Int,
        limits: ResourceLimits
    ) throws -> (storage: OwnedImageStorage, lease: StorageWriteLease) {
        try Task.checkCancellation()
        guard byteCount > 0 else { throw CodecError(.invalidArgument, "Storage capacity must be positive.") }
        guard byteCount <= limits.maximumDecodedBytes, byteCount <= limits.maximumMemoryBytes else {
            throw CodecError(.resourceLimitExceeded, "Storage allocation exceeds the admission budget.")
        }
        let allocationID = UUID()
        let lease = StorageWriteLease()
        let storage = OwnedImageStorage(
            reservedByteCount: byteCount,
            allocationID: allocationID,
            lease: lease
        )
        return (storage, lease)
    }

    public func reserveWrite() throws -> StorageWriteLease {
        try locked { state in
            guard state.phase == .available else {
                throw CodecError(.storageUnavailable, "Storage already has a writer or is sealed/invalid.")
            }
            let lease = StorageWriteLease()
            state.lease = lease; state.phase = .writing
            return lease
        }
    }

    public func withUnsafeMutableBytes<R>(lease: StorageWriteLease,
        _ body: (UnsafeMutableRawBufferPointer) throws -> R) throws -> R {
        try locked { state in
            try Self.check(lease, state)
            return try state.bytes.withUnsafeMutableBytes(body)
        }
    }

    public func finishAndSeal(lease: StorageWriteLease) throws -> any ReadOnlyImageStorage {
        try locked { state in
            try Self.check(lease, state)
            let sealed = SealedImageStorage(bytes: state.bytes, allocationID: allocationID)
            state.bytes = []
            state.lease = nil; state.phase = .sealed
            return sealed
        }
    }

    public func abortAndInvalidate(lease: StorageWriteLease) throws {
        try locked { state in
            try Self.check(lease, state)
            state.bytes = []
            state.lease = nil; state.phase = .invalid
        }
    }

    // Internal fresh-owned fill-and-seal helper for `Image.writeAdmittedOwned`.
    // Allocates one zero-initialised byte array, runs the synchronous fill borrow,
    // and returns an immutable `SealedImageStorage` with a fresh `allocationID`.
    // No mutable storage or destination owner escapes, and failed fills never publish.
    static func fillAndSealAdmittedOwned(
        byteCount: Int,
        limits: ResourceLimits,
        _ body: (UnsafeMutableRawBufferPointer) throws -> Void
    ) throws -> any ReadOnlyImageStorage {
        try Task.checkCancellation()
        guard byteCount > 0 else { throw CodecError(.invalidArgument, "Storage capacity must be positive.") }
        guard byteCount <= limits.maximumDecodedBytes, byteCount <= limits.maximumMemoryBytes else {
            throw CodecError(.resourceLimitExceeded, "Storage allocation exceeds the admission budget.")
        }
        let allocationID = UUID()
        var bytes = [UInt8](repeating: 0, count: byteCount)
        try Task.checkCancellation()
        try bytes.withUnsafeMutableBytes { rawBytes in
            guard rawBytes.count == byteCount else {
                throw CodecError(.storageUnavailable, "Provider returned inconsistent capacity.")
            }
            try body(rawBytes)
        }
        try Task.checkCancellation()
        return SealedImageStorage(bytes: bytes, allocationID: allocationID)
    }

    private static func check(_ lease: StorageWriteLease, _ state: borrowing State) throws {
        guard state.phase == .writing, state.lease == lease else {
            throw CodecError(.storageUnavailable, "Write lease is stale, foreign or unavailable.")
        }
    }

    private func locked<R>(_ body: (inout State) throws -> R) throws -> R {
        // Swift 6.2's Linux Mutex traps even on a same-thread try-lock. Admit
        // exactly one operation before touching it; callbacks therefore reject
        // re-entry without invoking the non-recursive mutex. The defer runs only
        // after withLock has released the state, including when the body throws.
        guard operationActive.compareExchange(
            expected: false, desired: true, ordering: .acquiring
        ).exchanged else {
            throw CodecError(.storageUnavailable, "A storage borrow is already active.")
        }
        defer { operationActive.store(false, ordering: .releasing) }
        return try state.withLock { state in try body(&state) }
    }
}

private final class SealedImageStorage: ReadOnlyImageStorage, Sendable {
    private let bytes: [UInt8]
    let allocationID: UUID
    var byteCount: Int { bytes.count }
    init(bytes: [UInt8], allocationID: UUID) {
        self.bytes = bytes; self.allocationID = allocationID
    }
    func withUnsafeBytes<R>(_ body: (UnsafeRawBufferPointer) throws -> R) throws -> R {
        try bytes.withUnsafeBytes(body)
    }
}
