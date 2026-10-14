# Milestone 4 performance and workspace follow-up — 14 October 2026

**Milestone 4 remains under qualification.** This record separates completed software checks from unresolved performance and physical-device gates. Milestone 5 remains deferred. Earlier evidence is retained in [the 13 October record](Milestone4.md).

## Source and implementation

The production/test checkpoint is `8389b29003a187b6c54c9d1cad463758f531ca24`: Sources tree `855b265e2856142095d4771efe10c64c5ed1e6e0`, Tests tree `f0bbfc902f4b284e7a2ea6cdfacf31392c1f525c`. The predecessor remains JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; starting main is `571fd7c905f7ef70b4f494513ecf979d620bebd5`. Suite policy 0.10.0, tools 6.2 minimum, Swift 6.4 primary, OS 26.0 floors, shared contracts, public API, production resource defaults and version `1.1.0-dev.2` are unchanged.

Lossless interleaved encoding now reads causal reconstructed neighbours directly from the source: reconstruction equals the source in this mode. Only near-lossless encoding retains predictor rows. Run detection scans four contiguous samples where layout permits, and bounded run fills avoid repeated nested-array copy-on-write checks. Strided views preserve byte order, padding and odd offsets; cancellation remains bounded. Packed comparison/fill tests cover these boundaries.

The bit writer is a private mutable value passed through synchronous kernels by `inout`. This removes per-word class-property exclusivity checks without disabling Swift exclusivity or output admission. Size checks now occur inside the kernel at the same cancellation checkpoints; each append still enforces its byte limit. Short Golomb words are emitted in one bounded write, with the original path retained for longer words. An independent bit-at-a-time reference checks stuffing, 1–32-bit writes and exact output limits.

Two diagnostic alternatives were not adopted: forcing additional sample-accessor inlining gave mixed encode/decode results, and a value-type reader did not consistently improve decode. Their observations remain diagnostic, separate from the final controlled comparison.

## Verification

Local debug, release, ASan and TSan each pass 84 declarations in 12 suites, with zero failures/skips at the checkpoint above. The host is Mac16,5 / M4 Max / 64 GiB, macOS 27.0.1; Apple Swift is 6.4 (`swiftlang-6.4.0.34.1`). Local Apple builds use Xcode 27.0 (27A266a), SDK 27.0 and deployment targets 26.0.

| Check | Current-source result |
| --- | --- |
| Debug / release / ASan / TSan | 84 declarations, 12 suites, zero failures/skips per run; all exit 0 |
| CLI | 73 payload and 103 process/help/manual/staged-install checks pass |
| Local Apple builds | Four simulator SDK libraries/consumers plus Watch arm64_32 module pass |
| Exact OS 26.0 simulator consumers | iPhone, iPad, tvOS, visionOS and watchOS pass |
| Exact OS 26.0 resource workloads | Four non-Watch profiles each pass 32 scalar/RGB NEAR 0/3 transactions; supplied destination identity preserved, zero reported supplied pixel allocations/copy bytes |
| Hosted checks | All 22 checks pass, including both Linux architectures/toolchains, native macOS Apple/Intel, independent CharLS, Watch architecture, storage/copy controls, measurement jobs and three mutation campaigns |
| One-hour ASan mutation campaign | Owned, supplied-destination and inspection campaigns each complete at least 3,600 seconds with 981 seeds, exit 0 and empty sanitizer stderr |
| Native macOS 26.0 arm64 | Exact 26.0 (25A354) guest passes all 84 declarations in release/debug/ASan/TSan, both CLI suites, the independent consumer and 32-frame resource workload |

