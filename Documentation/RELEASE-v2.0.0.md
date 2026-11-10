# SwiftJLS `2.0.0` (`v2.0.0`) Release Qualification Record

**Release Version:** `2.0.0`  
**Git Tag:** `v2.0.0`  
**Release Date:** `6 November 2026`  
**Suite Policy & Common Contract Baseline:** `0.10.0` (`Documentation/COMMON_CONTRACT_SHA256.txt` verified `7/7` byte-identical)  
**Swift Toolchain Baseline:** `swift-tools-version: 6.2` manifest minimum; qualified primary `Swift 6.4` in `Swift 6` language mode with complete concurrency checking  
**Apple Deployment Minimum (`PLAT-01` / `PLAT-02`):** `macOS 26.0`, `iOS / iPadOS 26.0`, `tvOS 26.0`, `watchOS 26.0`, `visionOS 26.0`  
**Linux Baseline (`PLAT-01`):** `Ubuntu 24.04` (`x86_64` and `aarch64`)  
**Migration Predecessor Baseline:** `raster-labs/JLSwift` at `15aa75164145414f3d5ffb801401c52d40cc5bcc` (`v0.10.1` maintenance line; caller-workspace extension at `d17545284a23e93f3d884a18f1046c4e305daa35`)  
**Pre-release Engineering Baseline:** `23d35df4ac1055b1af2fd194f5bc7124fb4addea` (Merge pull request #18 over `a9bf9e95933fc8135bbcc3922d6ce831ddfe2057`, promoting `1.1.0-dev.2` to `2.0.0`)  
**Licence (`POL-07`):** `Apache-2.0` at `v2.0.0` publication; relicensed to **`MIT`** (`LICENSE` and `NOTICE`) on `10 November 2026` under contract `0.11.0`  

---

## 1. Executive Summary & Shipped Surface

SwiftJLS `2.0.0` (`v2.0.0`) is the first stable release of the standalone pure-Swift JPEG-LS (`ISO/IEC 14495-1` / `ITU-T T.87`) library and `swiftjls-cli` executable for the **Swift Image Compression Suite**:

1. **`SwiftJLS` Library Product**:
   - **Common Owning API (`API-01..13`, `MEM-01..13`)**: `Encoder`, `Decoder`, `EncoderConfiguration`, `DecoderConfiguration`, `EncodeOptions`, `DecodeOptions`, `ImageDescriptor`, `PlaneDescriptor`, `Image`, `ImageDestination`, `ReadOnlyImageStorage`, `WritableImageStorage`, `StorageWriteLease`, `ImageInfo`, `EncodedImage`, `DecodedImage`, `OperationReport`, `CodecCapabilities`, `ResourceLimits`, and `CodecError`.
   - **JPEG-LS Core & Profiles**: Unsigned `2..16`-bit sample precision in `8`-bit or `16`-bit storage (little-endian and big-endian), lossless (`NEAR == 0`) and bounded near-lossless (`NEAR 1..min(255, MAXVAL / 2)`) coding, `1..4` components across planar and pixel-interleaved layouts, non-interleaved (`.none`), line-interleaved (`.line`), and sample-interleaved (`.sample`) scans, explicit preset parameters (`MAXVAL`, `T1`, `T2`, `T3`, `RESET`), non-interleaved row restart intervals (`DRI`/`RSTm`) plus inactive-`DRI` interleaved compatibility, lossless `HP1`/`HP2`/`HP3` RGB colour transforms for full-range 8/16-bit samples, bounded `LSE` mapping tables and continuations, ordered `APP`/`COM` and `SPIFF` metadata preservation/discard, extended dimensions (`LSE` type 4), subsampled line decoding with declared plane sampling factors, and DICOM odd-length trailing zero-byte padding compatibility.
   - **Qualified Monochrome Caller-Workspace Profile**: `QualifiedMonochromeDecoder(profile: .jlswift0101)` providing synchronous, nonthrowing, zero-allocation caller-workspace decoding with checked budgets and deadlines.
2. **`swiftjls-cli` Executable Product & UNIX Manual (`ManPages/swiftjls-cli.1`)**:
   - Commands: `encode`, `decode`, `inspect`, `validate`, `capabilities`, `help`, and `version` over JPEG-LS codestreams and the bounded 2D unsigned 16-bit `NRRD` interchange profile (`CLI-04`), with atomic sibling output transactions, structured JSON telemetry, five diagnostic verbosity levels (`CLI-08`), and staged binary/manual installation via `Scripts/install-cli.sh` (`CLI-09`).

---

## 2. Verified Release Preconditions

| Precondition | Verification | Outcome |
| --- | --- | --- |
| **1. Continuous integration executes with non-zero steps** | Hosted GitHub Actions workflows (`contract.yml`, `interop.yml`, `apple-runtime.yml`, `watch-device.yml`) execute and pass on `16adfe06` / `2fc8bfe3` (`21/21` checks on engineering head, `16/16` required checks on closeout head) | **PASSED** |
| **2. Private vulnerability reporting enabled** | `gh api repos/raster-labs/SwiftJLS/private-vulnerability-reporting` checked 6 November 2026 | **PASSED** (`{"enabled": true}`) |
| **3. Explicit owner release assignment** | Owner release directive on 6 November 2026 authorising release `2.0.0` (`v2.0.0`) | **PASSED** |

---

## 3. Executed Gates on the `2.0.0` Release Candidate

| Gate | Command / Evidence | Result |
| --- | --- | --- |
| **Shared contract SHA-256 manifest** | `(cd Documentation && shasum -a 256 -c COMMON_CONTRACT_SHA256.txt)` | **PASSED** (`7/7` shared contract files `OK`, contract `0.10.0`) |
| **Release-mode unit & regression suite** | `xcrun swift test -c release` | **PASSED** (`157` tests in `28` suites passed in `0.840s`, `0` failures) |
| **CLI process, help & staged manual suite** | `python3 Scripts/test-cli.py --binary .build/release/swiftjls-cli --output /tmp/swiftjls-cli-v200` | **PASSED** (`103/103` process checks passed) |
| **CLI payload & stream suite** | `python3 Scripts/test-payload-cli.py --binary .build/release/swiftjls-cli --output /tmp/swiftjls-payload-v200.json` | **PASSED** (`73/73` payload checks passed) |
| **Independent package consumer** | `xcrun swift run -c release --package-path Examples/IndependentConsumer Consumer` | **PASSED** (native lossless coding, padded 12-bit samples, and destination identity verified) |
| **Release preparation negative controls** | `python3 -m unittest discover -s Scripts/ReleasePreparation -p 'test_*.py' -v` | **PASSED** (`13/13` unit controls passed) |
| **Source, fixture & licence provenance** | Retained in [Documentation/Engineering/ReleasePreparation/Provenance.md](Engineering/ReleasePreparation/Provenance.md) and [SBOM/README.md](Engineering/ReleasePreparation/SBOM/README.md) (`2,819` hash checks across `14` manifests, `7` contracts, `20` migration records, `57` predecessor checks, and `4` validated derived SBOMs) | **PASSED** |

---

## 4. Unexecuted and Deferred Gates (Disclosed Explicitly per `POL-08`)

Per suite policy (`POL-08` — *"A missing required environment is an unexecuted gate, not a pass"*):

1. **Physical Apple device execution (`iPhone`, `iPad`, `Apple Watch`, `Apple TV`, `Apple Vision Pro`)**: **Unexecuted** (no physical devices available; OS 26.0 simulator runtime consumers, Watch `arm64_32` device-SDK compilation, and hardware-virtualised native `macOS 26.0` `25A354` execution passed in Milestone 4/5 qualification).
2. **DICOMKit & VoxeliaValidation downstream cutover**: **Deferred** to separate consumer-repository tasks.
3. **Universal runtime/allocator/stack workspace totals**: Scoped source bounds and 89-profile requested-heap accounting are complete; universal allocator/runtime/stack peaks remain reported as `peakWorkspaceBytes = nil`.
4. **Deferred predecessor helpers (`POL-05`)**: `PNGSupport`, `TIFFSupport`, and extended predecessor CLI verbs (`Batch`, `Benchmark`, `Compare`, `Convert`, `Verify`, `Completion`, `BenchDICOM`) remain in the `JLSwift` maintenance line by owner-approved disposition.
