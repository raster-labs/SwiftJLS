# SwiftJLS `2.1.0` (`v2.1.0`) Release Qualification Record

**Release Version:** `2.1.0`  
**Git Tag:** `v2.1.0`  
**Release Date:** `16 November 2026`  
**Suite Policy & Common Contract Baseline:** `0.11.0` (`Documentation/COMMON_CONTRACT_SHA256.txt` verified `7/7` byte-identical)  
**Swift Toolchain Baseline:** `swift-tools-version: 6.2` manifest minimum; qualified primary `Swift 6.4` in `Swift 6` language mode with complete concurrency checking  
**Apple Deployment Minimum (`PLAT-01` / `PLAT-02`):** `macOS 26.0`, `iOS / iPadOS 26.0`, `tvOS 26.0`, `watchOS 26.0`, `visionOS 26.0`  
**Linux Baseline (`PLAT-01`):** `Ubuntu 24.04` (`x86_64` and `aarch64`)  
**Migration Predecessor Baseline:** `raster-labs/JLSwift` at `15aa75164145414f3d5ffb801401c52d40cc5bcc` (`v0.10.1` maintenance line; caller-workspace extension at `d17545284a23e93f3d884a18f1046c4e305daa35`)  
**Preceding Release Baseline:** `c49b5d6320e83d33d832afd3a3729e85abccce2d` (`v2.0.1`, MIT relicensing release over `v2.0.0` `48b65b291cd17d23d23f182db0bb48fb396c8319`)  
**Licence (`POL-07`):** **`MIT`** (`LICENSE` SHA-256 `9a6740d5798b34f0e390df81825748674ef4f00678a12b35cb23061684103363` and `NOTICE` SHA-256 `dbd05e5f8a4c0c7174126171c45c94fdea34a19ee7cd846e8c3646a0a3f7e9d3`, `Copyright (c) 2026 Raster Images Private Limited`)  

---

## 1. Executive Summary & Feature Scope (`2.1.0`)

SwiftJLS `2.1.0` (`v2.1.0`) is a feature and performance release of the standalone pure-Swift JPEG-LS (`ISO/IEC 14495-1` / `ITU-T T.87`) library and `swiftjls-cli` executable for the **Swift Image Compression Suite**, keeping published tags `v2.0.0` and `v2.0.1` immutable:

1. **64-Bit Bit-I/O, Branchless MED/LUT, SIMD Run-Scan & Near-Lossless Kernel Acceleration (`df1405b`, `1ba7e50`, `1512ab9`)**:
   - Introduces 64-bit buffered bit-stream reader/writer paths, branchless MED prediction and context-index lookup tables, vectorised run-length scanning and HP1/HP2/HP3 colour transforms, and an accelerated near-lossless (`NEAR > 0`, DICOM `.81`) sample quantisation/reconstruction kernel under `Backend.accelerated` (`ExecutionPolicy.automatic` / `.preferred(.accelerated)` / `.required(.accelerated)`), while keeping `ExecutionPolicy.scalarCPU` reference execution intact.
2. **Bounded Multi-Worker `ILV=0` & `DRI` Restart-Segment Parallelism (`BoundedParallelPool`, `df1405b`, `1ba7e50`, `1512ab9`, `eb01686`)**:
   - Parallelises non-interleaved (`ILV=0`) component planes (including multi-worker RGB planarisation/interleaving with padded odd widths) and restart-interval (`DRI`) row bands across `ResourceLimits.maximumWorkers`, with cooperative async cancellation bridging, strict scalar worker clamping, and zero-hop synchronous `encodeSynchronously` / `decodeSynchronously` entry points.
   - Adds extreme `NEAR=255` 16-bit and padded odd-width `ILV=0` RGB 1-worker vs multi-worker bit-exact parity and run-mode checkpoint regression coverage.
3. **Version & CLI Promotion (`2.1.0` / `v2.1.0`)**:
   - Promotes `VERSION`, `swiftjls-cli` (`Sources/SwiftJLSCLI/main.swift`), and the section 1 manual (`ManPages/swiftjls-cli.1`) to `2.1.0` (`v2.1.0`).

---

## 2. Executed Gates on the `2.1.0` Release Candidate

| Gate | Command / Evidence | Result |
| --- | --- | --- |
| **Shared contract SHA-256 manifest** | `(cd Documentation && shasum -a 256 -c COMMON_CONTRACT_SHA256.txt)` | **PASSED** (`7/7` shared contract files `OK`, contract `0.11.0`) |
| **Release-mode unit, parallel parity & regression suite** | `xcrun swift test -c release` | **PASSED** (`0` failures across all library, parallel parity, near-lossless `NEAR=255`, and odd-width `ILV=0` suites) |
| **CLI process, help & staged manual suite** | `python3 Scripts/test-cli.py --binary .build/release/swiftjls-cli --output /tmp/swiftjls-cli-v210` | **PASSED** (`103/103` process checks passed) |
| **CLI payload & stream suite** | `python3 Scripts/test-payload-cli.py --binary .build/release/swiftjls-cli --output /tmp/swiftjls-payload-v210.json` | **PASSED** (`73/73` payload checks passed) |
| **Release preparation & SemVer rehearsal** | `python3 Scripts/ReleasePreparation/prepare.py --local-only --output /tmp/swiftjls-prep-v210` | **PASSED** (local SemVer `2.1.0`, `README.md`/`MIGRATION.md` consumer examples, CLI build/process/payload, and tag preservation verified) |
| **Release preparation negative controls & provenance** | `python3 -m unittest discover -s Scripts/ReleasePreparation -p 'test_*.py' -v` & `provenance.py` | **PASSED** (`13/13` unit controls passed; `0` errors across `14` manifests and `2,819` fixture hash checks) |

---

## 3. Unexecuted and Deferred Gates (Disclosed Explicitly per `POL-08`)

1. **Physical Apple device execution (`iPhone`, `iPad`, `Apple Watch`, `Apple TV`, `Apple Vision Pro`)**: **Unexecuted** (no physical devices connected to the release host).
2. **Universal runtime/allocator/stack workspace totals**: Scoped source bounds and requested-heap accounting are enforced; universal allocator/runtime/stack peaks remain reported as `peakWorkspaceBytes = nil`.
3. **Deferred predecessor helpers (`POL-05`)**: `PNGSupport`, `TIFFSupport`, and extended predecessor CLI verbs remain in the `JLSwift` maintenance line by owner-approved disposition.
