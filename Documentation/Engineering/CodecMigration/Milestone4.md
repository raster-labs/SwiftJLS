> Historical 13 October evidence. See [the 14 October follow-up](Milestone4Followup.md) for the current source, measurements and remaining gates.

# Milestone 4 qualification follow-up — 13 October 2026

**Milestone 4 remains incomplete.** The available OS 26.0 simulator checks and powered representative benchmarks have now run. This task also improves component sample access and validation. Performance regressions, complete workspace accounting and required hardware admission remain open. Milestone 5 is deferred to the later owner task.

## Revisions and changes

Starting main is `571fd7c905f7ef70b4f494513ecf979d620bebd5` (merged PR 15). The current production/test checkpoint is `36fb97e0a654c0d18802b666df2b07d24cb0637a`, compared with pinned JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Its Sources tree is `7b4aecdbcf2dcdf4d41a1b96ed41b72486e29e2e`; Tests tree is `ab4b286d69b8a34c21ebaa0d24e13cdc4d7cf2c1`. See [draft PR 16](https://github.com/raster-labs/SwiftJLS/pull/16).

Component precision validation reuses the existing bounded scalar check for contiguous row samples. Full-width unsigned containers need no value-range scan; odd row strides and interleaved samples retain the general check. Packed rows use a precomputed addressing condition, avoiding division/remainder for every sample. The condition avoids multiplication overflow. Views remain scoped borrows, padding is not inspected as samples, unaligned byte access remains supported, and no sample owner or full-image copy is added. New tests cover meaningful-bit failures, byte order, odd offsets/strides, padding and cancellation across the 256-sample checkpoint.

The benchmark measures preparation, encode, decode and preparation plus encode from identical canonical UInt16 samples. Its validated `--cases` selector records the exact representative subset. The largest RGB fixture exceeded conservative default workspace admission; the development consumer now explicitly allows 1 GiB workspace and 2 GiB total memory. The resource profile is recorded and checked in raw output. This changes benchmark configuration only; library resource defaults are unchanged. Failed/default-limit evidence is preserved separately.

Suite policy 0.10.0, tools 6.2 minimum, primary Swift 6.4, Swift 6 language mode and Apple OS 26.0 floors remain unchanged. Public API, package manifest, fixtures, seven common documents and `VERSION` (`1.1.0-dev.2`) are unchanged. No release, tag or consumer cutover is performed.

## Current-source verification

Local tests use Apple Swift 6.4 (`swiftlang-6.4.0.34.1`) on Mac16,5, M4 Max, 64 GiB, macOS 27.0.1. Apple consumers use Xcode 27.0 (27A266a), SDK 27.0 and deployment targets 26.0. [The evidence manifest](results/milestone4-powered-2026-10-13.json) records commands, hashes, logs and source scope.

| Check | Result at `36fb97e` |
| --- | --- |
| Debug, release, AddressSanitizer, ThreadSanitizer | 82 declarations in 11 suites per run; zero failures/skips; all exit 0 |
| CLI | 73 payload checks and 103 process/help/manual/staged-install checks pass |
| Standalone public API consumer | Passes padded 12-bit sample and destination-identity checks |
| Runner controls | 17 positive/negative controls pass |
| Hosted PR checks | All 17 pass, including independent CharLS, Linux 6.2/6.4 on both architectures, Apple/Intel macOS, four Apple SDKs, Watch arm64_32, storage/copy controls and benchmark smoke |
| Local Apple builds | Four signed simulator consumers and Watch arm64_32 module compile |
| Exact OS 26.0 runtimes | iPhone 17 Pro, iPad Pro 13-inch (M5), Apple TV 4K (3rd generation), Apple Vision Pro and Apple Watch Series 11 (46mm) consumers pass |
| Exact OS 26.0 concurrent resources | Four non-Watch profiles each pass 32 scalar/RGB NEAR 0/3 transactions; supplied destination identity preserved, zero reported supplied pixel allocations/copy bytes |
| Powered release comparisons | 24 scalar and 39 representative RGB cases; four alternating blocks, five warm-ups and five observations per producer/block, giving 20 observations per operation/producer/case |

The simulator runtime builds are iOS/iPadOS 23A343, tvOS 23J352, visionOS 23M336 and watchOS 23R353, all version 26.0. Watch uses its bounded consumer, including resource rejection and cancellation; the four-worker workload is not physical Watch evidence. The native host remains macOS 27.0.1.

Tests explicitly load the Command Line Tools Testing macro plugin with the default Swift Build engine. Earlier discovery failures, battery-powered smoke data, original OS 27 checks and the first OS 26 checks remain in their dated manifests. They are not relabelled as current-source results. The fresh [one-hour-per-entry ASan mutation campaign](https://github.com/raster-labs/SwiftJLS/actions/runs/38388412648) passes at `36fb97e` using Swift 6.4 release with AddressSanitizer and all 981 seeds. Owned decode completes 5,562,534 mutations; caller-destination entry completes 7,165,773 mutations (2,403,971 decode calls); inspection completes 4,559,697 mutations. Each runs at least 3,600 seconds, exits 0 and has empty sanitizer stderr. Raw heartbeats, final reports, log and last-input hashes are retained in the evidence manifest; sanitizer RSS is not ordinary workspace telemetry. All 16 checks also pass on documentation checkpoint `f09b333`, whose Sources and Tests trees are identical to `36fb97e`.

## Performance and allocation findings

[The powered performance report](PoweredPerformance.md) records the selected cases, raw observations, paired ratios, conditions and residual regressions. The owner chose representative larger images instead of the full 144-case RGB grid. All 36 RGB combinations at 512×512 plus three larger cases are measured on the final binary. Focused comparisons with the preceding SwiftJLS source show lower component latency, but do not establish parity with JLSwift. No >5% regression is silently accepted.

Power is no longer the blocker. Runs used AC power with thermal/load/memory snapshots. Normal workstation background activity remained; the first final-RGB load average was elevated after compilation, although its sampled CPU was mostly idle. These limitations prevent a blanket isolated-hardware qualification claim. Source preparation is reported separately because predecessor validation occurs during image construction while SwiftJLS checks borrowed samples during encode.

Current hosted heap evidence records 5,521 allocations, 15,200,678 bytes peak requested heap, 32 intentional owned-decoder pixel allocations and 36 caller pixel owners in the concurrent workload. Codec nonpixel heap peaks at 3,491,558 bytes and includes compressed data and metadata. Group peaks occur at different instants and must not be summed. The ten scoped copy-probe routes report zero intercepted source-copy bytes, while their injected controls detect the expected copies; a separate allocator mutation detects ten injected sample arrays. These are scoped observations, not a complete heap/stack census. The hosted merge commit `4a982ddaf67ed09024e08c77e8985a14ebb70179` has the same Sources and Tests trees as `36fb97e`.

The earlier successful Instruments trace remains historical: a debug-signed copy of the prior release benchmark recorded allocations after ordinary attach failed. Setup and multiple encode/decode boundaries share that process, some symbols are unresolved, and it does not close per-operation workspace accounting. See [the earlier Xcode evidence](results/milestone4-xcode-2026-10-13.json).

## Gates still open

| Gate | Remaining evidence |
| --- | --- |
| PERF-01..03 | Resolve measured latency regressions or record an explicit owner-approved correctness/safety cost and baseline; repeat affected cases under sufficiently controlled conditions. Representative powered data is now available. |
| Per-operation workspace | Separate algorithm workspace, compressed buffers, metadata, runtime and stack storage. `peakWorkspaceBytes` remains unknown; process RSS and heap groups do not replace it. |
| Native macOS minimum | Exact native macOS 26.0 execution is not established by this macOS 27.0.1 host. The current hosted Apple Silicon job reports macOS 26.6.2 (25G83), so it also does not establish exact 26.0. |
| Physical-device admission | The user confirmed no physical devices are available. Required non-Watch hardware/provisioning is unavailable/unexecuted. Physical Watch retains its task exclusion and remains unexecuted. |

These are incomplete requirements, not approved waivers. Milestone 5, reporting/support-policy setup, stable publication and programme rollout remain deferred.
