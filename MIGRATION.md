# Migrating applications from JLSwift to SwiftJLS

The successor uses Swift tools 6.2 with Swift 6.4 as the primary toolchain and Apple OS 26 deployment floors. See the [Swift 6.4 upgrade record](Documentation/Engineering/Swift64/README.md) for development versioning and validation; current codec availability is unchanged.

This guide is for application maintainers and coding agents changing a dependency. Library implementation work follows [AGENTS.md](AGENTS.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md).

**Current status: native scalar JPEG-LS supports unsigned greyscale and two to four components in 8-bit or 16-bit containers, with 2–16 meaningful bits.** Lossless and bounded near-lossless encoding and decoding use the common owning API. Padded rows, both byte orders and caller-supplied decode storage are supported. This is an ongoing migration: non-interleaved, line and sample scans are implemented, as are explicit presets/MAXVAL and non-interleaved row restarts. RGB interpretation requires a supported SPIFF header; otherwise multiple components retain explicit uninterpreted JPEG-LS IDs. HP1/HP2/HP3 are supported for lossless interleaved full-range 8/16-bit RGB. Mapping tables, APP/COM/SPIFF metadata, extended dimensions and subsampled line decoding are now available; see the [parity and compatibility record](Documentation/Engineering/CodecMigration/Parity.md). Keep production consumers on their qualified predecessor revision until their complete acceptance matrix passes. See [current evidence](Documentation/Engineering/CodecMigration/README.md).

The active migration uses suite policy **0.10.0** and predecessor commit **`15aa75164145414f3d5ffb801401c52d40cc5bcc`**. Older examples below record the original integration mapping. Compare your application's actual pinned revision before applying it; other predecessor versions may differ. The successor's implemented surface is in [Sources/SwiftJLS](Sources/SwiftJLS); executed coverage and unavailable gates are in [Documentation/MILESTONE1.md](Documentation/MILESTONE1.md).

## Dependency and deployment changes

| Item | Predecessor at the inspected commit | Successor now |
| --- | --- | --- |
| Repository / package | `Raster-Lab/JLSwift` / `JLSwift` | `Raster-Lab/SwiftJLS` / `SwiftJLS` |
| Library product / import | `JPEGLS` / `import JPEGLS` | `SwiftJLS` / `import SwiftJLS` |
| Executable | `jpegls` (target `jpeglscli`) | `swiftjls-cli` provides encode/decode/inspect/validate and help/version/capabilities |
| Swift | Tools 6.2, Swift 6 language mode | Tools 6.2, primary Swift 6.4, Swift 6 language mode; complete concurrency checking |
| Apple deployment minima | macOS 12, iOS 15 | macOS, iOS/iPadOS, tvOS, visionOS, watchOS 26.0 |

