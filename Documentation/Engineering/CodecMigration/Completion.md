# Migration completion audit — updated 14 October 2026

**Current-source software validation and scoped workspace accounting are complete; the performance gate remains open.** Source `c330b73` passes 108 declarations in 20 suites in four local and native arm64 macOS 26.0 configurations. All five exact OS 26.0 simulator consumers, four resource profiles and SDK builds pass. Native macOS execution uses Apple hardware virtualisation; it is not physical-device qualification. Scoped workspace accounting retains explicit measurement revisions and unknown universal totals. All physical-device tests remain pending at the owner’s request, and Milestone 5 remains deferred.

This audit applies [IMPLEMENTATION.md](../../../IMPLEMENTATION.md), [TESTING.md](../../TESTING.md), [PERFORMANCE.md](../../PERFORMANCE.md) and [PLATFORMS.md](../../PLATFORMS.md). Historical evidence and the seven shared contracts are preserved.

On 13 October the user confirmed that no physical devices are available and requested the available checks. The current task keeps all physical-device admission pending, including iPhone/iPad and Watch. See [the current closeout](Milestone4Closeout.md) and [workspace accounting](WorkspaceAccounting.md); historical results below retain their original revisions. The owner will verify CI and merge the pushed branch in GitHub.

## Revisions and scope

