# Release preparation — source, fixture and licence inventory

Current status (updated 10 November 2026): Suite policy **0.11.0** (`POL-07`) restores the **MIT** licence (`Copyright (c) 2026 Raster Images Private Limited`) for in-house source, scripts, synthetic fixture manifests and documentation while retaining [NOTICE](../../../NOTICE) for copyright attribution. `Scripts/ReleasePreparation/provenance.py` and `provenance-controls.py` now validate the MIT `LICENSE` digest (`9a6740d5798b34f0e390df81825748674ef4f00678a12b35cb23061684103363`), retained `NOTICE` digest (`dbd05e5f8a4c0c7174126171c45c94fdea34a19ee7cd846e8c3646a0a3f7e9d3`), contract `0.11.0` shared-contract hashes, `SPDX-License-Identifier: MIT` source headers, and `MIT` synthetic fixture declarations across all 2,819 fixture/generator hash comparisons. The 4 November 2026 audit record and its archived JSON reports (`results/provenance-2026-11-04.json` and `results/provenance-controls-2026-11-04.json`) remain preserved below as historical baseline evidence.

Audit date: 4 November 2026. Source baseline: SwiftJLS `a9bf9e95933fc8135bbcc3922d6ce831ddfe2057`. Suite policy at audit: **0.10.0**, with each of the seven shared documents retaining its recorded revision. This is a release-preparation audit of the committed baseline; the separate, uncommitted CharLS optimisation work is outside its scope.

The [machine-readable audit](results/provenance-2026-11-04.json) passes **2,819 fixture/generator hash comparisons across 14 manifests**, covering every non-JSON file under `Tests/SwiftJLSTests/Fixtures`, with zero missing, altered or uncovered files. It also passes all seven shared-contract digests, checks 20 migrated-source records and their current destination licence headers, and verifies **57 original-source hash comparisons** against pinned JLSwift Git objects: 20 migration records and 37 source records for the `qualified-d175` fixture producer. These are comparison counts, not unique source-file or codec-test counts.

The [failure controls](results/provenance-controls-2026-11-04.json) pass all eleven cases: the unchanged baseline, seven deliberately invalid temporary copies, the restored baseline, preservation of an existing report and a partial audit without predecessor objects. The invalid copies change a fixture, remove a fixture, add an unrecorded fixture, change a shared contract, falsify a predecessor source digest, remove `NOTICE` and alter its attribution. Each fails for the expected reason. Repository fixtures and historical manifests remain unchanged.

## Licences and source provenance

