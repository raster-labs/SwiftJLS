# SwiftJLS

JPEG-LS for the **Swift Image Compression Suite**.

**Status: native codec implemented; Milestone 4 qualification remains incomplete.** The common API now inspects, encodes and decodes unsigned 2–16-bit greyscale JPEG-LS in lossless and near-lossless modes. Compatible 8-bit or 16-bit image storage is borrowed directly; decode can write directly into caller storage. Explicit presets and row restart intervals are supported. Two-to-four-component planar/pixel layouts and non-interleaved/line/sample scans are implemented; RGB interpretation uses explicit SPIFF metadata or a supported HP transform marker. Lossless interleaved RGB supports HP1/HP2/HP3 for full-range 8/16-bit samples. Mapping tables, ordered APP/COM and SPIFF metadata, extended dimensions, explicit predecessor compatibility and subsampled line decoding are implemented; final qualification remains in progress. See the [milestone completion audit](Documentation/Engineering/CodecMigration/Completion.md), [profile matrix](Documentation/Engineering/CodecMigration/Parity.md) and [current validation](Documentation/Engineering/CodecMigration/Validation.md). The DICOM-padding and inactive-restart compatibility fixes merged in [PR 15](https://github.com/raster-labs/SwiftJLS/pull/15) on 13 October 2026.

At the 22 October fresh-owned factory candidate (`factory_002` on `codex/milestone-4-qualification`), **149 declarations in 27 suites** pass across all four host and hardware-virtualised native `macOS 26.0` configurations (`debug`, `release`, `ASan`, `TSan`), together with CLI, CharLS interoperability, five exact OS 26.0 simulator consumers, four non-Watch resource workloads and SDK builds; see [current validation](Documentation/Engineering/CodecMigration/Validation.md) and the [qualification archive manifest](Documentation/Engineering/CodecMigration/results/factory-qualification-2026-10-22.json) for full hashes and receipts. [Workspace accounting](Documentation/Engineering/CodecMigration/WorkspaceAccounting.md) attributes all 89 measured Linux operations while retaining universal `peakWorkspaceBytes = nil` (`pure_algorithm_workspace_complete = false`), and [performance and memory qualification](Documentation/Engineering/CodecMigration/Milestone4Performance.md) remains open (one confirmed incremental `p12-flat` `prepare_encode` regression, ten unresolved short comparisons and unresolved Apple RSS source contrasts). Historical [21 October `e6a6436` evidence](Documentation/Engineering/CodecMigration/Milestone4Performance.md#historical-21-october-e6a6436-performance-qualification) remains preserved; all physical-device tests and Milestone 5 remain pending, and the user verifies GitHub CI and merges the pushed branch.

SwiftJLS is the standalone successor to [JLSwift](https://github.com/Raster-Lab/JLSwift). The successor is intended to provide a harmonised API, explicit memory ownership, high-precision sample preservation and efficient shared-storage integration. It has no mandatory dependency on another suite library or CompressionFamily. Apache-2.0 licensing applies to these documents and subsequent authorised in-house implementation; third-party material retains its own terms.

## Swift 6.4 development candidate

The [22 October maintenance and factory follow-up](Documentation/Engineering/CodecMigration/RecentFixes.md) adds leading marker fill, explicit ICC discard, synchronous inspection callback rejection, an advanced [caller-workspace monochrome decoder](Documentation/QualifiedMonochrome.md), and the scalar-owned decode factory (`Image.writeAdmittedOwned` and `OwnedImageStorage.fillAndSealAdmittedOwned`) bypassing the private `ImageDestination` wrapper when `ScalarCodec.decode` has no supplied destination while keeping `ComponentCodec.decode`, caller-supplied destinations, leases, UUID identities, resource limits and cancellation checkpoints unchanged. Its source, validation, performance, memory and allocation evidence are recorded separately from earlier Milestone 4 measurements.

Current development version: **1.1.0-dev.2** ([VERSION](VERSION)); suite policy **0.10.0**. This increments the earlier unreleased 1.0.0 target and creates no release/tag. See the [current qualification record](Documentation/Engineering/CodecMigration/Validation.md) for executed checks and open gates; the [OS 27 record](Documentation/Engineering/OS27CLI/README.md) is historical. The historical [Milestone 1 evidence](Documentation/MILESTONE1.md) remains unchanged.

## Intended platform baseline

Swift 6.2 manifest minimum with Swift 6.4 as the qualified primary toolchain, Swift 6 language mode and complete concurrency checking. Apple OS deployment minima: macOS, iOS/iPadOS, tvOS, visionOS and watchOS 26.0. Apple Silicon is the primary optimisation target. macOS x86_64 and Linux ARM64/x86_64 are included with cleanly separated platform/architecture support. Ubuntu 24.04 is the initial Linux engineering baseline. CI covers Linux ARM64/x86_64, Apple Silicon/Intel macOS and Apple SDK compilation. Earlier simulator-runtime results retain their recorded revisions; physical-device admission remains unqualified.

## Start reading

**Moving an application from JLSwift? Read [MIGRATION.md](MIGRATION.md)** for dependency/import changes, the current API mapping, a runnable storage trial and the gates before production cutover. Production cutover requires the application acceptance matrix and the outstanding release qualification gates.

The scalar and component codec paths and predecessor extensions are migrated; final performance qualification remains in progress, with scoped workspace accounting recorded and unknown totals kept explicit. Start with [current evidence](Documentation/Engineering/CodecMigration/README.md) and [AGENTS.md](AGENTS.md).

- [Coding-agent entry point](AGENTS.md) and [codec-specific implementation plan](IMPLEMENTATION.md).
- [Suite policy](Documentation/SUITE_POLICY.md) and [common API](Documentation/COMMON_API.md).
- [Memory ownership and no-copy hand-off](Documentation/MEMORY_CONTRACT.md).
- [Unit, regression and security testing](Documentation/TESTING.md).
- [Performance gates](Documentation/PERFORMANCE.md), [platforms](Documentation/PLATFORMS.md) and [CLI](Documentation/CLI_CONTRACT.md).
- [History and source provenance](HISTORY.md), [change log](CHANGELOG.md), [security](SECURITY.md), [contributing](CONTRIBUTING.md) and [Apache-2.0 licence](LICENSE).

## Relationship to the suite

The four independent libraries are SwiftJ2K, SwiftJLS, SwiftJXL and SwiftJLI, all intended to live under Raster-Lab. A future optional umbrella adapts them for codec selection and in-process transcoding. The codecs do not depend on that umbrella. SwiftCompressionFamily is not part of this successor plan. The common contract is mirrored documentation plus behavioural tests, not a shared runtime package.

The package product and module are `SwiftJLS`; the CLI `swiftjls-cli` provides encode/decode/inspect/validate and help/version/capabilities. [The independent consumer](Examples/IndependentConsumer/Sources/Consumer/main.swift) compiles and runs against only this package, exercising native coding, exact padded 12-bit samples and destination identity. Retained, adapted and deferred predecessor features are listed in IMPLEMENTATION.md; the former inactive-DRI compatibility gap is fixed, with remaining qualification gates tracked in the completion audit. Nothing here changes the predecessor repository's current maintenance configuration.

## Native lossless example

```swift
import SwiftJLS

let descriptor = try ImageDescriptor.greyscale16(
    width: 3, height: 2, meaningfulBits: 12, rowBytes: 8)
let image = try ImageDestination.allocate(descriptor: descriptor)
    .writeUInt16 { x, y in x == 2 ? 4095 : UInt16(x + y * 3) }
let encoded = try await Encoder().encode(image)
let decoded = try await Decoder().decode(encoded.data)
let sample = try decoded.image.sampleUInt16(x: 2, y: 1) // 4095
```

This compresses and reconstructs the exact declared 12-bit samples. See the contract's scoped-pointer obligations before implementing custom storage adapters.

## Command-line help and manual

The CLI supports lossless and near-lossless greyscale coding through the bounded NRRD stream profile. `-h` / `--help`, command help, version and capability reporting describe current support. Five verbosity levels write diagnostics to stderr. See [CLI usage and installation](CLI.md); the installer updates the executable and manual together. Earlier OS 27 qualification records are historical; the current manifest and suite policy require OS 26.
