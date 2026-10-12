# SwiftJLS — staged implementation instructions

Read AGENTS.md and every common contract document first. The owner-assigned migration now includes the native codec, mapping tables, metadata and predecessor compatibility profiles. Follow the common contract when predecessor conventions differ. Maintain performance, reliability and security together. The implemented feature matrix is in [Parity.md](Documentation/Engineering/CodecMigration/Parity.md); executed and outstanding qualification is in [Validation.md](Documentation/Engineering/CodecMigration/Validation.md). Implementation completion does not authorise a stable release or consumer cutover.

For applications replacing the predecessor dependency, use [MIGRATION.md](MIGRATION.md). It records current owning APIs, codec profiles, compatibility options and deferred features; this document governs implementation inside SwiftJLS. Refresh the application guide as later milestones become available and tested.

## Source and destination

Current migration baseline: [raster-labs/JLSwift](https://github.com/raster-labs/JLSwift) at `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Target module/product: `SwiftJLS`. Target CLI: `swiftjls-cli`. Suite policy 0.10.0: tools 6.2, qualified primary Swift 6.4, Swift 6 language mode and Apple OS 26.0 floors. Intended first stable library version: `1.1.0`; this work remains unreleased.

The older inventory at `299b9a2e5bfe36ef104a3464a27d6c4c82874cc2` and the September product decisions below are historical inputs, not the selected codec baseline. CLI-01 renamed the executable after that inventory.

Do not migrate code from moving main without recording the selected revision. Reproduce relevant source tests and inspect source-level capabilities. Existing test totals and benchmark claims are historical, not successor acceptance evidence.

## Milestones and exit evidence

| Milestone | Work | Exit evidence |
| --- | --- | --- |
| 1 — contract feasibility | Establish Swift 6.4 package, independent local API/owning-memory types, descriptor validation and safe adapter experiment; no codec algorithm migration | Compiling equivalent public calls, lifecycle/race/error tests, standalone consumer build and contract issues resolved explicitly |
| 2 — migration baseline | Inventory predecessor subsystems/products; select and migrate the smallest native scalar lossless path with Apache-2.0/provenance reconciliation | Pinned predecessor comparison, independent decode/encode validation, exact sample/precision results, no new runtime codec dependency |
| 3 — shared-storage path | Direct final decode into caller storage and encode from compatible sealed storage | Required-sharing copy/allocation/lifetime proof; first suite pair or corresponding codec extension passes |
| 4 — feature/platform coverage | Extend supported modes/layouts, CLI, optional acceleration and all required OS/architecture paths | Capability matrix, codec-specific regressions, platform results, security and performance evidence |
| 5 — release preparation | Validate clean versioned consumption, docs/examples, migration guide, licence/fixture notices and release gates | Reviewed complete evidence; stable tag only after explicit release task |

Work one owner-assigned milestone at a time. Preserve internal algorithm names where helpful, but provide the agreed common public module surface. Do not publish a stable version or announce complete platform support while required gates are missing.


### Migration focus

- The predecessor library module is `JPEGLS`; the successor principal module is SwiftJLS. It currently has no CompressionFamily dependency. Preserve this independence.
- `Sources/JPEGLS/Encoder/JPEGLSPixelBuffer.swift` stores samples as nested `[[Int]]` component arrays. Create a validated compact-buffer reader for the new encoder path. The required shared-storage path must not construct full-frame nested arrays, copy a frame to interleave it, or widen every stored sample to Int solely for hand-off. Loading individual values into arithmetic locals and bounded predictor rows is allowed.
- Refactor lossless and near-lossless kernels to read through the same layout-aware access boundary. Preserve `NEAR == 0` as exact lossless, and validate nonzero maximum sample error. Configuration construction/placement must align with the common API.
- Implement direct decode into supplied output storage, preserving MAXVAL/meaningful precision rather than assuming every 16-bit container uses all 16 bits. Apply restart, interleave, mapping-table and colour-transform options only where their semantics are supported and tested.
- The predecessor's synchronous routines need real bounded cancellation points and a defined async execution policy. A thin async wrapper is insufficient. Keep a synchronous kernel if useful, but retain the owning storage for the full async operation.
- Native signed sample semantics are not inferred from a UInt16 memory view. Reject unsupported standalone signed-preservation requests until an explicit external mapping contract is implemented and tested.
- Do not reintroduce removed third-party implementation material. Independently maintained tools may be isolated test oracles with documented licensing; no external codec becomes a runtime fallback. Keep argument parsing outside the library dependency target.

### Codec-specific tests

Test predictor contexts, run interruption, Golomb coding, NEAR boundaries, preset/reset parameters, MAXVAL, 2..16-bit supported precision, line/sample/non-interleaved modes, restart intervals, mapping-table bounds, edge pixels, single-row/column images and truncated scans. Independently decode both lossless and near-lossless output and verify the declared error bound per logical sample. Tests must catch sample-width truncation and incorrect sign conversion.

Carry forward Data-slice index rebasing regressions, malformed headers/tables and unsupported dimensions. Exercise padded-row shared-buffer input, pool ownership, concurrent reader encodes and the cancellation lifecycle. Demonstrate that memory scales with the intended buffer/algorithm workspace, not a hidden full-frame Int matrix.

### Initial codec delivery — Milestones 2–4

The following codec work follows Milestone 1 contract feasibility. It is not part of the first coding task. Migrate the scalar path in Milestone 2, prove shared storage in Milestone 3, and extend features/CLI/platform coverage in Milestone 4.

Implement direct lossless encoding from the common unsigned 16-bit greyscale profile and exact JPEG-LS decode verification. Integrate with SwiftJ2K in the development-only harness; then add direct JPEG-LS decode-into and the reverse route. Preserve 12-in-16 declared precision in the compressed frame header.


## Product dispositions (POL-05)

Decided 22 September 2026 under contract 0.8.0 §3, which requires this inventory before any subsystem is relocated. Measured at predecessor JLSwift `a5757d3` with `swift package dump-package`. "Imports" counts files across DICOMKit, CompressionFamily, VoxeliaValidation, DICOMAdapter, RasterOneImage, OneImageViewer-iOS and telerad-dicom-viewer containing a top-level `import <module>`.

POL-05 requires every product to be explicitly **retained** (migrates, stays a public product), **adapted** (migrates with a changed shape — folded into the principal module, renamed, or re-expressed through the common API) or **deferred** (does not migrate for the first stable; stays with the predecessor through the maintenance window). Deferred is not deleted.

| Predecessor product | Files / lines | Imports | Disposition | Successor | Basis |
| --- | --- | --- | --- | --- | --- |
| `JPEGLS` | 31 / 11,993 | 2 | Adapted — renamed | `SwiftJLS` | API-01. [MIGRATION.md](MIGRATION.md) already documents `JPEGLS` → `SwiftJLS` and `import JPEGLS` → `import SwiftJLS`. |
| ↳ `Sources/JPEGLS/Contract/` | — | — | Adapted — folded in | `SwiftJLS` | Already an internal directory rather than a separate product, making this the cheapest of the four contract-layer merges. Contract 0.8.0 §5. |
| ↳ `PNGSupport.swift` | 19 KB | — | Deferred | none | Not JPEG-LS, and CLI-04 fixes the interchange profile as NRRD rather than PNG |
| ↳ `TIFFSupport.swift` | 20 KB | — | Deferred | none | as `PNGSupport` |
| `jpegls` (exec) | 14 / 4,298 | — | Adapted — renamed | `swiftjls` | CLI-01 |

**Current product list after CLI-01 naming reconciliation:** `SwiftJLS` (library) and `swiftjls-cli` (executable). The historical table above records the September decision before the naming amendment.

This codec is the migration pilot. It is the smallest of the four, it has no package dependency to extract, and it is the codec named in the suite's first cross-codec proof, so the shape of these decisions is settled here first and applied to the other three.

### Decisions recorded with these dispositions

**L1 — `PNGSupport` and `TIFFSupport` are deferred, and named in the farewell release.** Both are public API of `JPEGLS`, not internal helpers. Grepping DICOMKit and VoxeliaValidation — the only in-house importers of `JPEGLS` — for either type returns nothing, so deferring them breaks no in-house consumer. Because they are public, an external consumer could still rely on them, so the JLSwift v0.10.0 release notes must state that they do not migrate.

**CLI surface.** Retained and adapted: the CLI-01 verbs `encode`, `decode`, `inspect` (renamed from `Info`), `validate` and `capabilities`. Deferred to a CLI milestone after the first stable: `Batch`, `Benchmark`, `Compare`, `Convert`, `Verify` and `Completion`. Deferred under POL-05: `BenchDICOM`. Existing predecessor scripts are retained until tested replacements exist, as [MIGRATION.md](MIGRATION.md) already requires.

## Required handover

Update CHANGELOG.md and migration provenance. Provide the exact commands, commits, fixture hashes and outcomes; report tests not run and why, unsupported cases, allocation/copy evidence and performance impact. Map each advertised feature to a test and capability entry. Keep DICOMKit/Voxelia source changes outside this repository task unless the owner separately assigns them.

## Historical owner-authorised OS 27 and CLI foundation

Before codec migration, the owner raised Apple floors to 27.0 and requested executable help, verbosity and UNIX manuals. This bounded CLI foundation implements help/version/capabilities only; codec commands remain explicitly unavailable. See [CLI.md](CLI.md) and [new evidence](Documentation/Engineering/OS27CLI/README.md). The later codec/CLI milestones still govern real payload operations.

The preceding OS 27 paragraph is retained as history. Contract 0.5.0 restored OS 26.0, and the current migration implements the bounded greyscale NRRD payload commands. Current scope and qualification are linked at the top of this document.
