# Codec migration checkpoint — 10 October 2026

The user authorised completion of the library migration. This checkpoint implements part of that work; it is not a release or a claim that all five milestones are complete.

Source: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Target base: SwiftJLS `91092f78b492e332a7ec200e68b76604088e44fb`. Suite policy 0.10.0 governs over stale repository-specific platform prose. The manifest remains tools 6.2, Swift 6 mode and Apple OS 26. The seven common documents remain unchanged.

## Implemented and independently checked

- Native scalar single-component JPEG-LS, 2–16 meaningful bits in unsigned 8-bit or 16-bit storage, lossless and NEAR 1…min(255, MAXVAL/2).
- Inspection, owned decode and direct caller-destination decode; padded rows, offsets and both byte orders.
- Encode uses a scoped read of the sealed owner. Decode uses one scoped destination write. No full-image conversion or Int matrix is constructed. Lossless has no predictor pixel allocation; near-lossless has two UInt16 predictor rows. Reported zero pixel allocations refers to full-image allocations; workspace is reported unknown rather than fabricated.
- Native `swiftjls-cli` encode/decode/inspect/validate, bounded attached raw UInt16 NRRD, pipe cancellation/deadlines, atomic file publication and aligned manual/installer. NRRD output rejects lower declared precision rather than widening it.
- Checked size admission, bounded writer, limited Golomb prefixes, end padding validation, custom-table workspace admission, cancellation/deadlines and pre-publication failure cleanup.
- 90 lossless CharLS fixtures spanning every precision, edge dimensions, ramps, zero/max runs and seeded noise. 168 near-lossless cases include maximum NEAR values. SwiftJLS decodes the oracle's reconstructed samples exactly; the separate oracle decodes all 258 successor outputs within the specified sample-error bound.
- Pinned predecessor comparison: 78/90 lossless outputs byte-identical. Twelve noise cases at 2–7 bits differ following the corrected low-MAXVAL default-threshold formula; all 90 successor outputs decode exactly with CharLS. Earlier failed runs are retained as diagnostic history.

CharLS 2.4.2 (`36dd3307e070d8fbc765c3ba890b7e681046fa39`) is an isolated BSD-3-Clause test oracle, outside the Swift package and runtime. Synthetic fixtures are original Apache-2.0 data. Fixture hashes and oracle identity are in `Tests/SwiftJLSTests/Fixtures/manifest.json`; each adapted source's pinned path is in the adjacent source header and `../MigrationPreflight/scalar-provenance.json`.

## Executed environment and evidence

Local host: macOS 27.0.1 arm64, Apple Swift 6.4 (`swiftlang-6.4.0.34.1`), CommandLineTools SDK 27.0. Swift Testing macros require the explicit local plugin argument recorded in the command JSON. No compiler or concurrency check is disabled. Prior hosted preparation CI is historical evidence, not validation of this codec checkpoint.

`results/` contains exact commands, exit codes and compact outcomes. The current codec checkpoint passed 41 declarations in debug, release, AddressSanitizer and ThreadSanitizer runs, including 90 parameterised lossless cases and 168 near-lossless cases. The CLI passed 26 payload/stream checks and 103 help/diagnostics/manual/staged-install checks. Earlier failures caught fixture construction and signal-handler issues and were corrected; they are not counted as passes.

## Remaining migration and release gates

Multi-component layouts and interleaving, mapping/colour-transform extensions, metadata semantics, complete cross-codec allocation/copy instrumentation and mutation proof, fuzz duration, controlled performance/memory measurements, complete native platform/device qualification and fresh remote consumption remain work in progress. Unsupported combinations throw; no runtime reference codec is used. Stable release/tagging is a separate explicit task.

## Preset, restart and storage extension

The next checkpoint adds explicit MAXVAL/T1/T2/T3/RESET, cyclic RST0–RST7 row restarts in both fidelity modes, and direct 8-bit caller storage. Sign normalisation now precedes modular error reduction, as required by T.87. Malformed preset thresholds below NEAR + 1 and attempted decoder overrides are rejected.

The accepted corpus now contains 518 vectors: 90 ordinary lossless, 168 ordinary near-lossless, 224 restart vectors and 36 explicit presets encoded by the published T.87 HP reference V1.00. The reference independently accepted all 36 successor preset candidates. The CharLS adapter independently decoded all 482 non-preset successor streams. CharLS 2.4.2 prediction correction assumes a power-of-two alphabet for some custom MAXVAL cases; those diagnostic outputs are not accepted as conformance fixtures. The published reference refuses MAXVAL below 3: six candidates remain explicitly unsupported by that oracle, with local sample-bound tests only. This gap is not reported as an oracle pass.