Evidence: [pinned predecessor manifest](https://github.com/Raster-Lab/JLSwift/blob/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2/Package.swift), [current manifest](Package.swift), [platform qualification requirements](Documentation/PLATFORMS.md). An application supporting older Apple systems must retain a compatible dependency path or deliberately raise its deployment target before linking SwiftJLS. Build-only evidence does not establish device/runtime support.

For a local migration trial, add `.package(path: "../SwiftJLS")` to the consumer's package dependencies and `.product(name: "SwiftJLS", package: "SwiftJLS")` to its executable/application target. Adjust the relative path to your checkout. Alternatively add the local package through Xcode. Keep `JPEGLS` alongside it while the application adapter is being developed.

For a remote trial, use `https://github.com/Raster-Lab/SwiftJLS.git` and pin an actual reviewed full commit SHA available in that repository. Record it in the migration review and commit the application's resolved dependencies. **Do not use a `from: "1.1.0"` requirement yet:** 1.1.0 is intended, not published. SwiftJLS has no dependency on another suite codec or umbrella; adding all four is unnecessary.

## API mapping and current availability

The predecessor calls below are verified in its pinned [encoder](https://github.com/Raster-Lab/JLSwift/blob/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2/Sources/JPEGLS/JPEGLSEncoder.swift), [decoder](https://github.com/Raster-Lab/JLSwift/blob/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2/Sources/JPEGLS/JPEGLSDecoder.swift) and [image types](https://github.com/Raster-Lab/JLSwift/blob/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2/Sources/JPEGLS/Encoder/JPEGLSPixelBuffer.swift). The right column describes the implemented scalar profile, not feature parity.

| Existing application usage | Successor direction | Available now |
| --- | --- | --- |
| `MultiComponentImageData.grayscale(pixels:bitsPerSample:)`; component `pixels: [[Int]]` | Validated `ImageDescriptor`, owning `ImageDestination`, sealed `Image` | Synthetic storage and unsigned greyscale `writeUInt16` / `sampleUInt16` helpers work |
| `JPEGLSEncoder()`; `encode(_:configuration:) throws -> Data` | `try SwiftJLS.Encoder(configuration:)`; `try await encode(_:options:) -> EncodedImage` | Lossless and near-lossless encode; compressed bytes are `result.data`, diagnostics `result.report` |
| `JPEGLSDecoder().decode(_:) throws -> MultiComponentImageData` | `try SwiftJLS.Decoder()`; `try await decode(_:options:) -> DecodedImage` | Native scalar decode; samples are `result.image`, diagnostics `result.report` |
| Application header/parser calls | `Decoder.inspect(_:options:) -> ImageInfo` | Bounded one-to-four-component JPEG-LS inspection |
| Application-managed decoded buffer | `Decoder.decode(_:into:options:)` | Direct final decode; preflight rejection performs no write |
| `JPEGLSEncoder.Configuration(near: 0, ...)` | `EncoderConfiguration(mode: .lossless)` | Exact lossless coding implemented |
| Nonzero `near` | `.nearLossless(maximumAbsoluteError:)`, in integer sample units | Nonpositive bounds are invalid; positive bounds up to min(255, MAXVAL / 2) are implemented |
| `JPEGLSError` cases | `CodecError.category` and separate `CancellationError` | Remap handling explicitly; no case-for-case compatibility alias |

Interleave modes, presets/MAXVAL, restart intervals, mapping tables and colour transforms are predecessor-specific settings requiring separate capability checks and tests when migrated. `CodecOptions(restartIntervalLines:preset:interleaveMode:)` supports row restart intervals, validated explicit MAXVAL/T1/T2/T3/RESET values and `.none`/`.line`/`.sample` interleaving. Restarts require `.none`. Both lossless and near-lossless modes support restarts. Decoder parameters come from the codestream; encoder-only overrides are rejected by the decoder. Do not drop an old setting silently, infer support from an enum case, or replace near-lossless output with another fidelity mode.

## Runnable migration trial

Use this as `main.swift` in a separate executable consumer targeting macOS 26 or another supported deployment target, linked only to the local SwiftJLS library. It copies a small predecessor-shaped array into new owned storage, validates precision and encodes a JPEG-LS codestream.

```swift
import SwiftJLS

// Stand-in for one predecessor component's pixels; explicitly declared 12-bit.
let oldPixels: [[Int]] = [[0, 1, 4095], [4095, 2048, 2]]
let width = 3
let height = 2
guard oldPixels.count == height,
      oldPixels.allSatisfy({ $0.count == width }) else {
    throw SwiftJLS.CodecError(.invalidArgument, "Unexpected source geometry.")
}
let limits = try SwiftJLS.ResourceLimits(
    maximumDecodedBytes: 1024, maximumPixels: 64,
    maximumDimension: 8, maximumMemoryBytes: 1024 * 1024)
let descriptor = try SwiftJLS.ImageDescriptor.greyscale16(
    width: width, height: height, meaningfulBits: 12,
    rowBytes: 8, limits: limits)
let destination = try SwiftJLS.ImageDestination.allocate(
    descriptor: descriptor, limits: limits)
let allocationID = destination.storage.allocationID
let image = try destination.writeUInt16 { x, y in
    guard let value = UInt16(exactly: oldPixels[y][x]), value <= 4095 else {
        throw SwiftJLS.CodecError(.invalidArgument, "Sample exceeds 12-bit range.")
    }
    return value
}
guard image.storage.allocationID == allocationID,
      try image.sampleUInt16(x: 2, y: 0) == 4095 else {
    throw SwiftJLS.CodecError(.internalFailure, "Storage trial failed.")
}
let encoder = try SwiftJLS.Encoder()
let encoded = try await encoder.encode(image, options: .init(resourceLimits: limits))
let decoded = try await SwiftJLS.Decoder().decode(encoded.data, options: .init(resourceLimits: limits))
guard try decoded.image.sampleUInt16(x: 2, y: 0) == 4095 else {
    throw SwiftJLS.CodecError(.internalFailure, "Sample preservation failed.")
}
print("Native lossless migration trial passed.")
```

Run the consumer headlessly with Xcode's selected toolchain using `xcrun swift run --package-path /path/to/consumer`. See the existing [independent consumer manifest](Examples/IndependentConsumer/Package.swift) for a complete package layout. Its repository example can also be run with `xcrun swift run --package-path Examples/IndependentConsumer` from this repository. Record the actual compiler, SDK, command and result; this checks native sample and storage integration.

## Application behaviour to preserve

- **Subsampled components:** the predecessor's `MultiComponentImageData` can represent component dimensions derived from sampling factors. Successor planes now declare horizontal/vertical sampling factors and exact ceiling dimensions. Subsampled line decoding writes those planes directly; encoding subsampled planes remains unsupported, matching the predecessor encoder limitation. Do not silently upsample or relabel them.
- **Precision and interpretation:** preserve declared precision, dimensions, component roles, signedness, byte order, strides and metadata. For the first storage trial use unsigned greyscale, 16-bit storage and explicit meaningful bits (for example 12); values are low aligned and unsigned high bits must be zero. Do not infer precision from observed maxima, truncate an `Int`, apply display windowing or treat a `UInt16` view as proof of signed codec support. A descriptor accepting a layout does not mean a codec can encode it. Explicit non-power-of-two MAXVAL presets preserve the declared container precision. Independent published-reference qualification covers MAXVAL 10, 100, 255, 1000, 4095 and 65535; MAXVAL 1 and 2 currently have local invariant coverage only.
- **Ownership and copying:** `Image` retains a sealed immutable owner. A destination is single-use; initialise all samples, then share only read access. A failed write/cancelled write cannot publish a partial image. Preflight rejection before a write leaves the reservation usable. Never let a scoped pointer escape, cross `await`, or become an asynchronous owner. The sample above performs an explicit array-to-storage copy; it is not an end-to-end no-copy migration. Custom adapters must satisfy the [memory contract](Documentation/MEMORY_CONTRACT.md); default `requireSharedStorage` forbids a hidden full-frame repack during codec hand-off.
- **Concurrency and limits:** migrate synchronous call sites to structured `try await` calls and retain owners for the operation. Codec operations use `@concurrent`, one scalar worker and bounded cancellation/deadline checks; progress currently reports operation start and completion. Keep UI state on its actor; progress closures are `@Sendable`. Set finite `ResourceLimits` at construction and operation boundaries, include padding and concurrent work in budgets, and propagate `CancellationError`. Tests exercise deadline/cancellation rejection; controlled throughput qualification remains separate.
- **Errors and publication:** map `CodecError.category` to application outcomes instead of parsing messages or reusing the predecessor enum. Separate invalid arguments, unsupported features/layouts, resource exhaustion, unavailable storage/backends and cancellation. Do not turn an unsupported codec into an empty file, successful result or silent lossy fallback. Publish final application output only on successful completion.

## Features that need a separate migration decision

The predecessor has public `PNGSupport` and `TIFFSupport` helpers ([PNG source](https://github.com/Raster-Lab/JLSwift/blob/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2/Sources/JPEGLS/PNGSupport.swift), [TIFF source](https://github.com/Raster-Lab/JLSwift/blob/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2/Sources/JPEGLS/TIFFSupport.swift)). SwiftJLS supplies neither. Inventory direct use of these helpers and retain or separately replace the relevant application functionality.

The predecessor CLI also contains PNM/DICOM handling, batch/conversion/verification and benchmarking commands. The successor [CLI](CLI.md) provides native greyscale encode/decode through NRRD plus inspect/validate/help/version/capabilities. The [CLI contract](Documentation/CLI_CONTRACT.md) is not a predecessor command compatibility promise. Retain existing scripts until replacement commands are implemented and tested. DICOM transfer syntax, frame encapsulation, signed pixel interpretation and object metadata remain application responsibilities; the common `Image` metadata is not a DICOM object model. No SwiftJLS native transcoder is provided.

## Staged rollout and acceptance checklist

1. Record predecessor and successor commits, contract version, deployment targets, current package products/imports, codec options and auxiliary helper/CLI usage. Capture application regression fixtures with expected samples, precision, metadata and failure behaviour; use licensed synthetic or de-identified data.
2. Introduce an application-owned codec boundary and a separate successor trial target. During coexistence, use explicit module qualifications such as `JPEGLS.JPEGLSEncoder` and `SwiftJLS.Encoder`. Keep predecessor routing as the production default and make successor selection explicit. Common names in different suite modules are different Swift types.
3. Compile the contract trial and the application's adapter with strict Swift 6 checks. Test odd dimensions, padded rows, 12/16-bit extremes, invalid ranges, ownership, repeated writes, cancellation and resource rejection. Keep unsupported colour and signed modes blocked. Record copy/allocation costs of any legacy array conversion.
4. **After actual codec delivery**, check encode/decode/inspect capabilities and each required feature; a boolean alone does not prove an option/layout combination. Validate old compressed files with the successor and new files with both the predecessor and an independent JPEG-LS implementation. Lossless acceptance requires exact logical samples and interpretation; near-lossless requires the declared error bound. Identical compressed bytes are not a general lossless requirement.
5. Qualify application targets, memory, cancellation, concurrency, performance and persistence/output handling before a controlled rollout. Keep rollback to the pinned predecessor until all required features pass. Do not re-encode a stored corpus merely to rename the library.
6. Remove the predecessor dependency, imports and obsolete scripts only after every required call site is covered. Update application lockfiles, user documentation and release notes with deliberate deployment/behaviour changes and remaining limitations.

For coding agents: an application-migration task does not authorise implementing later codec milestones, changing common contracts, inventing missing APIs, tagging a release or declaring feature parity. Report modified call sites, exact revisions, commands/results, unavailable features and deferred acceptance gates. Stop production cutover at the current capability boundary while completing the authorised adapter/documentation work.

### Multi-component layout mapping

Planar, pixel-interleaved and mixed unsubsampled planes are read/written through their explicit component map and sample/pixel/row strides. RGB uses exactly `[.red, .green, .blue]` and `.rgb`; the encoder writes a SPIFF v2 RGB header. Otherwise use `.unknown` and unique `.uninterpreted("JPEG-LS:<id>")` roles, where `<id>` is the canonical decimal UInt8 component ID. Unlabelled three-component input is not silently interpreted as RGB. Alpha and ICC colour interpretation remain unsupported; opaque application payloads are preserved. Explicitly sampled planes support the predecessor line-decoder path.

Independent CharLS qualification covers 231 component fixtures and 330 successor outputs (including restart variants). Two-component line coding additionally has 33 published-reference fixtures with explicit normative presets; two-component sample coding has local error-bound tests only because the available oracles do not cover that profile. The published HP reference disagrees with normative implicit defaults for one narrow 2-bit near-lossless case, so explicit parameter evidence is distinguished from implicit-default interoperability. See the [component manifest](Tests/SwiftJLSTests/Fixtures/components.json) for precise coverage and hashes. SPIFF directories and density/aspect metadata are preserved; ordered APP/COM payloads and required mapping metadata follow the explicit policies in the parity record.

### HP colour transforms

`CodecOptions(restartIntervalLines: 0, interleaveMode: .line, colourTransform: .hp1)` enables a reversible HP transform; `.hp2`, `.hp3` and `.sample` are also qualified. Encoding requires lossless RGB, 8 or 16 meaningful bits and no explicit preset. Decoding accepts full-range presets, as used by CharLS for 16-bit images. Other precisions, transformed near-lossless data, non-interleaved transformed scans and reduced MAXVAL are rejected. An APP8 `mrfx` marker declares RGB even without SPIFF. This is the private HP convention, not a claim of JPEG-LS Part 2 conformance.

The pinned predecessor's `JPEGLSColorTransformation` formulas differ: HP1/HP2 omit the half-range bias, and HP3 uses a different lifting/order. Its `mrfx` marker does not distinguish those legacy semantics. Do not assume its transformed files are interchangeable with the independently qualified convention. For known legacy transformed assets, construct `Decoder(configuration: .init(codecOptions: .init(restartIntervalLines: 0, hpInterpretation: .legacyJLSwift)))`, then re-encode the recovered RGB image with the standard encoder. This explicit compatibility path currently covers the same lossless interleaved 8/16-bit profile. The flag is decoder-only. SwiftJLS does not guess between incompatible interpretations of the same marker. The 36 independent transform fixtures and all successor outputs were checked with CharLS 2.4.2. This compatibility limitation remains part of migration acceptance.
