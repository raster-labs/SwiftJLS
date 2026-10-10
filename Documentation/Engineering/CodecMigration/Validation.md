# Predecessor migration validation — 10 October 2026

The native predecessor profiles, mapping tables and metadata are implemented in the owning SwiftJLS API. The implementation is reviewable in [draft PR 14](https://github.com/raster-labs/SwiftJLS/pull/14). Stable-release qualification remains open for controlled performance and target-device memory measurements. This record does not authorise release, tagging, merging, predecessor archival or consumer cutover.

## Revisions and reproducibility

- Codec checkpoint: `da5bd84b13430226a3cbee192f2c32792da368a1`. Later evidence/harness/documentation commits do not change `Sources/SwiftJLS`; the final source manifest records the hashes.
- Predecessor: `15aa75164145414f3d5ffb801401c52d40cc5bcc`.
- Suite policy: 0.10.0, tools 6.2, primary Swift 6.4, Swift 6 language mode, Apple OS 26.0. All seven shared documents are unchanged.
- Oracles: CharLS 2.4.2 `36dd3307e070d8fbc765c3ba890b7e681046fa39`; mapping/extended support from isolated CharLS `04e44bb760632104ab1209593eea3f8c20ac11e5`; published T.87 reference V1.00 under its conformance-only licence. None is a production dependency.
- Local host: macOS 27.0.1 arm64, Mac16,5, 64 GiB, Apple Swift 6.4 (`swiftlang-6.4.0.34.1`), CommandLineTools SDK 27.0. Local testing loads the bundled Swift Testing macro plugin explicitly; no concurrency check is disabled.

The [parity matrix](Parity.md) defines profile scope and explicit legacy interpretation. Fixture manifests under `Tests/SwiftJLSTests/Fixtures` retain geometry, hashes, provenance and independent expected samples. Source attribution is in the adapted files and `../MigrationPreflight/scalar-provenance.json`. Historical checkpoint results remain in README.md and are not substituted for current-source checks.

## Executed checks

| Check | Result | Evidence |
| --- | --- | --- |
| Local debug and release | 73 declarations in nine suites pass in each build | `results/parity-final73-debug.json`, `results/parity-final73-release.json` |
| Separate AddressSanitizer and ThreadSanitizer | All 73 pass in each; exit zero | `results/parity-final73-asan.json`, `results/parity-final73-tsan.json` |
| Hosted contract matrix | All 14 jobs pass with the final 73-test suite; codec sources unchanged | [run 38050318859](https://github.com/raster-labs/SwiftJLS/actions/runs/38050318859) |
| Independent interoperability | 482 scalar, 372 component and 136 new mapping/extended/legacy successor outputs pass | [run 38049181028](https://github.com/raster-labs/SwiftJLS/actions/runs/38049181028); `results/parity-*-results.json` |
| CLI payload/transaction checks | 61 pass, including metadata-preservation rejection with empty stdout and unchanged existing output | `results/parity-final-cli.json` |
| Layout mutation sensitivity | Baseline passes; all eight wrong stride/order variants fail, ten aggregate failing expectations | `results/parity-layout-mutations.json`; accessor hashes unchanged at the final codec checkpoint |
| Scalar allocator mutation sensitivity | Deliberate hidden copies leave functional assertions passing; allocator detects all ten sample-array allocations | Ordinary-release CI artifact `cross-codec-copy-mutation` |
| In-process file observation | No prohibited application file events during either real cross-codec route | Ordinary-release CI artifact `cross-codec-file-observation` |

The hosted matrix includes Swift 6.2/6.4 on Linux x86-64/ARM64, native Apple Silicon and Intel macOS, all four Apple simulator SDK builds, shared-document hashes and separate local/URL-pinned consumers. The real SwiftJ2K development-only consumer uses pinned `be4e7a3ad352759e7a78a90f6a2e2c3b7aa0f748`, with sample/precision checks, both allocation identities, observed borrows, sentinel padding, differing strides, concurrent reader encodes and cancellation. The shipped package has no dependencies.

There are 981 retained JPEG-LS files. The duration campaign was started with the original 969; twelve later nonzero subsampling fixtures extend compatibility tests without changing codec source. Independent inputs comprise the earlier 819 plus 60 mapping and four extended-dimension fixtures. Actual predecessor regression files additionally cover 36 HP precision/interleave profiles, 36 combined mapping/HP lossless/near profiles, two continuation and two large-dimension files, plus the earlier six HP files. Two subsampled zero-run files are checked against the predecessor, and two native encoder goldens have independent decode checks. Twelve additional nonzero subsampled block/noise fixtures cover 8/12/16 bits and NEAR 0/3 against the unchanged predecessor decoder, with padded planes in both byte orders and sentinel gaps. Their fixture-only producer adapts the predecessor encoder scheduler; it is not an independent standards oracle. Counts describe distinct evidence categories, not 981 independent conformance vectors.

The published reference separately accepted 36 explicit-preset outputs and 33 two-component line outputs. MAXVAL 1/2 and two-component sample coding retain local-only qualification; the available reference does not cover those cases. Four 16-bit/three-byte-entry mapping candidates are excluded because the pinned CharLS oracle splits entries at continuation boundaries contrary to T.87. These exclusions are not counted as passing interoperability.

## Apple runtime execution

The native simulator consumer checks precision, caller allocation identity, padded output, HP, mapping metadata/re-encoding, explicit mapping, predecessor combined profiles, Watch limits and cancellation. The all-four-platform checkpoint run [38048492787](https://github.com/raster-labs/SwiftJLS/actions/runs/38048492787) passed. Final codec-checkpoint rerun [38049188670](https://github.com/raster-labs/SwiftJLS/actions/runs/38049188670) also passed all four. `results/parity-apple-runtime.json` records Swift 6.3.3 / Xcode 26.6, iOS 26.4.1, tvOS/visionOS 26.5 and watchOS 26.4. Deployment targets are 26.0; this is not runtime evidence on the exact 26.0 releases.

visionOS exposed a SwiftPM cross-target defect: it emitted ELF linker options and a 26.26.0 minimum. Failed attempts are retained as failures. The successful workflow compiles and links the exact library sources with the explicit Swift driver, XR SDK and `arm64-apple-xros26.0-simulator`, then executes the signed consumer inside the simulator. The other platforms use SwiftPM against their explicit simulator SDK/triple. Simulator execution is not physical-device qualification.

## Duration/security campaign

[Run 38049186415](https://github.com/raster-labs/SwiftJLS/actions/runs/38049186415) is executing the final 3,600-second AddressSanitizer campaign separately for owned decode, caller-destination decode and inspection. It cycles standard, explicit legacy and mapped-output configurations over the 969 seeds. This is deterministic mutation with heartbeat supervision, not coverage-guided fuzzing. Retained last input, generator seed, counts and process RSS make findings reproducible. Duration remains pending until all three jobs complete successfully; sanitizer RSS is not ordinary allocation accounting.

Earlier scalar, component and standard/legacy HP campaigns passed at their recorded revisions. The HP completion is archived in `results/fuzz-hp-hour.json`. Superseded mapping runs 38047378074 and 38048361249 were cancelled; neither counts as a duration pass.

## Allocation, copies and workspace

The Linux ordinary-release copy probe intercepts `memcpy`/`memmove` reads from the pixel owner's numeric range only during the actual scoped encoder borrow. Ten normal profile/interleave cases observe zero source-copy bytes; each matching deliberate-copy case observes the whole source capacity (210, 442 or 1,326 bytes). The self-test must observe a real copy before zero results are accepted. Inlined copies are outside this interceptor, so the independent allocator mutation and source review remain essential.

The scalar cross-codec trace classifies allocation stacks and finds no `OwnedImageStorage` sample-array allocation beneath scalar encode or supplied-destination decode. The broader profile pass also finds zero sample-owner arrays under either codec boundary across ten encode/caller-decode combinations and 98 additional legacy/extended/mapped/subsampled caller decodes. It classifies 922 stack types and 17,213 allocation calls referencing SwiftJLS. Counts include setup/runtime containers; they are not frame counts or peak bytes. [Run 38050318859](https://github.com/raster-labs/SwiftJLS/actions/runs/38050318859) passes all 14 jobs on the unchanged codec sources, including this stronger probe; `results/parity-profile-heap-*.json` retains the raw-profile hash and classifications. The first broad run classified five intentional owned outputs as forbidden caller-path allocations. That run failed; the corrected harness explicitly allocates every destination before calling decode, preserving the strict classifier. This is a boundary-specific allocation observation, not a claim that codec operations allocate nothing. Contexts, gradient tables, headers, metadata, compressed output and bounded predictor rows are expected. Lossless scalar encode has no predictor rows; near-lossless uses two UInt16 rows; interleaved encode uses two rows per component. Decode uses causal samples in final output. Mapping and HP are applied in final output or per-pixel arithmetic locals.

The metadata admission allowance is 32 times retained metadata bytes, covering archives, table copies and container overhead conservatively. It is an admission ceiling, not measured peak workspace. Full per-operation peak pixel/workspace accounting, concurrent stress at target-device limits and arbitrary inlined copy-byte accounting remain unqualified. Report fields that are unknown remain unknown.

## Performance and outstanding release gates

An updated ordinary-release comparison runs the pinned predecessor and final successor public APIs on 24 scalar cases: odd non-square, 512², 2048² and 4096×3073, 12/16 bits, flat/ramp/deterministic noise. Each case has four alternating process blocks, five warm-ups per block and twenty timings per direction. Every sample is checked outside timing; raw timings and environment are retained. The complete run is archived in `results/parity-final-benchmark/`. No local build/sanitizer/tracing job overlapped; a brief CLI regression and documentation/artifact work did. Developer-workstation runs remain advisory: power/thermal and unrelated host load are not controlled. No sanitizer, tracing or coverage run is used as throughput evidence.

For 2048² and 4096×3073 cases, successor/predecessor median ratios were 1.28–1.42 for 12-bit flat encode, 1.14–1.21 for ramp encode, 1.24–1.34 for noise encode, and 0.81–0.90 for full-16-bit flat encode. Flat decode ratios were 0.50–0.56; ramp decode 1.18–1.22 and noise decode 1.02–1.10. Per-case distributions and whole-process RSS are retained; reduced RSS is not direct workspace/copy evidence.

Six large-noise encoded sizes differ by at most 0.0007%; all other benchmark sizes match. `results/parity-benchmark-large-interop.json` independently checks every sample of both producers with CharLS and cross-decodes both directions successfully. Byte identity is not claimed for these streams. The migrated regular-mode encoder normalises the context sign before modular reduction; the predecessor did the reverse, permitting different half-range error representations. Earlier chronological text claiming unchanged sizes must not be applied to this corpus/revision.

Stable release is not qualified until controlled representative performance/peak-workspace measurements and physical Apple-device admission tests are complete. Large-case encoding regressions remain unresolved; no threshold is relaxed and no safety-cost waiver is invented. Colour/near-lossless performance coverage also needs controlled measurement. The existing owner-approved PNG/TIFF helper and extended CLI deferrals remain in force. No end-user application is migrated by this PR.