The reference workflow downloads the official ITU archive with SHA-256 verification and retains the HP conformance-only licence in its isolated temporary directory. No reference implementation or executable is shipped. Original synthetic samples and their reference-coded outputs are recorded in the fixture manifest. Reproduction uses `Scripts/Interop/reference-windows.py` followed by `generate-preset-fixtures.py`; the reference encoder chooses the SOF precision from MAXVAL, recorded separately from the original candidate precision.

`Examples/CrossCodecConsumer` depends on SwiftJ2K only in its separate development package, pinned to `be4e7a3ad352759e7a78a90f6a2e2c3b7aa0f748`. The library dependency graph remains empty. Its real 37×23 12/16-bit routes check every sample, both allocation identities, observed caller writes and adapter reads, sentinel padding, different row strides, concurrent reader codestream identity, cancellation invalidation and sealed-write rejection. OpenJPEG 2.5.4 and CharLS 2.4.2 independently decoded the exported validation codestreams exactly. This is integration evidence; report counters and address identity alone do not close the separate allocator telemetry/mutation/file-I/O observation gates.

Hosted checkpoint `be98b30` passed all seven contract jobs and the published-reference workflow. Later working-tree extensions require their own CI results; those older runs are not attributed to uncommitted code.

Local extension validation passed 46 declarations in debug, AddressSanitizer and ThreadSanitizer builds. The preceding release run passed 45 declarations; the final extra test covers invalid preset thresholds and decoder overrides. Exact commands and exit codes are in `results/advanced-*.json`. The pinned predecessor comparison remains 78/90 byte-identical, with the same twelve low-precision threshold corrections.

The new mutation harness and hosted workflow retain the last input, deterministic seed/ordinal, heartbeat-supervised execution, per-entry counts and peak process RSS. It is a deterministic mutation campaign, not coverage-guided fuzzing. The workflow runs one hour separately for owned decode, caller-destination decode and inspection under AddressSanitizer. Until those jobs finish, the duration gate remains unexecuted. Sanitizer RSS is recorded as process memory including instrumentation, never used as ordinary allocator/copy accounting.

## Platform and performance follow-up

Hosted run 38034362483 at `683548174cd1ae2921e0c6348df44d00285b799e` passed all 14 jobs. In addition to the earlier matrix it ran scalar tests on Intel macOS 26, compiled the library against iOS/tvOS/watchOS/visionOS simulator SDKs, and built and ran a fresh URL-pinned consumer without a path dependency. SDK compilation is not simulator or physical-device runtime qualification.

Three ordinary release benchmark experiments retain their environment, every raw timing and per-case summary under `results/benchmarks-*`. The first measures `7383b12`; the later two record source hashes for successive sample-access optimisations. Each of 24 cases uses four alternating predecessor/successor blocks, each with five warm-ups and five timings (20 timings per direction). Source sample verification and deterministic byte comparisons are outside timing. Output sizes were unchanged for this corpus. Whole-process RSS was substantially lower for large successor cases, but is not allocator/copy telemetry.

The initial flat-image encoding slowdown exceeded fourfold on some large cases. Four-sample range checks, word comparisons and bounded word fills reduced it; the final experiment's 2048² and 4096×3073 flat decode medians were 0.49–0.54 times the predecessor's. Encoding still showed ratios of 1.13–1.39 on representative ramp/noise cases and 1.37–1.44 on 12-bit flat cases; full-16-bit flat encoding was 0.84–0.91. These are advisory workstation measurements with no assertion of controlled power/thermal conditions. Remaining regressions are not waived: bounded input/output validation, cancellation and owning-API overhead require further profiling and controlled qualification before release. No comparative performance marketing claim is made.

Word accesses use Swift SE-0349's unaligned trivial loads/stores (available since Swift 5.7), within prevalidated sample extents and synchronous borrows. The 256-sample cancellation bound is retained. Added tests cover invalid high bits in every packed lane and tail, both byte orders and nonzero padding. See [SE-0349](https://github.com/swiftlang/swift-evolution/blob/main/proposals/0349-unaligned-loads-and-stores.md) for the alignment contract.
