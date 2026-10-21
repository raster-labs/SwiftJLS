# Milestone 4 implementation and qualification — 14 October 2026

This is the historical `c330b731` checkpoint. The [21 October performance record](Milestone4Performance.md) covers final source `e6a6436` (including the earlier `bee49a2` changes) and its fresh validation. The measurements and unresolved findings below retain their original source scope.

This record covers the performance and workspace follow-up to [the earlier 14 October checkpoint](Milestone4Followup.md). Physical-device tests remain pending at the owner's request, and Milestone 5 remains deferred. The owner will verify GitHub CI and merge the feature branch; this task implements, validates locally, records evidence and pushes the branch.

## Source and behaviour

The pushed production checkpoint is `c330b731e250d6b4c054c1c6a91fa9894e32a8c3`. Earlier intermediate checkpoints `940da40b867cd14f7888492162c13e237609d991` and `4a18f3f111d02dd3213bb15095f752f2a2bdcfdd` retain their separate validation results. The pinned predecessor is JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; the preceding successor checkpoint is `8389b29003a187b6c54c9d1cad463758f531ca24`. Shared contracts, tools 6.2 minimum, Swift 6.4 primary, Apple OS 26.0 floors, the public API, resource defaults and version `1.1.0-dev.2` are unchanged.

The context model owns one packed `ManagedBuffer` through a noncopyable value. Its 365 integer-only records replace repeated array uniqueness checks in the hot loop; pointers remain inside synchronous borrows. Small run and component state uses fixed-capacity `InlineArray` storage. Lossless line scans reuse the scalar row kernel and contiguous scalar views where the declared strides permit them. Sparse/padded layouts retain their general accessors. SIMD prefix matching and narrow-precision validation use bounded, unaligned loads and preserve byte order and odd offsets.

The header directory scanner skips marker-free words and retains bytewise marker/stuffing handling. Deadline checks read the monotonic dispatch clock without converting a caller's potentially huge finite deadline to an integer. Run detection uses the equivalent unquantised near-gradient condition. These changes preserve checks on dimensions, storage, output limits, input precision, cancellation and deadlines. Lossless line encoding and line decode use bulk scan/fill chunks of at most 256 scalar samples, compared with the previous 64 component positions. These are per-bulk-operation bounds, not a claim of an identical global interval between polls. Row-entry admission covers the first lossless run scan. Decode skips its initial fill poll only for a column-zero run of at most 256 samples; long runs retain the post-parse poll. Later blocks and nonzero-column runs retain their checks. Cancellation regressions observe actual reads/writes and untouched destination samples.

Lossless precision validation is fused into regular and run-interruption coding. An exact run contains only the already-validated causal value, including at restart boundaries; near-lossless and HP retain their input prepass. Native-endian 16-bit views select sample format once while preserving unaligned loads and stores. The near-lossless row loop takes one scoped mutable borrow, and its unused outer gradient table is removed. Context index/sign calculation uses the equivalent bounded base-nine sum; error normalisation multiplies the sample difference by the sign before quantisation and modular reduction. Exhaustive context triples, odd-address storage, custom MAXVAL, invalid run positions, padding, byte order and header word boundaries have dedicated regressions.

The immutable parsed header reuses its admitted descriptor, rechecking each caller's limits and preserving rejection diagnostics. Its small descriptor arrays remain alive with the header and can share storage with the owned output; it retains no pixel buffers. Destination teardown tracks whether its write lease has already been completed, avoiding a redundant abort of sealed storage. Dedicated regressions cover stricter descriptor limits and successful, failed and abandoned destination lifetimes.

Frame, extended-dimension and scan admission use checked canonical UInt16 extent arithmetic instead of constructing temporary descriptors. Successful checks prove the same positive geometry, precision, dimensions, pixel count and decoded capacity. Any failed fast-path condition calls the original descriptor constructor, preserving its diagnostic and validation order. The final interpreted descriptor is still constructed at EOI. A differential regression covers 432 combinations, including native integer overflow, invalid dimensions/precision, exact capacity and simultaneously restrictive limits.

Descriptor construction also avoids a uniqueness Set for a singleton component list, materialised sampling-factor arrays, and storing an overlap range when there is only one plane. Nonempty/nonnegative component checks, multi-component uniqueness, mapped-component coverage, multi-plane overlap detection, checked arithmetic and failure ordering are unchanged. Invalid singleton, duplicate and out-of-range component mappings have regression coverage.

