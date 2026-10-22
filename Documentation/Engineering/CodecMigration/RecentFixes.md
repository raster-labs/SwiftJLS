# JLSwift maintenance-fix follow-up — 22 October 2026

This owner-assigned follow-up compares JLSwift `d17545284a23e93f3d884a18f1046c4e305daa35` with SwiftJLS branch base `62309d3c59b04c5896d6ea076aae5ce06f5f33e3`. It addresses the four differences found in the read-only audit of predecessor PRs 125/126 and earlier marker-fill handling. Suite policy 0.10.0, Swift tools 6.2, primary Swift 6.4 and Apple OS 26 deployment floors remain unchanged.

## Implemented changes

| Audit finding | Follow-up |
| --- | --- |
| Leading `FF` marker fill before SOI was rejected | Accept bounded fill while retaining input-relative offsets, deadline/cancellation checks, complete-stream validation and DICOM parity over the entire supplied codestream. |
| ICC descriptors were rejected even under explicit discard | Scalar and component encoding permit `.discardAncillary`, charge retained ICC against operation budgets, and read the original pixel owner. Preservation and ICC interpretation remain unsupported; no colour transform is inferred. |
| Synchronous inspection silently ignored progress | Reject a supplied progress callback with `unsupportedFeature` after existing input/backend admission, before parsing or invoking it. Async encode/decode callbacks retain their existing contract. |
| No caller-scratch nonthrowing decoder | Add the explicitly selected, advanced synchronous `QualifiedMonochromeDecoder` profile described in [its API guide](../../QualifiedMonochrome.md). The owning common API remains separate. |

The previously verified compressed/pixel/storage limits, scan coverage, sliced-input origin, destination reuse, metadata requirements, MAXVAL checks and lease protections remain load-bearing regressions. Disjoint mixed scans continue to use the existing common decoder; the predecessor's narrower scan restriction is not imposed on that working implementation.

## Validation

The [hashed evidence manifest](results/recent-fixes-2026-10-22.json) retains source identities, exact commands, outputs, failures and measurement boundaries. Final production files and tests are identified by SHA-256, independently of the later documentation commit.

| Check | Executed result |
| --- | --- |
| macOS 27.0.1 arm64, Swift 6.4 | 144 declarations in 27 suites pass separately in debug, release, AddressSanitizer and ThreadSanitizer; zero failures/skips. |
| Linux aarch64, Swift 6.4, Ubuntu 24.04.5 container | All 144 declarations pass in debug. |
| CLI and independent consumer | 73 payload and 103 process/manual checks pass; separate release consumer passes. |
| Apple compilation | Four simulator SDK libraries/consumers and Watch arm64_32 device module pass with OS 26 deployment targets. These are build checks, not current-source OS 26 runtime or physical-device evidence. |
| Ordinary-release allocation observer | 430 cases / 860 operations plus separate cold inspection and decode pass: 862 observed calls, zero observed allocator calls, correct outcomes/samples and intact input/output/scratch guards. All nine C allocator controls and the Swift allocation control pass in each process. |
| ASan mutations | Owned, supplied destination, inspect, qualified decode and qualified inspect each pass 60 seconds with 981 seeds, reconciled counts and empty sanitizer stderr. These short runs do not satisfy the one-hour release gate; CI retains 3,600 seconds per entry. |
| Contract identity | All seven common document hashes match; the package still has no production dependencies. |

Independent review checked raw-span lifetimes/overlap, complete-capacity admission, 32-bit arithmetic, bounded malformed Golomb/run codes, entropy termination, selected mapping failures and unknown marker rejection. Cancellation tests and the probe use an independent scalar token; they inspect partial output only after the call returns.

The probe initially found ten high-NEAR standard-oracle failures. Investigation established a compatibility difference: the pinned predecessor clamps implicit thresholds differently. Three representative original streams also fail in the exact predecessor, while explicit standard LSE presets make all ten checked streams match their unchanged CharLS samples. The observer therefore labels all 28 formula-selected affected rows as explicit-standard-preset inputs; original/adapted codestream and independent sample hashes are retained. It also checks four separate predecessor-generated fixtures, including high NEAR. Both unadapted failed matrices remain archived. No default/profile behaviour or sample oracle was weakened to turn a failure into a pass.

