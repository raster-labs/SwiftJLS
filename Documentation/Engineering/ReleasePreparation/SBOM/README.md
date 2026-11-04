# Library and CLI SBOM qualification — 4 November 2026

Build-associated SBOM conformance is qualified through separately labelled
derived documents for clean revision
`53cea07be57fb030451a87bead9a3c3c0e863f04`. No codec, package manifest, CLI source,
or archived Swift 6.4 record was changed. This evidence covers the library-only
Milestone 5 candidate; DICOMKit integration remains pending.

| Check | Observed result |
| --- | --- |
| Build-associated generation | Four release builds exited 0: `SwiftJLS` and `swiftjls-cli`, each with SPDX and CycloneDX, `--sbom-filter all`, Swift Build and two jobs. |
| Raw SPDX 3.0.1 | Two schema findings per product: unsupported producer fields on package/product objects. Raw SHACL passes, but explicit checks identify the wrong SPDX `specVersion`, missing source licences and unsuitable package URLs. Neither SHACL alone nor generator exit 0 establishes conformance. |
| Raw CycloneDX 1.7 | Both schemas pass; duplicate product `bom-ref`, missing source licences and package/product URL defects remain explicit. |
| Derived outputs | All four official JSON Schema validations pass. Both SPDX documents pass the official OWL/SHACL model with warnings and informational results disallowed. Exact revisions, package/product identities, licences and references pass the separate semantic checks. |
| Negative controls | 20 checks pass, including schema-invalid fields, schema-valid semantic defects, an official SHACL failure, tampered raw/schema inputs, and output-preservation guards. |

[Generation receipt](results/generation.json) retains every build command, exit,
log hash, source hash and output hash. [Entry commands](execution.json) identify
the top-level invocations. Apple Swift **6.4.2**
(`swiftlang-6.4.2.1.9`), Xcode **27.2 / 27B52**, SDK **27.2** and arm64 macOS were
used; exact host/build details are in `results/`. Tools 6.2 and Apple OS 26.0
remain the package minima; this SBOM run does not qualify their runtime or
compiler compatibility. The built CLI reports `swiftjls-cli 1.1.0-dev.2`.

| Product | Derived documents | Qualification receipt |
| --- | --- | --- |
| `SwiftJLS` | [SPDX](derived/library/spdx.derived.json), [CycloneDX](derived/library/cyclonedx.derived.json) | [Library](derived/library/receipt.json) |
| `swiftjls-cli` | [SPDX](derived/cli/spdx.derived.json), [CycloneDX](derived/cli/cyclonedx.derived.json) | [CLI](derived/cli/receipt.json) |

Each [library transformation](derived/library/transformations.json) and
[CLI transformation](derived/cli/transformations.json) records before/after
values. The helper corrects the unsupported SPDX package properties and
specification version, assigns the generator licence to a software artefact,
adds source-backed Apache-2.0 assertions, removes the duplicate CycloneDX root
component, and identifies the immutable source with a canonical Swift package
URL. Product IDs remain unchanged; a product is not given an invented separately
resolvable package URL. The raw generator used the clean worktree's directory
name as its package identity. That identity and its original URLs remain in
the derived records, while source resolution explicitly uses
`pkg:swift/github.com/raster-labs/SwiftJLS@53cea07be57fb030451a87bead9a3c3c0e863f04`.
The source revision is not substituted with a purported stable release version.

The [supplement](derived/supplement.json) binds source licence/notice and observed
build artefacts. The library emits a 1,049,224-byte `SwiftJLS.o`; the separate
1,025,024-byte CLI has retained `otool` load commands. These commands identify
platform linkage, not a complete transitive SDK/runtime inventory, platform
licences, or installed runtime versions. There are no external runtime SwiftPM
dependencies. Development fixtures and oracle executables remain governed by
their separate provenance; they are not included as runtime dependencies.

The validators use the exact official schema/model/context bytes listed in
[validation-inputs/receipt.json](validation-inputs/receipt.json), reused from
the separately identified SwiftJLI qualification. Only validation inputs and
Apache-2.0 helper rules are reused, never SwiftJLI product/source claims.
[Adaptation provenance](../../../../Scripts/ReleasePreparation/SBOM/adaptation.json)
identifies the original helper. [Third-party notices](validation-inputs/README.md)
preserve all schema/model terms. Socket connections are denied during
validation; an unrecorded JSON-LD context is rejected.

Reproduce from a new clean checkout and fresh output/scratch directories:

```sh
python3 Scripts/ReleasePreparation/SBOM/generate.py \
  --repository /absolute/clean/SwiftJLS \
  --revision 53cea07be57fb030451a87bead9a3c3c0e863f04 \
  --output /absolute/new-evidence/results --scratch /absolute/new-scratch
python3 -m venv /absolute/validator-venv
/absolute/validator-venv/bin/python -m pip install \
  -r Scripts/ReleasePreparation/SBOM/requirements.txt
/absolute/validator-venv/bin/python Scripts/ReleasePreparation/SBOM/qualify.py \
  --raw /absolute/new-evidence/results \
  --inputs Documentation/Engineering/ReleasePreparation/SBOM/validation-inputs \
  --output /absolute/new-evidence/derived
```

For controls, copy the retained `validation-inputs` directory unchanged into the
new evidence directory, then run `controls.py --evidence /absolute/new-evidence
--output /absolute/new-evidence/controls` with the same validator interpreter.
[Pinned principal dependencies](../../../../Scripts/ReleasePreparation/SBOM/requirements.txt)
and the [complete executed environment](validator-packages.txt) are retained.
Every command refuses a completed output destination. The
[control receipt](controls/receipt.json) records the 20 individual results.

The initial derived attempt and executed helper are retained in `attempts/`.
Its raw-field checker misleadingly called the absent corrected version field
a source-revision difference. The final checker correctly recognises the raw
`software_internalVersion` and separately checks the other defects; it also
rejects an unexpected JSON-LD context. The raw files and generation record were
unchanged through both runs. Only the final `derived/` is qualification output.

The SPDX [serialization requirements](https://spdx.github.io/spdx-spec/v3.0.1/serializations/)
require structural and semantic validation. Its
[`specVersion` definition](https://spdx.github.io/spdx-spec/v3.0.1/model/Core/Properties/specVersion/)
describes the SPDX version, not a generator version. The
[CycloneDX 1.7 reference](https://cyclonedx.org/docs/1.7/json/) defines the BOM
structure and identity rules. This closes the scoped build-associated SBOM
conformance gate using the derived artefacts; raw SwiftPM conformance remains a
producer limitation. Physical-device qualification, support-policy acceptance,
release publication and DICOMKit integration are separate gates.