- Merged baseline: `571fd7c905f7ef70b4f494513ecf979d620bebd5`, [PR 15](https://github.com/raster-labs/SwiftJLS/pull/15), merged 13 October 2026; includes the preceding PR 14.
- Corrected runtime: `4008f213cc749514300de55dfc17b389fbd3b561`, now merged through [PR 15](https://github.com/raster-labs/SwiftJLS/pull/15). Qualification checkpoint `580a7de9d6f1c483833ac8fe141f9cd8cb225765` adds tests and development measurement tools; production sources, manifest, mutation harness and fixtures remain identical to `4008f21`.
- Current Milestone 4 checkpoint: `c330b731e250d6b4c054c1c6a91fa9894e32a8c3`; 108 declarations in 20 suites pass in debug/release/ASan/TSan on the host and native arm64 macOS 26.0 guest. All five exact OS 26.0 simulator consumers, four resource profiles and SDK builds pass. Native CLI checks (73 payload/103 process), independent consumer and resource workload pass. The powered 63-case campaign is complete; remaining decode regressions keep performance qualification open. The [final evidence record](results/milestone4-final-2026-10-14.json) retains the completed measurements and unresolved findings. The branch has been pushed; the owner verifies CI and merges in GitHub.
- Intermediate checkpoint `940da40b867cd14f7888492162c13e237609d991` passed 103 declarations in 18 suites in four local/native macOS 26.0 configurations and exact OS 26.0 simulator/resource checks. The earlier `8389b29` results remain in [their original evidence](results/milestone4-followup-2026-10-14.json).
- Migration predecessor: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Bounded-decoding comparisons additionally use unchanged `e4594319b83a79189a3e349ab282e2872b7ebd7a` on `fix/bounded-dicom-decoding`.
- Suite policy 0.10.0; tools 6.2 minimum, primary Swift 6.4, Swift 6 language mode, Apple OS 26.0. Development version remains `1.1.0-dev.2`.
- Scope is the library and its declared CLI. Consumer cutover, stable publication and predecessor maintenance/archival remain separate assignments.

The owner assigned Milestone 4 only, leaving Milestone 5 for later. [The current closeout](Milestone4Closeout.md) records context/storage, validation and fixed-cost improvements, fresh software checks and the completed benchmark measurements with unresolved dispositions. It does not waive outstanding qualification gates.

## Milestone disposition

| Milestone | Current disposition |
| --- | --- |
| 1 — API/memory feasibility | Implemented and validated in the recorded scope |
| 2 — native migration baseline | Implemented and independently validated |
| 3 — shared storage | Implemented; independent caller-storage/copy controls, sample/lifetime tests and measured heap evidence recorded |
| 4 — features/platforms | Implementation, four-configuration host/native macOS 26.0 validation (108 declarations, 20 suites), five exact OS 26.0 simulator consumers, four resource profiles and SDK builds pass at `c330b73`. The powered 63-case campaign is complete; remaining decode regressions keep performance qualification open. Scoped workspace accounting retains its measured-source boundaries. All physical-device tests remain pending |
| 5 — release preparation | Deferred to a later owner task. Remaining release gates, reporting/support policy and explicit release assignment prevent completion |

The [profile matrix](Parity.md) defines supported combinations. PNG/TIFF helpers and extended predecessor CLI verbs remain owner-approved deferrals. Signed/alpha/ICC interpretation, subsampled encoding, DNL unknown-height decoding and native transcoding are not newly advertised. Application acceptance remains governed by [MIGRATION.md](../../../MIGRATION.md).

## Earlier compatibility fixes and revision-scoped verification

The decoder now accepts line/sample-interleaved DRI values at or above frame height, because no restart boundary occurs within the frame. Tests cover 16/24/32-bit fields, the exact-height boundary, larger values including UInt32.max, subsampled line input, inspection, owned decode and supplied storage. Active interleaved schedules and stray RST0/RST7 markers remain rejected before taking the destination write lease. All four former 2×2 predecessor discrepancies now decode identically. The earlier failing results remain in [the original audit](results/migration-audit-2026-10-12.json).

The preceding DICOM-padding fix remains verified: precisely one zero after an odd-length complete codestream is accepted; incomplete/concatenated streams and other tails fail, and padding counts towards the compressed limit. All 18 bounded-decoding comparisons still agree. General limits deliberately follow TEST-06 rather than copying predecessor defaults or treating Int and UInt16 sample storage as equal byte budgets.

- **Hosted qualification:** all 15 PR checks pass at qualification checkpoint `580a7de`: the [14-job contract matrix](https://github.com/raster-labs/SwiftJLS/actions/runs/38245951833) and [independent CharLS interoperability](https://github.com/raster-labs/SwiftJLS/actions/runs/38245951832). All 15 checks also pass at `866e63e`: [contract matrix](https://github.com/raster-labs/SwiftJLS/actions/runs/38252574682) and [CharLS interoperability](https://github.com/raster-labs/SwiftJLS/actions/runs/38252574681). Production sources and the 80-test suite are unchanged.
- **Local correctness:** 80 tests in ten suites pass separately in debug, release, AddressSanitizer and ThreadSanitizer; 73 payload CLI checks, 103 process/help/install/manual checks and the independent consumer pass.
- **Concurrent admission:** four fixed workers exercise colour and near-lossless decoding, insufficient workspace, expired deadlines, cancellation and destination reuse. A separate ordinary-release consumer checks every sample across 32 512×512 scalar/RGB NEAR 0/3 frame transactions.
- **Independent memory:** [hosted ordinary-build observation](https://github.com/raster-labs/SwiftJLS/actions/runs/38245951833) records 5,521 allocations and a 15,620,616-byte requested-heap peak for that concurrent workload. Exactly 32 codec `OwnedImageStorage` sample-array allocations match the 32 intentional owned decodes. The 36 caller pixel allocations are four source owners plus 32 supplied destinations. No unexpected owner-backed pixel allocations are observed in this workload; arbitrary arrays outside those stacks are not automatically classified as pixels. Codec nonpixel heap peaks at 3,320,448 bytes; it includes compressed buffers/metadata and is not pure algorithm workspace. Individual group peaks must not be added. Runtime/unattributed allocations remain explicit.
- **Existing profile routes:** the ten encode/caller-decode profiles plus 98 additional decodes retain zero pixel allocations beneath encode/caller-decode. Their whole-process requested-heap peak is 682,405 bytes. Heap replay matches Heaptrack's total peaks and allocation counts; injected-copy controls remain separate evidence.
- **Final-duration mutation:** all [three one-hour campaigns](https://github.com/raster-labs/SwiftJLS/actions/runs/38244562355) pass on corrected runtime `4008f21`, using all 981 seeds: 6,858,685 owned-decode iterations, 8,855,815 caller-destination mutations (2,971,517 decode calls), and 6,966,138 inspections. Each ran at least 3,600 seconds under AddressSanitizer, exited zero and produced empty sanitizer stderr. [Exact duration/results and artifact hashes](results/fuzz-migration-followup-hour.json) are retained; sanitizer RSS is not ordinary workspace telemetry.
- **Watch architecture:** the corrected runtime passes the [arm64_32 device-SDK build](https://github.com/raster-labs/SwiftJLS/actions/runs/38244562747). This is compilation evidence, not physical execution.
- **Exact minimum simulators:** the 13 October local Swift 6.4/Xcode 27 consumers pass on iOS/iPadOS 26.0 (23A343), tvOS 26.0 (23J352), visionOS 26.0 (23M336) and watchOS 26.0 (23R353). Four non-Watch profiles also pass the 32-frame concurrent scalar/RGB workload. [Exact commands and results](results/milestone4-os26-2026-10-13.json) preserve the physical-device and workspace limitations.
- **Earlier Apple runtime:** all [four simulator jobs](https://github.com/raster-labs/SwiftJLS/actions/runs/38244565906) pass on the corrected runtime: iOS 26.4.1, tvOS 26.5, watchOS 26.4 and visionOS 26.5, using Xcode 26.6 / Swift 6.3.3. Direct storage, RGB/HP, mapping/metadata, bounded limits, cancellation and combined legacy mapping/HP checks pass. [Exact runtime evidence](results/migration-followup-apple-runtime.json) remains distinct from OS 26.0 or physical-device execution.

See [Validation.md](Validation.md) and [follow-up evidence](results/migration-followup-2026-10-12.json) for commands, source equivalence, run status, raw measurements and limitations. The earlier provenance audit verified all 20 migrated-source records, 2,678 fixture/sample hash entries, all seven common-contract hashes and 981 mutation seeds; its historical record is unchanged.

## Performance investigation

The powered campaign completed all 24 scalar cases and the owner-selected 39 RGB cases, including every 512×512 combination and three larger examples. Results and per-case dispositions are retained in [the current report](Milestone4Closeout.md#performance) and [final evidence record](results/milestone4-final-2026-10-14.json). The full 144-case RGB grid remains outside the owner-selected scope.

Focused measurements informed the implemented optimisations, but do not substitute for the final representative campaign. The [earlier powered report](Milestone4Followup.md#performance) retains its residual regressions and source revision. Preparation timing exposes differing public-API validation boundaries; it does not waive encode/decode regressions. No safety check, fidelity or regression threshold was weakened. Historical interrupted and default-resource-limit attempts remain separate.

## Current qualification boundaries and pending work

| Requirement | Remaining action / constraint |
| --- | --- |
| PERF-01..03 | All 63 cases measured at `c330b73`. Five main-campaign decode cases exceed 5%; tiny repeated measurements also retain outliers. A tested RGB optimisation remains unpromoted pending a powered comparison. No regression waiver is recorded. |
| Full scoped workspace accounting | Source bounds and all 89 observed-operation requested-heap ledgers are complete and attributed. An exact universal heap-plus-stack-plus-allocator total is unknown; retain `peakWorkspaceBytes: nil` and `pure_algorithm_workspace_complete: false`. See [scope and limits](WorkspaceAccounting.md). |
| All physical devices | Pending by owner direction: representative iPhone/iPad, Watch and other required target-device admission remain unexecuted. Simulator and device-architecture builds do not replace physical execution. |
| GitHub handoff | Production `c330b73` is pushed. The owner verifies CI on the final pushed head and merges in GitHub. Current-source software validation and evidence are recorded; performance qualification remains open. |
| Security/release readiness | GitHub reports private vulnerability reporting disabled. An enable attempt returned HTTP 404 and did not change it. An administrator must establish an actionable private channel and the first stable version's support policy. Stable release/tagging requires a separately assigned release task after gates close. |
| Programme rollout | Application-specific acceptance and dependency cutover, followed by predecessor maintenance/archival, remain outside this library task. |

Physical-device testing and Milestone 5 remain explicitly deferred by the owner. Passing software checks does not establish full release qualification or imply that only Watch testing is pending.
