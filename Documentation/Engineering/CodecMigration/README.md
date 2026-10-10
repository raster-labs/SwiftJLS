# Codec migration checkpoint — 10 October 2026

The user authorised completion of the library migration. This checkpoint implements part of that work; it is not a release or a claim that all five milestones are complete.

Source: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Target base: SwiftJLS `91092f78b492e332a7ec200e68b76604088e44fb`. Suite policy 0.10.0 governs over stale repository-specific platform prose. The manifest remains tools 6.2, Swift 6 mode and Apple OS 26. The seven common documents remain unchanged.

## Implemented and independently checked

- Native scalar single-component JPEG-LS, 2–16 meaningful bits in unsigned 16-bit storage, lossless and NEAR 1…min(255, MAXVAL/2).
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

Multi-component layouts and interleaving, restart/mapping/colour-transform extensions, metadata semantics, cross-codec shared-storage harness, fuzz duration, controlled performance/memory measurements, complete native platform/device qualification and fresh remote consumption remain work in progress. Unsupported combinations throw; no runtime reference codec is used. Stable release/tagging is a separate explicit task.