Diagnostic bulk-reader and forced-inlining variants gave mixed results and were rejected. A large inline context array caused a substantial slowdown and was also rejected. They are not shipping implementations or qualification results. The final small inline state and heap-owned context design have independent correctness and lifetime review.

## Local validation

At the production checkpoint, debug, release, AddressSanitizer and ThreadSanitizer each pass 108 declarations in 20 suites with zero failures or skips on the host and native arm64 macOS 26.0 guest. All five exact OS 26.0 simulator consumers, four resource profiles and SDK builds pass. The powered 63-case campaign is complete; decode regressions keep performance qualification open. These final unit builds explicitly use Swift 6.4 from `/Library/Developer/CommandLineTools`, including its testing macro library; they are not Xcode test builds. The host is Mac16,5 / M4 Max / 64 GiB, macOS 27.0.1. Apple SDK builds use Xcode 27.0 with deployment targets 26.0. Exact commands and toolchain selection are retained with the results; performance tables and the archived evidence below retain the unresolved findings.

| Check | Recorded result |
| --- | --- |
| CLI | Final source passes 73 payload and 103 process/help/manual/staged-install checks, including native macOS 26.0 execution |
| Apple compilation | Four simulator SDK libraries/consumers and Watch arm64_32 module pass on final source |
| Exact OS 26.0 simulators | iPhone, iPad, tvOS, visionOS and watchOS consumers pass on final source |
| Exact OS 26.0 resource workloads | Four non-Watch 32-transaction workloads pass on final source with full sample checks and supplied allocation identity |
| Native macOS 26.0 arm64 | All four 108-test configurations, both CLI suites, independent consumer and 32-frame resource workload pass on final source |
| Development workspace consumer | Earlier setup passes 61 additional local operation checks before Linux allocation collection; see the separately revisioned workspace evidence |

The exact native guest is macOS 26.0 (25A354), `arm64`, `VirtualMac2,1`, four CPUs and 8 GiB RAM. Tart 2.41.0 runs it through Apple hardware virtualisation using `ghcr.io/cirruslabs/macos-tahoe-base@sha256:6b01ed7bb644831fc3b5fdb297c8541bf7f032633d4ac5ac9b04affa163b3772`. It executes host-built Swift 6.4 binaries. This is native-architecture runtime evidence, without a guest-build, native Intel or physical-device claim. The VM was stopped before the powered performance measurements; its shutdown log is retained in the evidence archive.

The retained Xcode test-loader attempt at the earlier `940da40b867cd14f7888492162c13e237609d991` source passed all 103 declarations on the host, but no guest unit tests executed because its transferred package omitted `XCTest.framework`. That attempt is retained as a failed packaging/loader record. The explicit Command Line Tools rebuild supplied the successful `4a18f3` native test package, recorded independently of those host passes. The `c330b73` native cycle subsequently passed all four 108-declaration configurations and the CLI/consumer/resource checks. The intermediate `4a18f3` run passed all four 104-declaration configurations; neither earlier result is substituted for the final run.

Simulator builds remain iOS/iPadOS 23A343, tvOS 23J352, visionOS 23M336 and watchOS 23R353, all version 26.0. These consumers are distinct from the entire unit suite and physical-device qualification.

## Performance

The controlled 63-case representative campaign is complete for `c330b731e250d6b4c054c1c6a91fa9894e32a8c3` against the pinned JLSwift predecessor: 24 lossless scalar cases and the selected 39 RGB cases, including representative larger images. Each case has four alternating process blocks, five warmups and five timed iterations per producer per block, using release builds without sanitizers and owned decode. The native macOS 26.0 VM was stopped before timing; its [shutdown log](results/milestone4-final-2026-10-14/native-vm.log) is retained. The [condition record](results/milestone4-final-2026-10-14/powered/performance-disposition.json) contains 45 AC-power observations with no recorded thermal or performance warning: 43 around the main campaign and two around the separate deep-warm repeat. These samples do not establish thermal isolation on this developer workstation. Subsequent candidate timing was paused when the host reported battery power.

The following ranges are successor/predecessor pooled median latency ratios; lower is faster. Full per-case values, block ratios and byte counts are retained in the [campaign analysis](results/milestone4-final-2026-10-14/powered/combined-analysis.json) and [performance disposition](results/milestone4-final-2026-10-14/powered/performance-disposition.md).