The caller payload is 144,864 bytes on the measured 64-bit ABI (137,968 bytes by the 32-bit layout formula). This is fixed reusable scratch, separate from borrowed encoded bytes and final UInt16 output. The observer covers exported Linux allocator entry points on the operation thread. Hidden allocator calls, direct mappings, other threads, stack/runtime costs and caller preparation are outside that observation; universal workspace totals remain unknown. The test-only adapter, C interposer and reference generators are not production dependencies.

The Mac initially switched to battery before timing. The later powered comparison below records the resumed work; the original validation manifest retains its historical battery state. Earlier source-pinned performance/workspace archives keep their original scope. Swift 6.2, other hosted architectures, current-source minimum-OS runtime qualification and the one-hour campaigns remain for CI/qualification; the owner verifies CI and merges.

## Powered maintenance comparison — 22 October

After power was restored, a separate [hashed comparison record](results/recent-fixes-powered-2026-10-22.json) compared pre-fix SwiftJLS `62309d3` with implementation `e66f7da`. Both immutable source snapshots were rebuilt using the same Swift 6.4 release toolchain and identical benchmark consumer, without the predecessor compilation flag. This measures the common owning APIs, not the new caller-workspace API, ICC-bearing encoding or inspection-specific latency.

Six scalar/RGB cases cover 37×23 and 512×512 images. Four alternating paired blocks supply five warm-ups and five timed observations per process: 20 samples per producer, case and operation. All processes validate complete reconstructed samples before timing, and encoded sizes match across revisions. Ratios below one favour the candidate:

| Case | Encode | Decode | Prepare | Prepare + encode | Maximum process RSS |
| --- | ---: | ---: | ---: | ---: | ---: |
| 37×23, 12-bit scalar noise | 0.791 | 0.980 | 0.967 | 0.857 | 1.026 |
| 37×23, 16-bit scalar flat | 0.970 | 0.958 | 1.015 | 1.011 | 1.021 |
| 512×512, 12-bit scalar noise | 1.034 | 1.009 | **1.140** | 1.043 | **1.159** |
| 512×512, 16-bit scalar flat | 0.902 | 0.956 | 0.981 | 0.990 | 0.958 |
| 512×512, 16-bit RGB noise, line | 0.997 | 1.009 | 0.915 | 0.999 | 0.948 |
| 512×512, 12-bit RGB ramp, sample | 0.958 | 0.973 | 0.957 | 0.956 | 1.011 |

The preparation and maximum-RSS flags triggered one fixed investigation: 16 direct paired blocks and eight interleaved same-candidate control pairs, using unchanged binaries. The repeat pooled encode/decode/preparation/combined ratios are **0.994 / 0.992 / 0.990 / 1.006**. The preparation slowdown did not recur in pooled results, although four of 16 individual preparation pairs exceed 1.05. All observations and paired spreads remain archived; the repeat does not replace the original data.

**Whole-process RSS remains inconclusive.** Its repeat maximum ratio is 1.012, but its median ratio is 1.051. The identical-candidate control median ratio is 0.944, showing process variability without proving its cause or waiving the finding. Preparation, descriptor, storage and benchmark sources are byte-identical between revisions; compiler layout and runtime effects are not thereby excluded. RSS is not a measurement of pure algorithm workspace.

All 194 condition observations report AC power and no recorded thermal/performance warning. System, application and VM activity remained visible, so this is a powered developer-workstation comparison, not idle isolation. Independent recomputation reconciles all 96 process records, schedules, source/binary identities and statistics. There is no population-equivalence, full performance-gate or Milestone 4 completion claim. The earlier short-decode findings remain pending.

## Qualification boundary

This follow-up does not close the earlier short-decode performance findings, universal workspace totals, physical-device admission or release requirements. The 21 October performance/workspace archives retain their exact source scope. Physical-device testing remains pending, Milestone 5 remains deferred, and the owner verifies CI and merges the pushed branch in GitHub.
