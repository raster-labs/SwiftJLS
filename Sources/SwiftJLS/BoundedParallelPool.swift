// SPDX-License-Identifier: MIT
import Dispatch
import Foundation
import Synchronization

/// Bounded synchronous work-stealing helper used by `Backend.accelerated`
/// to parallelize independent JPEG-LS component scans (`ILV=0`) and `DRI`/`RSTm`
/// restart intervals without unbounded thread creation.
internal enum BoundedParallelPool {
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
        try Task.checkCancellation()
        let effectiveWorkers = min(count, workerCount(requested: workers))
        if effectiveWorkers <= 1 {
            for index in 0..<count {
                try Task.checkCancellation()
                try body(index)
            }
            return
        }

        let parentCancelled = Task.isCancelled
        let state = ParallelFailureState(initiallyCancelled: parentCancelled)
        let nextIndex = Atomic<Int>(0)

        DispatchQueue.concurrentPerform(iterations: effectiveWorkers) { _ in
            while true {
                if state.hasFailed { return }
                let idx = nextIndex.wrappingAdd(1, ordering: .relaxed).oldValue
                if idx >= count { return }
                if state.initiallyCancelled {
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

        try state.rethrowIfFailed()
        try Task.checkCancellation()
    }
}

private final class ParallelFailureState: Sendable {
    let initiallyCancelled: Bool
    private let failedFlag: Atomic<Bool>
    private let errorLock: Mutex<(any Error)?>

    init(initiallyCancelled: Bool) {
        self.initiallyCancelled = initiallyCancelled
        self.failedFlag = Atomic<Bool>(false)
        self.errorLock = Mutex(nil)
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
