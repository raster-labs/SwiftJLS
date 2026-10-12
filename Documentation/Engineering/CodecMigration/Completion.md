# Migration completion audit — 12 October 2026

**The migration is not fully complete.** The native codec and shared-storage paths have substantial executed evidence, but one predecessor compatibility gap and mandatory qualification gates remain. This audit applies the exit requirements in [IMPLEMENTATION.md](../../../IMPLEMENTATION.md), the [testing contract](../../TESTING.md), [performance contract](../../PERFORMANCE.md) and [platform contract](../../PLATFORMS.md). Passing CI does not close requirements that its jobs do not measure.

## Revisions and scope

- Merged SwiftJLS main: `f481f6031279b8ca5c51f559df33cc66a9e4e06b`, [PR 14](https://github.com/raster-labs/SwiftJLS/pull/14), merged 12 October.
- Tested runtime candidate: `3f16daf61f88bc136b6db478fd13abac234af4f5`, [draft PR 15](https://github.com/raster-labs/SwiftJLS/pull/15), not yet merged. The documentation follow-up leaves its source, tests, scripts, fixtures and package manifest unchanged.
- Migration predecessor: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; bounded-decoding comparison additionally uses `e4594319b83a79189a3e349ab282e2872b7ebd7a` on `fix/bounded-dicom-decoding`.
- Suite policy 0.10.0; tools 6.2 minimum, primary Swift 6.4, Swift 6 language mode, Apple OS 26.0. The seven shared documents retain their individual revisions and verified hashes.
- Scope is this library and its declared CLI. Consumer cutover, a stable release and predecessor maintenance/archival have not been performed by this work.

## Milestone disposition

| Milestone | Evidence checked | Disposition |
| --- | --- | --- |
| 1 — API and memory feasibility | Descriptor, ownership, concurrency and cancellation suites; independent local and URL consumers; shared-contract checks | Implemented and validated in the recorded scope |
| 2 — native migration baseline | Pinned source provenance, scalar lossless/near-lossless samples, independent oracle inputs and successor outputs, no runtime codec dependency | Implemented and independently validated |
| 3 — shared storage | Real SwiftJ2K/SwiftJLS consumer, destination identity, padded/strided samples, scoped borrows, cancellation, allocator/copy mutation controls and file observation | Implemented with boundary-specific evidence; no claim of complete peak-workspace measurement |
| 4 — features and platforms | Scalar/component/preset/mapping/HP/metadata/subsampling profiles, bounded CLI, Linux/macOS and Apple SDK checks | Incomplete: inactive DRI gap below; controlled performance/workspace and physical-device admission remain open |
| 5 — release preparation | Standalone consumption, guide/examples, licence/provenance and current documentation reviewed | Incomplete: remaining gates, final candidate duration qualification, release support policy and explicit release approval |

The [profile matrix](Parity.md) defines actual supported combinations. PNG/TIFF helpers and extended predecessor CLI verbs are owner-approved deferrals, not accidentally missing migrations. Signed/alpha/ICC interpretation, subsampled encoding, DNL unknown-height decoding and native transcoding are not advertised as implemented. [Application migration](../../../MIGRATION.md) remains a separate acceptance process.

## Verified current evidence

At `3f16daf`, each local debug, release, AddressSanitizer and ThreadSanitizer suite passes 77 declarations in nine suites. The CLI passes 73 payload checks, and the independent consumer preserves samples and caller allocation identity. All 16 hosted checks pass, including independent CharLS interoperability and the cross-codec consumer. Exact results and links are retained in [DICOM padding evidence](results/dicom-padding-2026-10-12.json) and [Validation.md](Validation.md).

Eighteen focused bounded-decoding comparisons agree with the unchanged JLSwift fix branch. The candidate accepts precisely one zero after an odd-length complete codestream, rejects incomplete/concatenated streams and invalid tails, and enforces compressed/pixel/all-component storage limits. Int versus UInt16 sample widths are accounted for in byte-limit comparisons. General resource defaults intentionally follow TEST-06 rather than copying predecessor defaults.

The documentation audit verified all 20 source hashes and destination paths in the scalar provenance map, 2,678 fixture/sample hash entries across 2,678 distinct files, all seven shared-contract hashes, and the retained count of 981 JPEG-LS files. The documentation pass also verified 104 relative links and JSON syntax, passed man-page lint, and passed 103 CLI help/diagnostic/staged-install/manual checks. Runtime source, tests, scripts, fixtures, manifest and version remain identical to the tested candidate. These checks validate recorded integrity; they do not turn predecessor-authored fixtures into independent standards oracles. See [audit evidence](results/migration-audit-2026-10-12.json).

## Confirmed open compatibility gap: inactive DRI

The predecessor accepts line- and sample-interleaved streams whose declared restart interval is at least their height: no restart boundary occurs inside the frame. SwiftJLS rejects every nonzero DRI with interleaving in [JPEGLSHeader.swift](../../../Sources/SwiftJLS/JPEGLS/JPEGLSHeader.swift), even when no RST marker is needed. This contradicts complete predecessor parity; it is not an approved feature deferral.

Four fresh comparisons used 2×2, 8-bit RGB planes `[1, 2; 3, 4]`, both `.line` and `.sample` interleaving, and DRI values 2 and 9999. The unchanged predecessor decoded all samples exactly. SwiftJLS returned `unsupportedFeature` in all four cases. [Audit evidence](results/migration-audit-2026-10-12.json) retains the synthetic input bytes and results. The predecessor's `interleavedStreamWithInactiveDRI` test in [its regression suite](https://github.com/raster-labs/JLSwift/blob/15aa75164145414f3d5ffb801401c52d40cc5bcc/Tests/JPEGLSTests/JPEGLSRobustnessRegressionTests.swift) also covers this behaviour.

Reproduce by encoding those planes with `JPEGLSEncoder`, inserting the DRI segment `FF DD 00 04 00 02` (or `FF DD 00 04 27 0F`) immediately after SOI, then decoding the same bytes with each library. Before closing this gap, add successor regressions at and above the image height for both interleaves, preserve rejection of active unsupported restart schedules and stray/out-of-sequence markers, and exercise inspection plus both decode destinations. This audit records the gap; it does not change codec behaviour.

## Gates that still prevent completion

| Requirement | What remains |
| --- | --- |
| Predecessor compatibility | Resolve the inactive-DRI rejection and verify the boundary cases above |
| PERF-01..03 | Controlled, interleaved predecessor/successor measurements with the required repetitions, distributions, encoded sizes and memory/copy metrics; investigate the recorded large-case latency regressions rather than treating workstation results as a pass |
| MEM/TEST resource evidence | Complete peak pixel/workspace measurement and concurrent admission stress, including colour and near-lossless profiles; unknown report fields must remain unknown |
| PLAT device/runtime qualification | Physical Apple-device execution and memory/deadline admission; simulator SDK compilation and the 32-bit Watch compile are not hardware runtime evidence; exact minimum-version runtime coverage remains distinct |
| TEST-05 final revision | A full one-hour-per-entry campaign on the final release candidate after parser corrections. The passed 10 October campaigns stay pinned to their older revisions; the 15-second-per-entry candidate smoke checks do not replace them |
| Release readiness | Confirm the security reporting/supported-version policy, review all gates, and obtain a separately assigned stable release task; no stable 1.1.0 tag was found during this audit |
| Programme rollout | Application-specific acceptance, deployment-floor changes and dependency cutover, then predecessor maintenance/archival under the recorded policy; these are separate from a library source migration |

Existing advisory benchmark regressions and oracle coverage exclusions remain in [Validation.md](Validation.md). No threshold is relaxed, no compatibility option is silently enabled, and no physical-device or controlled-benchmark result is inferred from passing CI. Historical records and owner-supplied documents are preserved.
