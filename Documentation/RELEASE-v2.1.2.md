# SwiftJLS `2.1.2` (`v2.1.2`) Release Qualification Record

**Release Version:** `2.1.2`  
**Git Tag:** `v2.1.2`  
**Release Date:** `16 November 2026`  
**Suite Policy & Common Contract Baseline:** `0.11.0` (`Documentation/COMMON_CONTRACT_SHA256.txt` verified `7/7` byte-identical)  
**Swift Toolchain Baseline:** `swift-tools-version: 6.2` manifest minimum; qualified primary `Swift 6.4` in `Swift 6` language mode with complete concurrency checking  
**Apple Deployment Minimum (`PLAT-01` / `PLAT-02`):** `macOS 26.0`, `iOS / iPadOS 26.0`, `tvOS 26.0`, `watchOS 26.0`, `visionOS 26.0`  
**Linux Baseline (`PLAT-01`):** `Ubuntu 24.04` (`x86_64` and `aarch64`)  
**Migration Predecessor Baseline:** `raster-labs/JLSwift` at `15aa75164145414f3d5ffb801401c52d40cc5bcc` (`v0.10.1` maintenance line; caller-workspace extension at `d17545284a23e93f3d884a18f1046c4e305daa35`)  
**Preceding Release Baseline:** `8527cf4e047aa72ae308ee5b985cd6eba6d4580a` (`v2.1.1`)  
**Licence (`POL-07`):** **`MIT`** (`LICENSE` SHA-256 `9a6740d5798b34f0e390df81825748674ef4f00678a12b35cb23061684103363` and `NOTICE` SHA-256 `dbd05e5f8a4c0c7174126171c45c94fdea34a19ee7cd846e8c3646a0a3f7e9d3`, `Copyright (c) 2026 Raster Images Private Limited`)  

---

## 1. Executive Summary & Scope (`2.1.2`)

SwiftJLS `2.1.2` (`v2.1.2`) is a performance and workspace-qualification patch release over `v2.1.1` (`8527cf4`), keeping published tags `v2.1.0` and `v2.1.1` immutable:

1. **Zero Capture-Box Worker Clamping & Planar Band Helpers**:
   - Replaces mutable `var effectiveWorkers` captures in `ScalarCodec` and `ComponentCodec` with `BoundedParallelPool.clampedWorkerCount` and extracts static `deinterleaveBand` / `interleaveBand` helpers, eliminating per-decode/per-encode closure capture boxes.
2. **Cached Linux Processor Count (`BoundedParallelPool`)**:
   - Caches `ProcessInfo.processInfo.activeProcessorCount` once per process in `BoundedParallelPool` instead of re-reading `/sys/fs/cgroup/*` files on every parallel worker query in Linux containers.
3. **85/85 Hosted `heaptrack` Per-Operation Workspace Evidence (`43885275360`)**:
   - Completes `Scripts/StorageEvidence/measure-operation.py` attribution across function-signature-specialized control allocators, `JPEGLSBitSource`-generic interleaved `NativeUInt16Writer` buffers, and `libdispatch` `concurrentPerform` runtime frames (`allocations` and `qualified-caller-workspace` both green on `f1b6044`).
4. **Version & CLI Promotion (`2.1.2` / `v2.1.2`)**:
   - Promotes `VERSION`, `swiftjls-cli` (`Sources/SwiftJLSCLI/main.swift`), and `ManPages/swiftjls-cli.1` to `2.1.2` (`v2.1.2`).

---

## 2. Executed Gates on the `2.1.2` Release Candidate

| Gate | Command / Evidence | Result |
| --- | --- | --- |
| **Shared contract SHA-256 manifest** | `(cd Documentation && shasum -a 256 -c COMMON_CONTRACT_SHA256.txt)` | **PASSED** (`7/7` shared contract files `OK`, contract `0.11.0`) |
| **Release unit/parity suites** | `swift test --build-system native -c release` | **PASSED** (`163/163` tests in `29` suites) |
| **Hosted Linux `heaptrack` per-operation workspace matrix** | GitHub Actions run `43885275360` (`85/85` profiles + `qualified-caller-workspace`) | **PASSED** (`codec_heap_attribution_complete: true`) |
| **CLI process & payload suites** | `Scripts/test-cli.py` (`103` checks) & `Scripts/test-payload-cli.py` (`73` checks) | **PASSED** |
| **Release preparation unit controls** | `python3 -m unittest discover -s Scripts/ReleasePreparation` | **PASSED** (`13/13` tests) |

---

## 3. Unexecuted and Deferred Gates (Disclosed Explicitly per `POL-08`)

1. **Physical Apple device execution (`iPhone`, `iPad`, `Apple Watch`, `Apple TV`, `Apple Vision Pro`)**: **Unexecuted** (no physical devices connected to the release host).
2. **Universal runtime/allocator/stack workspace totals**: Scoped source bounds and requested-heap accounting are enforced; universal allocator/runtime/stack peaks remain reported as `peakWorkspaceBytes = nil`.
3. **Deferred predecessor helpers (`POL-05`)**: `PNGSupport`, `TIFFSupport`, and extended predecessor CLI verbs remain in the `JLSwift` maintenance line by owner-approved disposition.