| Operation | Scalar, 24 cases | RGB, 39 cases |
| --- | ---: | ---: |
| Encode | 0.3372–0.9764 | 0.0517–0.9466 |
| Decode | 0.4205–1.1694 | 0.1027–1.0906 |
| Prepare | 0.3247–1.0125 | 0.3230–0.4306 |
| Prepare + encode | 0.3243–1.0453 | 0.0752–0.8111 |

Five main-campaign decode observations exceed the 5% pooled reporting threshold. Their disposition remains unresolved; the two rows that exceed 5% in every paired block are distinguished below, and the other three are not treated as cleared merely because their blocks vary.

| Decode case | Predecessor → successor µs | Pooled ratio | Every paired block >1.05 |
| --- | ---: | ---: | --- |
| Scalar 37×23, 16-bit flat, NEAR 0 | 15.500 → 18.125 | 1.1694 | Yes |
| Scalar 37×23, 16-bit noise, NEAR 0 | 33.208 → 35.104 | 1.0571 | No |
| RGB 512×512, 12-bit noise, NEAR 3, sample interleave | 29,533.521 → 31,059.979 | 1.0517 | No |
| RGB 512×512, 12-bit ramp, NEAR 0, sample interleave | 12,347.875 → 13,466.437 | 1.0906 | Yes |
| RGB 512×512, 12-bit ramp, NEAR 3, sample interleave | 11,943.167 → 12,654.167 | 1.0595 | No |

No main-campaign encode, prepare or prepare-plus-encode pooled observation exceeds 5%, and no whole-process peak RSS observation exceeds 5%. RSS is not algorithm-workspace accounting. All 13 RGB encoded-size increases above 1% have an exact header-only explanation in the [untimed stream verification](results/milestone4-final-2026-10-14/diagnostics/rgb-size/summary.json): seven lossless cases add 44 bytes (34-byte SPIFF header and 10-byte end-directory marker); six NEAR 3 cases add 29 bytes (the same 44 bytes minus the predecessor's 15-byte default LSE). All 13 entropy streams are byte-identical, and complete streams become identical after removing only those exact segments. Sizes match the campaign, all 26 bidirectional cross-decodes pass sample checks, and all 52 export/decode commands exit zero. Binary hashes are checked against the frozen campaign. This is current-stream evidence, not an independent standards-oracle run; its incidental timings are not qualification evidence.

The separate [deep-warm tiny-image repeat](results/milestone4-final-2026-10-14/diagnostics/final-flat-deep-warm/summary.json) uses four alternating blocks with 20,000 warmups and 1,000 timed iterations. For 37×23 flat input, pooled encode/decode ratios are 1.0781/1.0924 at 12 bits and 1.3099/1.1478 at 16 bits. These observations remain unresolved and do not replace the main campaign. Earlier detached-task controls change the common caller context; both original asynchronous producer wrappers already execute on the generic executor. The later [preserved async-boundary controls](results/milestone4-final-2026-10-14/diagnostics/async-boundary/conclusions.md) give opposing signs across precisions and materially shift the synchronous control against the original producer. They establish no stable additive dispatch cost and justify no regression waiver.

An unpromoted native-sample decode candidate passes [110 release tests and eight focused AddressSanitizer tests](results/milestone4-final-2026-10-14/diagnostics/unpromoted-native-sample/expanded-test-results.json). It has no powered comparison yet and is not the shipping implementation or the source of the results above. Performance closure remains pending that comparison and resolution of the recorded regressions. Historical campaigns retain their own revisions. Physical-device testing remains pending, Milestone 5 remains deferred, and the owner retains GitHub CI verification and merge responsibility.

## Workspace accounting

See [the source inventory and measured allocation ledger](WorkspaceAccounting.md). It accounts separately for algorithm state, compressed buffers, pixels, metadata, descriptors and runtime storage across active public paths. Measured requested heap, source-derived bounds and sampled stack observations have different scopes. Unknown stack/allocator totals remain unknown; production `peakWorkspaceBytes` remains `nil`.

## Handoff and remaining scope

The owner performs CI verification and merging in GitHub. The branch push triggers the source-dependent workflows. The refreshed workspace artifact is collected here as a required measurement, separately from general CI verification. The owner must review the required checks on the final pushed head before merging; earlier passes remain scoped to their recorded revisions.

Representative physical iPhone/iPad and other required target-device admission remain unexecuted. Physical Watch is also pending. Milestone 5, stable tagging/publication, support/security-channel release decisions and consumer cutover remain outside this task.
