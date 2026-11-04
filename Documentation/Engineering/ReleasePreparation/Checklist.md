# Milestone 5 library closeout — 4 November 2026

The owner has left DICOMKit integration pending and assigned completion of the
other library Milestone 5 tasks. The implementation scope is the five release
preparation items in [IMPLEMENTATION.md](../../../IMPLEMENTATION.md), not a new
codec milestone or stable publication. Each item below has an implementation,
repeatable validation and retained evidence. Final hosted checks for the latest
workflow changes are recorded separately before handover.

The runtime baseline is `a9bf9e95933fc8135bbcc3922d6ce831ddfe2057`, migration
predecessor `15aa75164145414f3d5ffb801401c52d40cc5bcc` and qualified extension
predecessor `d17545284a23e93f3d884a18f1046c4e305daa35`. Suite policy 0.10.0,
tools 6.2, primary Swift 6.4, Swift 6 mode and Apple OS 26.0 remain in force.
VERSION remains `1.1.0-dev.2`. No runtime source, API, root package manifest,
fixture, common contract or supplied Swift 6.4 document changes are included.

| Assigned library item | Completion evidence and limits |
| --- | --- |
| Clean versioned consumption | [Preparation runner](../../../Scripts/ReleasePreparation/prepare.py) tests a temporary SemVer tag in a disposable repository and the public repository at the exact full revision, with both lockfiles checked. All 23 commands, seven consumer/example executions, 103 CLI process checks and 73 payload checks pass on their recorded revisions, including both hosted compiler lines. No project tag is created. [Independent audits](README.md) retain command, source, lockfile and artifact identities. |
| Documentation and examples | Native independent consumer and exact README/MIGRATION Swift examples execute; all eight example manifests parse with explicit dependency names. CLI help, VERSION, diagnostics, payloads, staged installer/update and manual discovery are covered. The two typed test-expression corrections retain the same expected values. The compiler runner now uses the native API and current platform floor. |
| Migration guide | [MIGRATION.md](../../../MIGRATION.md) maps dependency/import, storage, fidelity, metadata, error and profile changes, with executable acceptance examples and an explicit implemented/planned boundary. Application-specific DICOMKit acceptance and dependency cutover remain pending by the owner's direction. No integration candidate is included in this PR. |
| Licence and fixture notices | [Provenance audit](Provenance.md) verifies 14 fixture manifests, 2,819 fixture/generator files, seven contracts, 20 migration records and 57 pinned predecessor source comparisons; eleven corruption/preservation controls pass. [Library and CLI SBOM qualification](SBOM/README.md) adds four clean build-associated outputs, four independently validated derived schemas, two SPDX semantic-model validations and twenty negative/provenance controls. Raw generator defects and all third-party schema/model notices are preserved. |
| Release gates and handover | [RELEASE.md](../../../RELEASE.md) defines candidate selection, version/manual alignment, packaging, security/support, platform and publication acceptance. GitHub private reporting is enabled. The support policy is prepared for maintainer acceptance. [PR 18](https://github.com/raster-labs/SwiftJLS/pull/18) carries reviewable changes and exact checks. Stable publication and owner merge remain separate actions. |

The final preparation audit also corrected incomplete Apple fallback compiler
inputs. Three workflows formerly selected 28 files and omitted all 11 qualified
decoder files. They now compile all 39 sources and typecheck an external
`QualifiedMonochromeDecoder` client. The [local regression evidence](results/apple-sdk-source-coverage/README.md)
reproduces the old missing-API failure, then passes visionOS simulator SDK and
Watch `arm64_32` SDK compilation/linking with the complete source list. These
checks use installed 27.2 SDKs targeting 26.0; they are not physical-device runs.

The [pre-follow-up hosted snapshot](results/ci-53cea07b.json) records all sixteen
checks passing on `53cea07be57fb030451a87bead9a3c3c0e863f04`. It does not establish
the new Apple workflow coverage; the subsequent CI result must be read at its
own revision. SBOM generation uses that clean commit and binds every production
input, licence, notice, manifest and version hash. Later evidence/workflow changes
do not alter those compiled product inputs.

## Sample, copy, lifetime and performance review

The independent consumer checks all six padded 12-bit samples, destination
identity and declared zero hand-off copies/pixel allocations. Hosted copy
controls and the corrected mutation classifier require exactly ten injected
sample-array allocations; the baseline remains zero. This declaration check
and measured allocation evidence have distinct scopes. Existing source-bound
sample, lifetime/race, sanitizer, CharLS oracle, 89-profile workspace and
candidate005 performance evidence remains linked from the
[qualification audit](../CodecMigration/Completion.md). Unknown allocator,
runtime and stack totals remain unknown. This milestone changes preparation
tools, workflow coverage and documentation, so no codec performance or memory
improvement is claimed and no unchanged hot path is re-benchmarked.

## Outstanding acceptance boundaries

- **Physical devices:** no physical iPhone, iPad, Watch or other required device
  was available. SDK compilation, simulator execution and virtualised macOS
  results do not close this Milestone 4 prerequisite for stable release.
- **Release decisions:** maintainer acceptance of the proposed first-stable
  support policy, owner review/merge and a separately authorised stable release
  remain open. No tag, GitHub release or predecessor archival is performed.
- **DICOMKit:** integration, its additional compatibility changes and application
  validation remain excluded and pending. Separate worktrees and evidence are
  preserved; their results are not attributed to this library candidate.
- **Tooling limits:** Swift 6.2 Linux Swift Build test launching and consumer
  linking remain failed in the retained attempts. The explicitly selected
  native-engine compatibility passes do not relabel those failures. Raw SwiftPM
  SBOM conformance remains a producer limitation; only the labelled derived
  documents satisfy the scoped qualification checks.

The library preparation work can be reviewed independently of these acceptance
boundaries. Full milestone/release acceptance is not declared complete while
the required physical-device and release decisions remain outstanding.