The shipped package has no external package dependencies in [Package.swift](../../../Package.swift). Its in-house source and documentation use [MIT](../../../LICENSE) (contract 0.11.0; [Apache-2.0] at the 4 November 2026 audit), with Raster Images Private Limited attribution retained in [NOTICE](../../../NOTICE). The [migration manifest](../MigrationPreflight/scalar-provenance.json) identifies the original paths, byte hashes and adaptations from JLSwift [`15aa75164145414f3d5ffb801401c52d40cc5bcc`](https://github.com/raster-labs/JLSwift/tree/15aa75164145414f3d5ffb801401c52d40cc5bcc). That pinned predecessor's `LICENSE` and `NOTICE` retain Apache-2.0 and the same copyright holder; the owner authorised MIT relicensing of in-house material in contract 0.11.0. Successor source is adapted, so original and current source digests are recorded separately; equality between them is not expected.

Fixtures retain their individual manifest declarations of original synthetic MIT samples (updated from Apache-2.0 under contract 0.11.0). This audit checks those declarations and their hashes; it does not relicense an external oracle, import third-party implementation code or change published predecessor history. The root MIT licence does not override an external tool's terms.

| Material | Retained origin and terms | Distribution boundary |
| --- | --- | --- |
| Scalar/component/HP fixtures | Synthetic samples; CharLS 2.4.2 at `36dd3307e070d8fbc765c3ba890b7e681046fa39`, BSD-3-Clause oracle | Checked-in samples/codestreams and original Apache-2.0 adapters only. CharLS is separately built for tests; its licence stays with that checkout. |
| Mapping and extended-dimension fixtures | Synthetic samples; CharLS development mapping API at `04e44bb760632104ab1209593eea3f8c20ac11e5` | Same isolated-oracle boundary; unsupported three-byte mapping chunks remain documented in the manifest. |
| Explicit scalar presets and two-component line fixtures | Synthetic samples; ITU T.87 HP conformance reference V1.00, archive SHA-256 `c54f20d167485399d2094d3375151d2ec31535d4c32d92fb929b15fc364ea41a` | The existing [reference runner](../../../Scripts/Interop/reference-windows.py) downloads the reference into temporary storage and retains its original notices for conformance testing. No reference implementation or executable is shipped. |
| Legacy profiles, mapping/HP combinations and subsampled streams | Synthetic compatibility fixtures generated from pinned JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; Apache-2.0 | Compatibility evidence, including the explicitly adapted fixture-only subsampling scheduler; not an independent standards oracle. |
| Qualified monochrome regressions | JLSwift `d17545284a23e93f3d884a18f1046c4e305daa35`; retained generators and synthetic Apache-2.0 samples | Producer source and fixture hashes are retained in the nested provenance manifest. High-NEAR predecessor defaults are compatibility evidence. |
| Fixed storage goldens | SwiftJLS `9ca35c57c6f355af547f48a6598ad4efa7f9f492`; synthetic Apache-2.0 fixtures | Fixed-configuration byte identity for layout mutation controls; original independent-decoder evidence remains revision-scoped. |

Reproduction and oracle limitations are recorded in [Scripts/Interop/README.md](../../../Scripts/Interop/README.md). Development-only cross-codec consumers and benchmark/reference tools do not enter the shipped package dependency graph. Their existing terms and pins remain applicable when reproducing those experiments.

## Fixture index

Each link below is the authoritative retained manifest. Counts include encoded files, reference/reconstructed samples, tables and, for the qualified corpus, retained Swift generators.

| Manifest | Hash comparisons |
| --- | ---: |
| [manifest.json](../../../Tests/SwiftJLSTests/Fixtures/manifest.json) — scalar lossless, near-lossless, restart and explicit presets | 1,464 |
| [components.json](../../../Tests/SwiftJLSTests/Fixtures/components.json) | 693 |
| [components-reference.json](../../../Tests/SwiftJLSTests/Fixtures/components-reference.json) | 99 |
| [components-hp.json](../../../Tests/SwiftJLSTests/Fixtures/components-hp.json) | 108 |
| [components-legacy-hp.json](../../../Tests/SwiftJLSTests/Fixtures/components-legacy-hp.json) | 18 |
| [mapping.json](../../../Tests/SwiftJLSTests/Fixtures/mapping.json) | 240 |
| [extended.json](../../../Tests/SwiftJLSTests/Fixtures/extended.json) | 8 |
| [legacy-profiles.json](../../../Tests/SwiftJLSTests/Fixtures/legacy-profiles.json) | 72 |
| [legacy-combined.json](../../../Tests/SwiftJLSTests/Fixtures/legacy-combined.json) | 72 |
| [legacy-extra.json](../../../Tests/SwiftJLSTests/Fixtures/legacy-extra.json) | 6 |
| [subsampled-nonzero.json](../../../Tests/SwiftJLSTests/Fixtures/subsampled-nonzero.json) | 24 |
| [low-max-near-default.json](../../../Tests/SwiftJLSTests/Fixtures/low-max-near-default.json) | 3 |
| [storage-goldens.json](../../../Tests/SwiftJLSTests/Fixtures/storage-goldens.json) | 2 |
| [qualified-d175/provenance.json](../../../Tests/SwiftJLSTests/Fixtures/qualified-d175/provenance.json) | 10 |
| **Total** | **2,819** |

## Reproduction and limits

Run from the SwiftJLS repository root, using a separate JLSwift clone containing both pinned revisions:

```sh
git clone --filter=blob:none --no-checkout https://github.com/raster-labs/JLSwift.git /tmp/SwiftJLS-m5-predecessor
python3 Scripts/ReleasePreparation/provenance.py --predecessor /tmp/SwiftJLS-m5-predecessor --output Documentation/Engineering/ReleasePreparation/results/provenance-2026-11-04.json
python3 Scripts/ReleasePreparation/provenance-controls.py --predecessor /tmp/SwiftJLS-m5-predecessor --output Documentation/Engineering/ReleasePreparation/results/provenance-controls-2026-11-04.json
```

Both Python commands exited **0** in this audit. Use a fresh clone destination and fresh output paths when reproducing: an existing report is never overwritten. The audit returns 1 for a detected failure and 2 for a partial inventory without `--predecessor`; a partial result does not satisfy the source-provenance gate. JSON records contain file-level expected/actual hashes, source revision, script digest and errors. The scripts do not fetch or execute an oracle, alter a repository setting or modify audited inputs; a partial Git clone can fetch pinned blobs during `git show`.

There is no codec, public API, sample/copy/lifetime or hot-path change here, and no new performance or memory measurement is claimed. Digest equality establishes preservation of the recorded material. Existing interoperability, memory, security and platform results retain their own revisions and limitations. This inventory does not establish physical-device qualification, complete release readiness or permission to create a stable tag.
