# Migration completion audit — updated 14 October 2026

**The known compatibility gap is fixed; full migration/release qualification is still incomplete.** This follow-up implements the compatibility fixes and expands software qualification, including native macOS 26.0 execution and controlled representative measurements. Residual performance regressions, incomplete algorithm-workspace attribution and required physical-device evidence remain open. Physical Watch testing is excluded from this task at the user's request; that exclusion is not a hardware pass or a change to the shared release contracts.

This audit applies [IMPLEMENTATION.md](../../../IMPLEMENTATION.md), [TESTING.md](../../TESTING.md), [PERFORMANCE.md](../../PERFORMANCE.md) and [PLATFORMS.md](../../PLATFORMS.md). Historical evidence and the seven shared contracts are preserved.

On 13 October the user confirmed that no physical devices are available and requested the available checks. Physical-device admission therefore remains unavailable/unexecuted. Current-source software and powered benchmark results are recorded in [the 14 October follow-up](Milestone4Followup.md); historical results below retain their original revisions.

## Revisions and scope

- Merged baseline: `571fd7c905f7ef70b4f494513ecf979d620bebd5`, [PR 15](https://github.com/raster-labs/SwiftJLS/pull/15), merged 13 October 2026; includes the preceding PR 14.
- Corrected runtime: `4008f213cc749514300de55dfc17b389fbd3b561`, now merged through [PR 15](https://github.com/raster-labs/SwiftJLS/pull/15). Qualification checkpoint `580a7de9d6f1c483833ac8fe141f9cd8cb225765` adds tests and development measurement tools; production sources, manifest, mutation harness and fixtures remain identical to `4008f21`.
- Current Milestone 4 checkpoint: `8389b29003a187b6c54c9d1cad463758f531ca24`; run/predictor/bit-writer improvements, 84 declarations passing in four configurations, fresh exact-26.0 simulator checks, native macOS 26.0 tests in all four configurations and per-operation heap/stack measurements. [Current evidence](results/milestone4-followup-2026-10-14.json).
- Migration predecessor: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Bounded-decoding comparisons additionally use unchanged `e4594319b83a79189a3e349ab282e2872b7ebd7a` on `fix/bounded-dicom-decoding`.
- Suite policy 0.10.0; tools 6.2 minimum, primary Swift 6.4, Swift 6 language mode, Apple OS 26.0. Development version remains `1.1.0-dev.2`.
- Scope is the library and its declared CLI. Consumer cutover, stable publication and predecessor maintenance/archival remain separate assignments.

The owner assigned Milestone 4 only on 13 October, leaving Milestone 5 for later. [The current follow-up](Milestone4Followup.md) records component optimisations, fresh software checks and powered representative benchmarks. It does not waive outstanding qualification gates.

## Milestone disposition

| Milestone | Current disposition |
| --- | --- |
| 1 — API/memory feasibility | Implemented and validated in the recorded scope |
| 2 — native migration baseline | Implemented and independently validated |
| 3 — shared storage | Implemented; independent caller-storage/copy controls, sample/lifetime tests and measured heap evidence recorded |
| 4 — features/platforms | Known compatibility gap closed; exact 26.0 simulator consumers and native arm64 macOS 26.0 tests pass. Representative performance and heap/stack measurements are complete; residual regressions, remaining algorithm-workspace attribution and non-Watch physical-device qualification remain open |
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

The [current powered report](Milestone4Followup.md#performance) supersedes the earlier battery-powered timings for current-source assessment. It covers all 24 scalar cases and the owner-selected 39 RGB cases, including every 512×512 combination and three larger examples. Four alternating blocks retain 20 observations per producer/operation/case, plus preparation, encoded sizes, process RSS and condition snapshots. The full 144-case RGB grid was not completed.

Component access, lossless predictor reuse, bounded run fills and value-writer changes improve measured hot paths, but residual JLSwift-relative regressions remain. Preparation timing exposes differing public-API validation boundaries; it does not waive encode/decode regressions. Background workstation activity and sampled load remain disclosed. No safety check, fidelity or regression threshold was weakened. Historical interrupted and default-resource-limit attempts are retained separately.

## Requirements still preventing completion

| Requirement | Remaining action / constraint |
| --- | --- |
| PERF-01..03 | Powered representative measurements are now recorded. Resolve or explicitly accept residual regressions with a recorded reason, measured cost and baseline; repeat affected profiles after implementation changes. No waiver is recorded. |
| Full workspace accounting | All 32 selected requested-heap ledgers reconcile; 16 separate stack profiles retain interior observations. Remaining unattributed allocations and stack attribution/sampling limits prevent complete pure algorithm-workspace accounting. Keep `peakWorkspaceBytes: nil` where no complete measurement exists; see [current scope](Milestone4Followup.md#workspace-accounting). |
| Non-Watch physical devices | Unavailable/unexecuted: the user confirmed no physical devices on 13 October. Execute representative iPhone/iPad and other required target-device admission tests when hardware and provisioning are available. The user has now installed Xcode 27.0; simulator consumer and Watch device-architecture builds pass locally, but `devicectl` reports no connected devices. No physical pass is claimed. |
| Physical Watch | Excluded from this task by the user. Remains explicitly unexecuted in release/platform evidence. |
| Security/release readiness | GitHub reports private vulnerability reporting disabled. An enable attempt returned HTTP 404 and did not change it. An administrator must establish an actionable private channel and the first stable version's support policy. Stable release/tagging requires a separately assigned release task after gates close. |
| Programme rollout | Application-specific acceptance and dependency cutover, followed by predecessor maintenance/archival, remain outside this library task. |

These are explicit incomplete requirements, not implicitly approved deferrals. Passing software tests alone does not make the migration complete except for Watch testing.
