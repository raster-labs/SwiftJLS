# SwiftJLS

JPEG-LS for the **Swift Image Compression Suite**.

**Status: native scalar migration in progress.** The common API now inspects, encodes and decodes unsigned 2–16-bit greyscale JPEG-LS in lossless and near-lossless modes. Compatible 8-bit or 16-bit image storage is borrowed directly; decode can write directly into caller storage. Explicit presets and row restart intervals are supported. Colour/interleaving, mapping extensions, metadata and remaining platform/release qualification are still pending. See [migration evidence](Documentation/Engineering/CodecMigration/README.md). No stable release has been published.

SwiftJLS is the standalone successor to [JLSwift](https://github.com/Raster-Lab/JLSwift). The successor is intended to provide a harmonised API, explicit memory ownership, high-precision sample preservation and efficient shared-storage integration. It has no mandatory dependency on another suite library or CompressionFamily. Apache-2.0 licensing applies to these documents and subsequent authorised in-house implementation; third-party material retains its own terms.

## Swift 6.4 development candidate

Current development version: **1.1.0-dev.2** ([VERSION](VERSION)); suite policy **0.10.0**. This increments the earlier unreleased 1.0.0 target and creates no release/tag. See the [current qualification record](Documentation/Engineering/OS27CLI/README.md) for adopted features, exact Xcode/Swift Build evidence and open platform gates. The historical [Milestone 1 evidence](Documentation/MILESTONE1.md) remains unchanged.

## Intended platform baseline

Swift 6.2 manifest minimum with Swift 6.4 as the qualified primary toolchain, Swift 6 language mode and complete concurrency checking. Apple OS deployment minima: macOS, iOS/iPadOS, tvOS, visionOS and watchOS 26.0. Apple Silicon is the primary optimisation target. macOS x86_64 and Linux ARM64/x86_64 are included with cleanly separated platform/architecture support. Ubuntu 24.04 is the initial Linux engineering baseline. These are requirements, not completed qualification claims.

## Start reading

**Moving an application from JLSwift? Read [MIGRATION.md](MIGRATION.md)** for dependency/import changes, the current API mapping, a runnable storage trial and the gates before production cutover. Codec replacement remains blocked until later milestones supply the required JPEG-LS capabilities.

The scalar codec is now migrated; advanced extensions and the first real cross-codec shared-storage proof remain in progress. Start with [current evidence](Documentation/Engineering/CodecMigration/README.md) and [AGENTS.md](AGENTS.md).

- [Coding-agent entry point](AGENTS.md) and [codec-specific implementation plan](IMPLEMENTATION.md).
- [Suite policy](Documentation/SUITE_POLICY.md) and [common API](Documentation/COMMON_API.md).
- [Memory ownership and no-copy hand-off](Documentation/MEMORY_CONTRACT.md).
- [Unit, regression and security testing](Documentation/TESTING.md).
- [Performance gates](Documentation/PERFORMANCE.md), [platforms](Documentation/PLATFORMS.md) and [CLI](Documentation/CLI_CONTRACT.md).
- [History and source provenance](HISTORY.md), [change log](CHANGELOG.md), [security](SECURITY.md), [contributing](CONTRIBUTING.md) and [Apache-2.0 licence](LICENSE).

## Relationship to the suite

The four independent libraries are SwiftJ2K, SwiftJLS, SwiftJXL and SwiftJLI, all intended to live under Raster-Lab. A future optional umbrella adapts them for codec selection and in-process transcoding. The codecs do not depend on that umbrella. SwiftCompressionFamily is not part of this successor plan. The common contract is mirrored documentation plus behavioural tests, not a shared runtime package.

The package product and module are `SwiftJLS`; the CLI `swiftjls-cli` provides encode/decode/inspect/validate and help/version/capabilities. [The independent consumer](Examples/IndependentConsumer/Sources/Consumer/main.swift) compiles and runs against only this package, exercising native coding, exact padded 12-bit samples and destination identity. Features from the predecessor are migration candidates whose exact coverage must be verified; see IMPLEMENTATION.md. Nothing here changes the predecessor repository's current maintenance configuration.

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
