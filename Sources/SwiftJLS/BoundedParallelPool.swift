// SPDX-License-Identifier: MIT
import Dispatch
import Foundation
import Synchronization

internal final class OperationCancellationToken: Sendable {
    private let cancelledFlag = Atomic<Bool>(false)

    internal init() {}

    internal func cancel() {
        cancelledFlag.store(true, ordering: .releasing)
    }

    internal var isCancelled: Bool {
        cancelledFlag.load(ordering: .acquiring)
    }
}

/// Bounded synchronous work-stealing helper used by `Backend.accelerated`
/// to parallelize independent JPEG-LS component scans (`ILV=0`) and `DRI`/`RSTm`
/// restart intervals without unbounded thread creation.
internal enum BoundedParallelPool {
    @TaskLocal internal static var activeCancellation: OperationCancellationToken?

    internal static func withTaskCancellationBridge<R: Sendable>(
        _ body: () throws -> R
    ) async throws -> R {
        try Task.checkCancellation()
        let token = OperationCancellationToken()
        return try await withTaskCancellationHandler {
            if Task.isCancelled {
                token.cancel()
                throw CancellationError()
            }
            return try Self.$activeCancellation.withValue(token) {
                try body()
            }
        } onCancel: {
            token.cancel()
        }
    }

    @inline(__always)
    internal static func checkCancellation() throws {
        if Task.isCancelled { throw CancellationError() }
        if let token = activeCancellation, token.isCancelled {
            throw CancellationError()
        }
    }

    internal static func workerCount(requested: Int) -> Int {
        let hw = max(1, ProcessInfo.processInfo.activeProcessorCount)
        return max(1, min(requested, hw))
    }

    internal static func forEach(
        count: Int,
        workers: Int,
        body: @Sendable (Int) throws -> Void
    ) throws {
        guard count > 0 else { return }
        try checkCancellation()
        let effectiveWorkers = min(count, workerCount(requested: workers))
        if effectiveWorkers <= 1 {
            for index in 0..<count {
                try checkCancellation()
                try body(index)
            }
            return
        }

        let token = activeCancellation
        let parentCancelled = Task.isCancelled || (token?.isCancelled ?? false)
        let state = ParallelFailureState(initiallyCancelled: parentCancelled, token: token)
        let nextIndex = Atomic<Int>(0)

        DispatchQueue.concurrentPerform(iterations: effectiveWorkers) { _ in
            Self.$activeCancellation.withValue(token) {
                while true {
                    if state.hasFailed { return }
                    let idx = nextIndex.wrappingAdd(1, ordering: .relaxed).oldValue
                    if idx >= count { return }
                    if state.isCancelled {
                        state.record(CancellationError())
                        return
                    }
                    do {
                        try body(idx)
                    } catch {
                        state.record(error)
                        return
                    }
                }
            }
        }

        try state.rethrowIfFailed()
        try checkCancellation()
    }
}

private final class ParallelFailureState: Sendable {
    let initiallyCancelled: Bool
    let token: OperationCancellationToken?
    private let failedFlag: Atomic<Bool>
    private let errorLock: Mutex<(any Error)?>

    init(initiallyCancelled: Bool, token: OperationCancellationToken?) {
        self.initiallyCancelled = initiallyCancelled
        self.token = token
        self.failedFlag = Atomic<Bool>(false)
        self.errorLock = Mutex(nil)
    }

    var isCancelled: Bool {
        initiallyCancelled || (token?.isCancelled ?? false)
    }

    var hasFailed: Bool {
        failedFlag.load(ordering: .acquiring)
    }

    func record(_ error: any Error) {
        errorLock.withLock { stored in
            if stored == nil {
                stored = error
                failedFlag.store(true, ordering: .releasing)
            }
        }
    }

    func rethrowIfFailed() throws {
        if let err = errorLock.withLock({ $0 }) {
            throw err
        }
    }
}

internal final class ChunkOutputCollector: Sendable {
    private let slots: Mutex<[[UInt8]]>

    internal init(count: Int) {
        self.slots = Mutex(Array(repeating: [], count: count))
    }

    internal func store(index: Int, bytes: [UInt8]) {
        slots.withLock { $0[index] = bytes }
    }

    internal func takeAll() -> [[UInt8]] {
        slots.withLock { current in
            let out = current
            current = []
            return out
        }
    }
}
