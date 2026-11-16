# SwiftJLS `2.1.1` (`v2.1.1`) Release Qualification Record

**Release Version:** `2.1.1`  
**Git Tag:** `v2.1.1`  
**Release Date:** `16 November 2026`  
**Suite Policy & Common Contract Baseline:** `0.11.0` (`Documentation/COMMON_CONTRACT_SHA256.txt` verified `7/7` byte-identical)  
**Swift Toolchain Baseline:** `swift-tools-version: 6.2` manifest minimum; qualified primary `Swift 6.4` in `Swift 6` language mode with complete concurrency checking  
**Apple Deployment Minimum (`PLAT-01` / `PLAT-02`):** `macOS 26.0`, `iOS / iPadOS 26.0`, `tvOS 26.0`, `watchOS 26.0`, `visionOS 26.0`  
**Linux Baseline (`PLAT-01`):** `Ubuntu 24.04` (`x86_64` and `aarch64`)  
**Migration Predecessor Baseline:** `raster-labs/JLSwift` at `15aa75164145414f3d5ffb801401c52d40cc5bcc` (`v0.10.1` maintenance line; caller-workspace extension at `d17545284a23e93f3d884a18f1046c4e305daa35`)  
**Preceding Release Baseline:** `a96ae9ca7c3582db2ce0e855ebfb7acffb147c05` (`v2.1.0`)  
**Licence (`POL-07`):** **`MIT`** (`LICENSE` SHA-256 `9a6740d5798b34f0e390df81825748674ef4f00678a12b35cb23061684103363` and `NOTICE` SHA-256 `dbd05e5f8a4c0c7174126171c45c94fdea34a19ee7cd846e8c3646a0a3f7e9d3`, `Copyright (c) 2026 Raster Images Private Limited`)  

---

## 1. Executive Summary & Scope (`2.1.1`)

SwiftJLS `2.1.1` (`v2.1.1`) is a qualification and toolchain patch release over `v2.1.0` (`a96ae9c`), keeping published tag `v2.1.0` immutable:

1. **`Swift 6.2` Manifest-Minimum Test Compilation**:
   - Decomposes the `writeUInt16` test generator closure in `Tests/SwiftJLSTests/ParallelAccelerationTests.swift` with explicit types so `Swift 6.2.4` (`swift:6.2-noble`) compiles the test target cleanly without expression type-check timeouts.
2. **Explicit `swiftc` `watchOS` & `visionOS` Qualification**:
   - Adds `-package-name swiftjls` to explicit `xcrun swiftc` library compilation steps in `.github/workflows/contract.yml`, `.github/workflows/apple-runtime.yml`, and `.github/workflows/watch-device.yml` for `xrsimulator` and `arm64_32-apple-watchos26.0`.
3. **Complete Per-Operation Heaptrack Workspace Attribution**:
   - Captures `OperationCancellationToken` on `CodecBudget` at operation start, removes redundant GCD worker-thread `TaskLocal` re-binding in `BoundedParallelPool.forEach`, routes accelerated planar/predictor/schedule buffers through non-inlined helpers, and attributes one-time `TaskLocal` singletons and parallel control/workspace stacks in `Scripts/StorageEvidence/measure-operation.py`.
4. **Version & CLI Promotion (`2.1.1` / `v2.1.1`)**:
   - Promotes `VERSION`, `swiftjls-cli` (`Sources/SwiftJLSCLI/main.swift`), and `ManPages/swiftjls-cli.1` to `2.1.1` (`v2.1.1`).

---

## 2. Executed Gates on the `2.1.1` Release Candidate

| Gate | Command / Evidence | Result |
| --- | --- | --- |
| **Shared contract SHA-256 manifest** | `(cd Documentation && shasum -a 256 -c COMMON_CONTRACT_SHA256.txt)` | **PASSED** (`7/7` shared contract files `OK`, contract `0.11.0`) |
| **Debug & Release unit/parity suites (`< 50 ms` type-check)** | `swift build --build-tests -Xswiftc -Xfrontend -Xswiftc -warn-long-expression-type-checking=50` & `swift test -c release` | **PASSED** (`163/163` tests in `29` suites) |
| **`watchOS` (`arm64_32`) & `visionOS` (`xrsimulator`) `swiftc` qualification** | Direct `xcrun swiftc -package-name swiftjls` library + module builds | **PASSED** |
| **Workspace replay & profile runner negative controls** | `measure-operation.py --self-test`, `run-workspace-profiles.py --self-test`, and `17-1-0-encode` `heaptrack` replay | **PASSED** (`codec_heap_attribution_complete: true`) |
| **CLI process & payload suites** | `Scripts/test-cli.py` (`103` checks) & `Scripts/test-payload-cli.py` (`73` checks) | **PASSED** |
| **Release preparation & provenance** | `prepare.py --local-only`, `test_*.py`, and `provenance.py` (`2,819` fixture hashes) | **PASSED** |

---

## 3. Unexecuted and Deferred Gates (Disclosed Explicitly per `POL-08`)

1. **Physical Apple device execution (`iPhone`, `iPad`, `Apple Watch`, `Apple TV`, `Apple Vision Pro`)**: **Unexecuted** (no physical devices connected to the release host).
2. **Universal runtime/allocator/stack workspace totals**: Scoped source bounds and requested-heap accounting are enforced; universal allocator/runtime/stack peaks remain reported as `peakWorkspaceBytes = nil`.
3. **Deferred predecessor helpers (`POL-05`)**: `PNGSupport`, `TIFFSupport`, and extended predecessor CLI verbs remain in the `JLSwift` maintenance line by owner-approved disposition.
