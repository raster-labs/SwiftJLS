// SPDX-License-Identifier: MIT
import Foundation

/// Runtime availability and test-simulation hook for the CPU SIMD + multi-worker
/// accelerated backend (`Backend.accelerated`).
package enum AccelerationRuntime {
    @TaskLocal package static var forceUnavailable: Bool = false

    package static var isAvailable: Bool {
        !forceUnavailable
    }

    @discardableResult
    package static func withSimulatedUnavailable<R>(
        _ body: () throws -> R
    ) rethrows -> R {
        try $forceUnavailable.withValue(true, operation: body)
    }

    internal static func resolve(policy: ExecutionPolicy) throws -> (backend: Backend, fallbackReason: String?) {
        let available = isAvailable
        switch policy {
        case .scalarCPU, .preferred(.scalarCPU), .required(.scalarCPU):
            return (.scalarCPU, nil)
        case .automatic:
            return available ? (.accelerated, nil) : (.scalarCPU, nil)
        case .preferred(.accelerated):
            if available {
                return (.accelerated, nil)
            }
            return (.scalarCPU, "Acceleration unavailable; scalar CPU selected.")
        case .required(.accelerated):
            guard available else {
                throw CodecError(.backendUnavailable, "No accelerated backend is implemented.")
            }
            return (.accelerated, nil)
        }
    }
}