Simulator runtime builds are iOS/iPadOS 23A343, tvOS 23J352, visionOS 23M336 and watchOS 23R353, each version 26.0. These are simulator consumers, not physical-device runs or the entire unit suite on every mobile platform. [Hosted contract results](https://github.com/raster-labs/SwiftJLS/actions/runs/38539561010) and [independent interoperability](https://github.com/raster-labs/SwiftJLS/actions/runs/38539560991) retain their platform scopes.

The [final-source one-hour mutation campaign](https://github.com/raster-labs/SwiftJLS/actions/runs/38539601828) completes 7,602,198 owned-decode mutations, 9,759,259 supplied-destination mutations (3,274,991 decode calls after inspection), and 8,186,499 inspections: 25,547,956 iterations in total. No sanitizer finding is reported. Sanitizer RSS is retained separately and is not ordinary-build workspace evidence. The earlier `68a286d` campaign is archived under its own source scope.

## Exact native macOS 26.0 execution

The guest reports macOS **26.0 (25A354)** and `arm64`, with model `VirtualMac2,1`, four CPUs and 8 GiB RAM. Tart 2.41.0 runs the arm64 OS through Apple hardware virtualisation on the M4 Max; this is native-architecture runtime evidence, not a physical-device or native Intel claim. The pinned image is `ghcr.io/cirruslabs/macos-tahoe-base@sha256:6b01ed7bb644831fc3b5fdb297c8541bf7f032633d4ac5ac9b04affa163b3772`.

Host-built Swift 6.4 binaries from the final source pass all four 84-declaration configurations with zero failures/skips. The independent Apple consumer, 73 payload CLI checks and 103 process/help/install/manual checks also pass. The ordinary-release resource consumer verifies all samples across 32 scalar/RGB NEAR 0/3 transactions, preserves supplied destination identity and reports zero supplied pixel allocations/copy bytes. These are execution results; no guest compilation or VM performance comparison is claimed.

The guest's version/architecture checks run before the suites. Binary/fixture hashes, commands, XML and stdout/stderr are retained in the evidence archive. Download retries, an SSH password-prompt matching failure and a subsequent connection attempt after the first driver exited and its guest was no longer reachable are preserved as setup failures. Correcting the prompt matcher and starting the VM independently unblocked the run; no codec change was needed. The VM was stopped after all checks passed.

## Performance

The owner-approved representative scope remains 24 scalar plus 39 RGB cases: every 512² RGB combination and three larger examples. Both consumers start from identical canonical samples. Each case retains four alternating blocks, five warm-ups and five observations per block/producer, preparation and directly measured preparation-plus-encode, encoded sizes, process RSS, median/p95/range and condition samples. The benchmark-only 1 GiB workspace / 2 GiB memory budget is unchanged.

The intermediate production checkpoint `68a286d` completed all 63 cases on AC power. It reduced the worst RGB encode ratio from the previous 15.531× to 3.276×, but retained repeated regressions. That intermediate result is not relabelled as evidence for the later value-writer checkpoint. A further five-case diagnostic comparison found approximately 17% lower scalar ramp encode latency with the value writer; this motivated the final repeated campaign.

All 24 scalar and 39 RGB cases complete successfully on the final source. Ratios are successor/predecessor median latency; lower is faster. The scalar overview excludes the six tiny 37×23 harness cases, which remain in the raw data. Repetition in all four paired blocks identifies consistent effects without pretending to be a confidence interval.

| Cases | Operation | Ratio range | Median >1.05 | All four blocks >1.05 |
| --- | --- | --- | --- | --- |
| 18 scalar | Encode | 0.784–1.476× | 9 | 8 |
| 18 scalar | Owned decode | 0.492–1.188× | 10 | 8 |
| 18 scalar | Preparation + encode | 0.369–0.939× | 0 | 0 |
| 39 RGB | Encode | 0.056–3.465× | 15 | 15 |
| 39 RGB | Owned decode | 0.124–1.655× | 26 | 26 |
| 39 RGB | Preparation + encode | 0.079–1.462× | 5 | 4 |

Preparation plus encode is faster in all 18 larger scalar cases in this campaign. Encode-only and decode regressions remain: the largest repeated added median costs are 99.3 ms for the largest noisy RGB decode, 70.6 ms for the larger near-lossless RGB decode, 29.8 ms for the largest 16-bit scalar-noise decode, and 22.2 ms for the largest flat RGB encode. The worst RGB encode ratio is now 3.465×; the historical 13 October campaign recorded 15.531×. These are separately dated campaigns, not an isolated causal estimate of one change.

The source still uses scoped raw-buffer/stride access and bounded resource/cancellation checks. The predecessor uses prepared contiguous sample owners, and some validation occurs during its preparation. Separate preparation measurements expose that difference but do not explain away all remaining costs. CPU sampling motivated the writer change; remaining decode and flat/strided encode costs require further investigation or an explicitly accepted measured trade-off. No latency waiver or new accepted baseline is recorded.

The final window runs 09:08–09:29 UTC on 14 October. All 42 condition samples report AC power and no recorded thermal/performance warnings. Sampled CPU idle ranges from 59.60% to 84.00%; one-minute load declines from 12.83 to 4.69. This task's download is paused, and no local compilation, sanitiser or profiler overlaps timed observations. Normal workstation activity and lightweight documentation/API work remain; this is monitored developer-hardware evidence, not an isolated laboratory. Raw timings, p95/spread, RSS, power/thermal/load and memory-pressure records are retained in [the evidence manifest](results/milestone4-followup-2026-10-14.json).

Encoded-size and header interpretation retain the earlier distinction: RGB SPIFF signalling is semantic metadata, and small streams can exceed percentage size thresholds. No size waiver is created by this campaign. Cross-codec sample correctness is separately checked by the independent CharLS workflow.


## Workspace accounting

A development-only consumer marks one encode, owned decode, caller-destination decode or inspection between explicit allocation markers. Setup stays live before the begin marker, results stay live through the end marker, and full sample verification follows it. The library has no instrumentation dependency.

Ordinary release Heaptrack 1.5 records on Ubuntu 24.04 x86_64 / Swift 6.4 (release with debug symbols, without sanitizers) cover 17² and 512², scalar/RGB, NEAR 0/3 and all four operations: 32 separate processes. The ledger reports requested heap bytes, allocation calls, compressed buffers, predictor/context state, pixels, descriptors, storage-control objects, runtime and unattributed stacks. Categories at the same total-peak instant reconcile to that total. Separate category maxima cannot be added. Supplied destinations and source owners belong to the live baseline; caller-decode must not add an owned pixel allocation.

A separate pinned Valgrind 3.27.1 build (`b50f9a09ca65cc983c934bd0f50059304f3e939f`) observes stack/heap snapshots for 16 512² operations. It uses explicit begin/end snapshots. Very short inspections can have boundary snapshots only; their unobserved transient interior peaks remain unknown. Stack includes all active runtime threads and marker calls, and Massif heap-extra is an allocator model, not measured allocator overhead. Instrumented timings are not benchmark evidence.

Earlier Valgrind 3.22 and 3.27.1 attempts crashed inside libdispatch's async-main teardown. A synchronous main-thread driver executing the same async codec APIs unblocked profiling. One visibility compilation failure and the first boundary-only inspection parser rejection are retained as failed tooling attempts. They are neither codec failures nor passes.

The [final Heaptrack run](https://github.com/raster-labs/SwiftJLS/actions/runs/38539553458) passes all 32 marked operations. Encode, inspection and supplied-destination decode add zero owned-pixel array allocations; each owned decode adds exactly one. The latter requests 524,320 bytes for 512² scalar or 1,572,896 bytes for RGB, including the array's 32-byte storage header. Independent source/copy controls remain part of the hosted contract matrix.

| 512² profile | Encode heap increase | Owned decode increase | Supplied decode increase | Inspect increase |
| --- | --- | --- | --- | --- |
| Scalar, NEAR 0 | 224,595 | 634,357 | 109,569 | 619 |
| Scalar, NEAR 3 | 220,960 | 629,362 | 104,574 | 619 |
| RGB, NEAR 0 | 1,779,429 | 2,318,061 | 744,417 | 1,321 |
| RGB, NEAR 3 | 1,623,422 | 2,162,454 | 588,810 | 1,321 |

Values are requested-heap increases above the live setup baseline, in bytes; they include compressed output/reader copies and other operation storage, not just the algorithm. Recognised algorithm-state group increases range from 16,312 to 23,552 bytes in the 512² encode/decode cases. Remaining unattributed codec group increases reach 168 bytes. Every requested-heap byte is retained in the ledger, including unattributed bytes; small unknowns are not rounded to zero.

The [final stack run](https://github.com/raster-labs/SwiftJLS/actions/runs/38539606703) observes all 16 profiles, this time with interior snapshots for each. Observed stack peaks range from 6,448 to 18,096 bytes, including runtime/marker activity. Earlier boundary-only observations remain distinct failed-tooling history. Snapshot thinning still prevents a claim of exhaustive transient-peak capture.

These measurements provide a per-operation storage ledger for the selected profiles. Unattributed allocations and stack attribution limits remain explicit. They do not establish a universal exact algorithm-workspace counter or justify replacing production `peakWorkspaceBytes: nil` with an estimate.

## Remaining acceptance boundaries

- Resolve reproducible latency regressions, or obtain an explicit accepted correctness/safety trade-off with measured cost and a new baseline. There is no silent PERF-03 waiver.
- Complete any remaining pure algorithm-workspace attribution; measured requested heap, sampled stack and RSS have different scopes.
- Representative physical iPhone/iPad tests remain unexecuted. The owner requested use of installed simulators and GitHub resources, which provide software evidence; [PLATFORMS.md](../../PLATFORMS.md) also requires representative device tests. Physical Watch remains excluded and unexecuted.

Passing these software checks cannot establish that physical Watch is the only remaining requirement. No stable release, tag, merge, application cutover or Milestone 5 work is performed by this task.
