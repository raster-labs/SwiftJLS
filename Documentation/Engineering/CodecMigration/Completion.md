# Migration completion audit — 12 October 2026

**The known compatibility gap is fixed; full migration/release qualification is still incomplete.** This follow-up implements the compatibility fixes and expands software qualification, but cannot substitute workstation measurements or simulator builds for controlled performance and required physical-device evidence. Physical Watch testing is excluded from this task at the user's request; that exclusion is not a hardware pass or a change to the shared release contracts.

This audit applies [IMPLEMENTATION.md](../../../IMPLEMENTATION.md), [TESTING.md](../../TESTING.md), [PERFORMANCE.md](../../PERFORMANCE.md) and [PLATFORMS.md](../../PLATFORMS.md). Historical evidence and the seven shared contracts are preserved.

## Revisions and scope

- Merged main: `f481f6031279b8ca5c51f559df33cc66a9e4e06b`, [PR 14](https://github.com/raster-labs/SwiftJLS/pull/14).
- Corrected runtime: `4008f213cc749514300de55dfc17b389fbd3b561`, in unmerged [PR 15](https://github.com/raster-labs/SwiftJLS/pull/15). Qualification checkpoint `580a7de9d6f1c483833ac8fe141f9cd8cb225765` adds tests and development measurement tools; production sources, manifest, mutation harness and fixtures remain identical to `4008f21`.
- Migration predecessor: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Bounded-decoding comparisons additionally use unchanged `e4594319b83a79189a3e349ab282e2872b7ebd7a` on `fix/bounded-dicom-decoding`.
- Suite policy 0.10.0; tools 6.2 minimum, primary Swift 6.4, Swift 6 language mode, Apple OS 26.0. Development version remains `1.1.0-dev.2`.
- Scope is the library and its declared CLI. Consumer cutover, stable publication and predecessor maintenance/archival remain separate assignments.

## Milestone disposition

| Milestone | Current disposition |
| --- | --- |
| 1 — API/memory feasibility | Implemented and validated in the recorded scope |
| 2 — native migration baseline | Implemented and independently validated |
| 3 — shared storage | Implemented; independent caller-storage/copy controls, sample/lifetime tests and measured heap evidence recorded |
| 4 — features/platforms | Known compatibility gap closed; controlled performance, complete per-operation workspace and non-Watch physical-device qualification remain open |
| 5 — release preparation | Documents/examples/provenance and software qualification updated; remaining release gates, reporting/support policy and explicit release assignment prevent completion |

The [profile matrix](Parity.md) defines supported combinations. PNG/TIFF helpers and extended predecessor CLI verbs remain owner-approved deferrals. Signed/alpha/ICC interpretation, subsampled encoding, DNL unknown-height decoding and native transcoding are not newly advertised. Application acceptance remains governed by [MIGRATION.md](../../../MIGRATION.md).

## Completed fixes and verification

The decoder now accepts line/sample-interleaved DRI values at or above frame height, because no restart boundary occurs within the frame. Tests cover 16/24/32-bit fields, the exact-height boundary, larger values including UInt32.max, subsampled line input, inspection, owned decode and supplied storage. Active interleaved schedules and stray RST0/RST7 markers remain rejected before taking the destination write lease. All four former 2×2 predecessor discrepancies now decode identically. The earlier failing results remain in [the original audit](results/migration-audit-2026-10-12.json).

The preceding DICOM-padding fix remains verified: precisely one zero after an odd-length complete codestream is accepted; incomplete/concatenated streams and other tails fail, and padding counts towards the compressed limit. All 18 bounded-decoding comparisons still agree. General limits deliberately follow TEST-06 rather than copying predecessor defaults or treating Int and UInt16 sample storage as equal byte budgets.

- **Hosted qualification:** all 15 PR checks pass at qualification checkpoint `580a7de`: the [14-job contract matrix](https://github.com/raster-labs/SwiftJLS/actions/runs/38245951833) and [independent CharLS interoperability](https://github.com/raster-labs/SwiftJLS/actions/runs/38245951832). Later changes affect the locally validated benchmark harness and documentation; production sources and the 80-test suite are unchanged.
- **Local correctness:** 80 tests in ten suites pass separately in debug, release, AddressSanitizer and ThreadSanitizer; 73 payload CLI checks, 103 process/help/install/manual checks and the independent consumer pass.
- **Concurrent admission:** four fixed workers exercise colour and near-lossless decoding, insufficient workspace, expired deadlines, cancellation and destination reuse. A separate ordinary-release consumer checks every sample across 32 512×512 scalar/RGB NEAR 0/3 frame transactions.
- **Independent memory:** [hosted ordinary-build observation](https://github.com/raster-labs/SwiftJLS/actions/runs/38245951833) records 5,521 allocations and a 15,620,616-byte requested-heap peak for that concurrent workload. Exactly 32 codec `OwnedImageStorage` sample-array allocations match the 32 intentional owned decodes. The 36 caller pixel allocations are four source owners plus 32 supplied destinations. No unexpected owner-backed pixel allocations are observed in this workload; arbitrary arrays outside those stacks are not automatically classified as pixels. Codec nonpixel heap peaks at 3,320,448 bytes; it includes compressed buffers/metadata and is not pure algorithm workspace. Individual group peaks must not be added. Runtime/unattributed allocations remain explicit.
- **Existing profile routes:** the ten encode/caller-decode profiles plus 98 additional decodes retain zero pixel allocations beneath encode/caller-decode. Their whole-process requested-heap peak is 682,405 bytes. Heap replay matches Heaptrack's total peaks and allocation counts; injected-copy controls remain separate evidence.
- **Final-duration mutation:** all [three one-hour campaigns](https://github.com/raster-labs/SwiftJLS/actions/runs/38244562355) pass on corrected runtime `4008f21`, using all 981 seeds: 6,858,685 owned-decode iterations, 8,855,815 caller-destination mutations (2,971,517 decode calls), and 6,966,138 inspections. Each ran at least 3,600 seconds under AddressSanitizer, exited zero and produced empty sanitizer stderr. [Exact duration/results and artifact hashes](results/fuzz-migration-followup-hour.json) are retained; sanitizer RSS is not ordinary workspace telemetry.
- **Watch architecture:** the corrected runtime passes the [arm64_32 device-SDK build](https://github.com/raster-labs/SwiftJLS/actions/runs/38244562747). This is compilation evidence, not physical execution.
- **Apple runtime:** all [four simulator jobs](https://github.com/raster-labs/SwiftJLS/actions/runs/38244565906) pass on the corrected runtime: iOS 26.4.1, tvOS 26.5, watchOS 26.4 and visionOS 26.5, using Xcode 26.6 / Swift 6.3.3. Direct storage, RGB/HP, mapping/metadata, bounded limits, cancellation and combined legacy mapping/HP checks pass. [Exact runtime evidence](results/migration-followup-apple-runtime.json) remains distinct from OS 26.0 or physical-device execution.

See [Validation.md](Validation.md) and [follow-up evidence](results/migration-followup-2026-10-12.json) for commands, source equivalence, run status, raw measurements and limitations. The earlier provenance audit verified all 20 migrated-source records, 2,678 fixture/sample hash entries, all seven common-contract hashes and 981 mutation seeds; its historical record is unchanged.

## Performance investigation

A new 24-case predecessor/successor release comparison uses four alternating process blocks with five warm-ups per block and 20 timed iterations per direction/case. Raw distributions, median, p95, spread, throughput, encoded sizes, process RSS, binary hashes, power and load snapshots are retained in [the benchmark results](results/migration-followup-benchmark/summary.json).

The benchmark harness now also supports RGB NEAR 0/3 and all three interleaves. Its 36 small colour and six small scalar smoke profiles pass for both libraries; the full 144-case colour timing remains a controlled-hardware follow-up. Smoke measurements are not performance qualification.

The host stayed on battery. Large 12-bit encoding remains roughly 1.15–1.46× predecessor latency; 16-bit ramp/noise encoding roughly 1.16–1.35×. Process RSS is lower, but does not waive latency regressions or establish workspace accounting. A separate five-second CPU sample identifies meaningful-bit validation at `ScalarCodec.swift:120` as a substantial part of flat 12-bit encoding; this is an investigation lead, not proof of every regression's cause or an approved safety/performance trade-off. The pinned predecessor validates immutable pixel planes during `MultiComponentImageData` construction, outside the timed encoder call; SwiftJLS validates meaningful-bit ranges inside encoding. Thus these public-API timings include different validation boundaries and do not isolate kernel overhead. Controlled follow-up must also measure source preparation/end-to-end cost. A second five-second profile of full-range 16-bit noise concentrates in the scalar kernel/bit writer, where the meaningful-bit validation scan is skipped; the flat 12-bit explanation therefore does not resolve the other regressions. No safety check or regression threshold was weakened.

## Requirements still preventing completion

| Requirement | Remaining action / constraint |
| --- | --- |
| PERF-01..03 | Repeat representative scalar and supported colour measurements on controlled, powered hardware; resolve or explicitly accept measured regressions with a recorded cost/baseline. This battery-powered run is advisory. |
| Full workspace accounting | Retain measured heap groups and unknown fields honestly; complete per-operation algorithm-workspace accounting, separating compressed buffers, metadata, runtime and stack storage. Current external peaks do not justify replacing `peakWorkspaceBytes: nil` with an estimate. |
| Non-Watch physical devices | Execute representative iPhone/iPad and other required target-device admission tests with available hardware and provisioning. Command Line Tools are active; no Xcode installation was found in `/Applications`, and `xcrun --find devicectl` fails; no physical pass is claimed. |
| Minimum/platform runtimes | Obtain and execute the required OS 26.0 runtime coverage; the passed newer-minor simulator runtimes cannot be reported as exact-minimum passes. |
| Physical Watch | Excluded from this task by the user. Remains explicitly unexecuted in release/platform evidence. |
| Security/release readiness | GitHub reports private vulnerability reporting disabled. An enable attempt returned HTTP 404 and did not change it. An administrator must establish an actionable private channel and the first stable version's support policy. Stable release/tagging requires a separately assigned release task after gates close. |
| Programme rollout | Application-specific acceptance and dependency cutover, followed by predecessor maintenance/archival, remain outside this library task. |

These are explicit incomplete requirements, not implicitly approved deferrals. Passing software tests alone does not make the migration complete except for Watch testing.
