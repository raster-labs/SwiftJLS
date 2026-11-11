# SwiftJLS `2.0.1` (`v2.0.1`) Release Qualification Record

**Release Version:** `2.0.1`  
**Git Tag:** `v2.0.1`  
**Release Branch:** `codex/release-2.0.1`  
**Release Date:** `11 November 2026`  
**Suite Policy & Common Contract Baseline:** `0.11.0` (`Documentation/COMMON_CONTRACT_SHA256.txt` verified `7/7` byte-identical)  
**Swift Toolchain Baseline:** `swift-tools-version: 6.2` manifest minimum; qualified primary `Swift 6.4` in `Swift 6` language mode with complete concurrency checking  
**Apple Deployment Minimum (`PLAT-01` / `PLAT-02`):** `macOS 26.0`, `iOS / iPadOS 26.0`, `tvOS 26.0`, `watchOS 26.0`, `visionOS 26.0`  
**Linux Baseline (`PLAT-01`):** `Ubuntu 24.04` (`x86_64` and `aarch64`)  
**Migration Predecessor Baseline:** `raster-labs/JLSwift` at `15aa75164145414f3d5ffb801401c52d40cc5bcc` (`v0.10.1` maintenance line; caller-workspace extension at `d17545284a23e93f3d884a18f1046c4e305daa35`)  
**Preceding Release Baseline:** `48b65b291cd17d23d23f182db0bb48fb396c8319` (`v2.0.0`, merged PR #19 over `3144d8b15c4cb764b1f3a85b8806c36eded09165`)  
**Pre-release Engineering Baseline:** `a014bac5611ca654079c655e8fd88eb25caeab15` (Merge pull request #20 over `22efb678ce3d9a5f322e1170f43ab11e9f088088` and `e2eaa35149879f5bbc2ace21d91e3cb823cf9100`, restoring the `MIT` licence under contract `0.11.0`)  
**Licence (`POL-07`):** **`MIT`** (`LICENSE` SHA-256 `9a6740d5798b34f0e390df81825748674ef4f00678a12b35cb23061684103363` and `NOTICE` SHA-256 `dbd05e5f8a4c0c7174126171c45c94fdea34a19ee7cd846e8c3646a0a3f7e9d3`, `Copyright (c) 2026 Raster Images Private Limited`)  

---

## 1. Executive Summary & Patch Scope (`2.0.1`)

SwiftJLS `2.0.1` (`v2.0.1`) is a patch release of the standalone pure-Swift JPEG-LS (`ISO/IEC 14495-1` / `ITU-T T.87`) library and `swiftjls-cli` executable for the **Swift Image Compression Suite**, publishing the **MIT** relicensing under suite policy **0.11.0** (`POL-07`) while keeping published tag `v2.0.0` immutable:

1. **MIT Licence Restoration (`POL-07`, Contract `0.11.0`)**:
   - Restores the `MIT` licence (`Copyright (c) 2026 Raster Images Private Limited`) across `LICENSE`, `Documentation/SUITE_POLICY.md`, `Documentation/COMMON_CONTRACT_SHA256.txt`, all in-house Swift, C/C++, Python and shell `SPDX-License-Identifier: MIT` headers, synthetic fixture manifest declarations under `Tests/SwiftJLSTests/Fixtures/`, and release-preparation provenance/SBOM validation gates (`Scripts/ReleasePreparation/provenance.py`, `prepare.py`, and `SBOM/qualify.py`), while retaining `NOTICE` and preserving all third-party oracle notices and historical archives unchanged.
2. **CI Reference-Oracle Checkout Hardening**:
   - Enables Git long paths (`core.longpaths=true`) before Windows checkout in `.github/workflows/reference-oracle.yml`.
3. **Version & CLI Promotion (`2.0.1` / `v2.0.1`)**:
   - Promotes `VERSION`, `swiftjls-cli` (`Sources/SwiftJLSCLI/main.swift`), and the section 1 manual (`ManPages/swiftjls-cli.1`) to `2.0.1` (`v2.0.1`).
   - Preserves the complete common owning API (`Encoder`, `Decoder`, `ImageDescriptor`, `Image`, `ImageDestination`, `ReadOnlyImageStorage`, `WritableImageStorage`, `StorageWriteLease`) and the synchronous caller-workspace `QualifiedMonochromeDecoder(profile: .jlswift0101)` profile unchanged from `2.0.0`.

---

## 2. Verified Release Preconditions

| Precondition | Verification | Outcome |
| --- | --- | --- |
| **1. Continuous integration executes with non-zero steps** | Hosted GitHub Actions workflows execute and pass on `a014bac5` (PR #20) and the `codex/release-2.0.1` release candidate | **PASSED** |
| **2. Private vulnerability reporting enabled** | `gh api repos/raster-labs/SwiftJLS/private-vulnerability-reporting` checked 11 November 2026 | **PASSED** (`{"enabled": true}`) |
| **3. Explicit owner release assignment** | Owner release directive on 11 November 2026 authorising release `2.0.1` (`v2.0.1`) on preserved branch `codex/release-2.0.1` | **PASSED** |

---

## 3. Executed Gates on the `2.0.1` Release Candidate

| Gate | Command / Evidence | Result |
| --- | --- | --- |
| **Shared contract SHA-256 manifest** | `(cd Documentation && shasum -a 256 -c COMMON_CONTRACT_SHA256.txt)` | **PASSED** (`7/7` shared contract files `OK`, contract `0.11.0`) |
| **Release-mode unit & regression suite** | `xcrun swift test -c release` | **PASSED** (`157` tests in `28` suites passed, `0` failures) |
| **CLI process, help & staged manual suite** | `python3 Scripts/test-cli.py --binary .build/release/swiftjls-cli --output /tmp/swiftjls-cli-v201` | **PASSED** (`103/103` process checks passed) |
| **CLI payload & stream suite** | `python3 Scripts/test-payload-cli.py --binary .build/release/swiftjls-cli --output /tmp/swiftjls-payload-v201.json` | **PASSED** (`73/73` payload checks passed) |
| **Independent package consumer** | `xcrun swift run -c release --package-path Examples/IndependentConsumer Consumer` | **PASSED** (native lossless coding, padded 12-bit samples, and destination identity verified) |
| **Release preparation & SemVer rehearsal** | `python3 Scripts/ReleasePreparation/prepare.py --local-only --output /tmp/swiftjls-prep-v201` | **PASSED** (local SemVer `2.0.1`, CLI build/process/payload, and tag preservation verified) |
| **Release preparation negative controls** | `python3 -m unittest discover -s Scripts/ReleasePreparation -p 'test_*.py' -v` | **PASSED** (`13/13` unit controls passed) |
| **Source, fixture & licence provenance** | `python3 Scripts/ReleasePreparation/provenance.py --output /tmp/swiftjls-provenance-v201.json` | **PASSED** (`0` errors across `14` manifests, `2,819` fixture hash checks, `7` contracts, `20` migrated source MIT header checks, and `LICENSE`/`NOTICE` digests) |

---

## 4. Unexecuted and Deferred Gates (Disclosed Explicitly per `POL-08`)

Per suite policy (`POL-08` — *"A missing required environment is an unexecuted gate, not a pass"*):

1. **Physical Apple device execution (`iPhone`, `iPad`, `Apple Watch`, `Apple TV`, `Apple Vision Pro`)**: **Unexecuted** (no physical devices available; OS 26.0 simulator runtime consumers, Watch `arm64_32` device-SDK compilation, and hardware-virtualised native `macOS 26.0` `25A354` execution passed in Milestone 4/5 qualification).
2. **DICOMKit & VoxeliaValidation downstream cutover**: **Deferred** to separate consumer-repository tasks.
3. **Universal runtime/allocator/stack workspace totals**: Scoped source bounds and 89-profile requested-heap accounting are complete; universal allocator/runtime/stack peaks remain reported as `peakWorkspaceBytes = nil`.
4. **Deferred predecessor helpers (`POL-05`)**: `PNGSupport`, `TIFFSupport`, and extended predecessor CLI verbs (`Batch`, `Benchmark`, `Compare`, `Convert`, `Verify`, `Completion`, `BenchDICOM`) remain in the `JLSwift` maintenance line by owner-approved disposition.
