# History and provenance — SwiftJLS

## Predecessor maintenance-fix migration — 2026-10-22 (unreleased)

- Add the explicit `QualifiedMonochromeDecoder` caller-workspace profile with synchronous nonthrowing outcomes, checked budgets, deadline/cancellation and complete-stream admission.
- Accept leading marker fill, permit explicit ICC discard without altering pixels, and reject progress callbacks on synchronous inspection.
- Add independent fixtures, malformed-input and lifetime regressions, a development allocation probe with positive controls, and qualified-entry mutation coverage.
- Keep exact validation and allocation scope in [the maintenance-fix record](Documentation/Engineering/CodecMigration/RecentFixes.md). Earlier performance findings, physical-device admission and Milestone 5 remain open; the owner verifies CI and merges.

Entries below describe their dated checkpoints. Current merged/candidate revisions, completed milestones and open gates are in [the completion audit](Documentation/Engineering/CodecMigration/Completion.md); old CI billing and unsupported-codec statements are not current status.

## Documentation foundation — 17 September 2026

The owner chose four fresh repositories under Raster-Lab, with independent codecs, a common API and memory contract, MIT licensing and an optional adapter-based umbrella. The previous proposal for a new shared-foundation package, SwiftCompressionFamily 2.0.0, was superseded. The intended first stable release here is 1.0.0; no library version has been released or tagged by this foundation.

| Item | Recorded source |
| --- | --- |
| Predecessor | [Raster-Lab/JLSwift](https://github.com/Raster-Lab/JLSwift) |
| Default branch observed | main |
| Inspected source snapshot | [299b9a2e5bfe36ef104a3464a27d6c4c82874cc2](https://github.com/Raster-Lab/JLSwift/commit/299b9a2e5bfe36ef104a3464a27d6c4c82874cc2) |
| Highest stable-shaped tag observed | [v0.9.1](https://github.com/Raster-Lab/JLSwift/tree/v0.9.1) |
| Source-tree licence observed | Apache-2.0 |
| Successor licence | Apache-2.0, for owner-authorised in-house material (contract 0.8.0) |
| Inspection date | 2026-09-17 |

The tag and the inspected branch snapshot are separate references; this record does not assert they resolve to the same commit. Before migrating a tagged baseline, resolve annotated tags to commits and record the exact chosen SHA. The pinned snapshot above was read for documentation preparation; it was not independently built or regression-tested in this task.

## Migration provenance requirements

The coding agent must record source repository, commit, original path and successor path for each migrated subsystem, and distinguish copied/adapted in-house material from new implementation. Record retained tests, fixture licences and explicit product/feature dispositions. Keep predecessor bug history accessible through links. Do not import old tags, rewrite predecessor history or imply all historical commits have been relicensed.

The owner states the implementation is in-house and has authorised Apache-2.0 relicensing (contract 0.8.0; the foundation recorded this as MIT). Preserve accurate original copyright years and ownership. Audit any third-party dependencies, tools or fixtures separately. The root licence is not authority to remove another party's notices.

The originals are intended to become maintenance projects while new development moves here. No predecessor settings, README, branch, release, licence or archive flag was changed during this documentation preparation. Maintenance announcements and downstream DICOMKit/Voxelia migration are separate work.

## Swift 6.4 development upgrade — 19 September 2026

The owner assigned the successor upgrade before Milestone 2 and requested version increments. Starting from `d85332fd7a7ce67ae27f9806f3e4b3c09dd3bd9f`, the candidate requires Swift tools 6.4 in Swift 6 language mode, advances shared contract 0.2.1 to 0.3.0 and advances the unreleased 1.0.0 target to 1.1.0 (`1.1.0-dev.1` development identifier). Platform floors, public API signatures, licensing and codec milestone scope are preserved. This is not a release/tag. The [upgrade record](Documentation/Engineering/Swift64/README.md) keeps current evidence separate from the earlier historical reports.

## OS 27 and CLI foundation — 19 September 2026

Apple platform floors are 26.0; contract 0.5.0 reverses the 0.4.0 raise to 27.0, which no released SDK, toolchain or CI runner can currently validate. Development version 1.1.0-dev.2, common contract 0.5.0. The standalone `swiftjls` provides help/version/capabilities, five diagnostic levels and a matching section 1 manual installed/updated with the binary. Codec commands remain unavailable. Byte-order sample access uses explicit fixed-width integer conversion and does not raise the runtime floor. See [qualification and limitations](Documentation/Engineering/OS27CLI/README.md). Historical evidence and supplied documents remain unchanged.
## Apple floor restored to 26.0 — 20 September 2026

Contract 0.5.0 reverses the 0.4.0 raise of the Apple deployment floors to 27.0 and returns them to 26.0. Verification found that no generally available Xcode ships OS 27 SDKs, that no stable `macos-27` continuous-integration runner exists, and that Swift 6.4.0 rejects a 27.0 deployment target because its supported range ends at 26.5.x. Every OS 27 qualification claim was therefore unreproducible.

The raise was not an independent platform decision. Contract 0.4.0 adopted the OS-27-gated byte-order span overloads, and the floor moved so that they would compile. Contract 0.3.0 had already specified the correct treatment, explicit fixed-width integer endian conversion without raising the runtime floor, and that rule is restored. The compiler minimum returns to Swift 6.2 with Swift 6.4 retained as the qualified primary toolchain, because a manifest floor constrains consumer resolution and every current consumer resolves at 6.2.

Public signatures, ownership and fidelity semantics, milestone boundaries and Linux scope are unchanged. The OS 27 and Swift 6.4 records remain as history, marked superseded where they assert a platform baseline.

## Shared-storage rules refined from measurement — 20 September 2026

Contract 0.6.0 amends seven memory rules and adds one testing rule. Exploratory spikes ran the caller-storage question against all four predecessor codecs in both directions before any migration work, and every amendment comes from something those spikes measured or broke rather than from anticipated design.

The central finding reverses a standing assumption. `CopyPolicy.requireSharedStorage` is reachable in every codec, and each library reaches caller samples through exactly one stage, so pointing that stage at caller memory is small and local. What blocks the policy is the container each library exposes — `Data` per component, a packed `[UInt8]` with no row stride, a `[[Int]]` façade over an already-flat interior, or an initialiser that rejects any buffer that is not the packed frame size. A caller holding a padded plane cannot describe an image without first copying it. The `Image`/`ImageDescriptor` layer is therefore not packaging around working codecs; it is the Milestone 3 work.

The predecessor's lossless hot path already runs over a flat `UInt16` plane behind its `[[Int]]` public surface, so the work here is a row stride in two loops. `[[Int]]` is a façade at the boundary, not the working representation, and MEM-10's warning about it applies to the public type rather than to the codec.

Measured effects, all from a developer machine: live heap held after one JPEG 2000 decode fell from 16 MB in 6 blocks to 1 KB in 2 at 2048×2048, and for JPEG XL from 2 MB to nothing at 1024×1024; the JPEG 2000 output stage ran 9–35% faster writing the caller's plane; and on the encode side the copy a caller must make today costs 5.5 ms and 8 MB at 2048×2048 while the widening loop costs the same either way. Four defects surfaced during the work: inferred plane origins shearing padded multi-plane output, a shared encode that dropped its container wrapper and was caught only by comparing bytes rather than samples, a harness that bound an owner to storage released on the same line, and an address-sanitizer run reporting 100 MB live on a path holding nothing, which a probe traced to the sanitizer quarantining freed blocks.

The spikes are exploratory and are not proposed for merge into the predecessor repositories. No platform, milestone, release or CLI decision changes, and continuous integration remains blocked, so none of these results is a release gate.

## Decision D1 — codec libraries stay where they are, 20 September 2026

Contract 0.7.0 settles the programme's open architectural question. The shipping codec libraries are the existing repositories; the four contract repositories hold the shared documents, the reference implementation of the shared image layer and the cross-codec conformance harness. No codec source is relocated and nothing is deleted.

The Milestone 3 spikes decided it. All four codec interiors proved contract-capable through single-point changes, and the obstacle to caller-owned storage is the public image type rather than the codec, so the remaining work is additive and identical in size wherever it is done. Migration would have paid, on top of that identical work, the relocation of roughly 219,000 lines of codec source and 184,000 lines of tests together with fixtures and cross-codec oracles, with no continuous integration available to catch what such a move breaks. The contract repositories hold about 1,000 lines of source each, so little built work is given up; three in-house consumers already resolve the existing libraries by URL at pinned released versions, and none references a contract repository.

JLSwift keeps its codec, its 15,112 lines of source and its 19,976 lines of tests, and gains the contract surface additively. Its lossless hot path already runs over a flat `UInt16` plane, so the shared-storage work is a row stride in two loops. It is Apache-2.0 while this repository is MIT; POL-07 authorises relicensing but the predecessor was deliberately relicensed to Apache-2.0 on 26 August 2026, so the owner should settle this rather than let it drift. VoxeliaValidation consumes it by URL.

Two matters are referred to the owner rather than assumed: the Apache-2.0 and MIT split between the existing libraries and the contract repositories, which POL-07 authorises resolving but which should be a deliberate choice; and the inventory and splitting of auxiliary predecessor products under POL-05. The decision rests on documentation evidence gathered on one machine and authorises no codec milestone or release.

## Decision D2 — codec libraries relocate here, 22 September 2026

Contract 0.8.0 supersedes Decision D1. The owner has reaffirmed the repository foundation v0.1.0 as the guidance for this migration and instructed that the codecs move into the successor repositories. Under document precedence rule 1 the owner's current explicit decision outranks a previous contract revision.

JLSwift relocates here: 15,112 lines of source and 19,976 lines of tests, with its fixtures and oracles. It has no external package dependency, and its lossless hot path already runs over a flat `UInt16` plane. Its public `PNGSupport` and `TIFFSupport` helpers and its PNM/DICOM CLI commands are the auxiliary products needing a POL-05 disposition. VoxeliaValidation and DICOMKit consume it by URL.

This codec is the migration pilot: it is the smallest of the four, it has no dependency to extract, and it is the codec named in the suite's first cross-codec proof. What it teaches is applied to the other three.

The sequence is a final JLSwift release at v0.10.0, then relocation, then a first stable 1.1.0 here once the TEST-07 gates pass, then a maintenance window on the predecessor, then its archive. JLSwift is not renamed or deleted: this repository's HISTORY.md and MIGRATION.md pin its commits and source files by permalink, and those links are the provenance record.

D1's measurements are retained as the risk register rather than discarded. The continuous-integration objection is unresolved and becomes a precondition: the organisation's Actions billing remains locked, a re-run of JLSwift's CI on 22 September 2026 completed with `steps=0`, and no codec source moves before CI executes and passes here. This record authorises no codec milestone and no release.

## Contract 0.9.0 — floor decision and programme sequence, 22 September 2026

Decision D3 keeps the Apple deployment floor at 26.0 and places the cost of adoption on each consumer at its own cutover. DICOMKit consumes JLSwift from 0.9.0 at macOS 15 / iOS 18 / tvOS 18 / visionOS 2; VoxeliaValidation pins it at revision `299b9a2` on the same floors. JLSwift is the supported route for those consumers until they raise their floors and re-point, and it is archived only after the last of them has moved.

This repository is the pilot: Milestones 2 to 5 run here first, and what they teach is applied to the other three. The predecessor's current release candidate is v0.10.0-rc.1 (tag at `a5757d3`; `main` has since advanced to `13591f9` with SPDX header corrections); its promotion is the predecessor's own release task and is not authorised here.

The continuous-integration precondition from 0.8.0 stands. Actions billing remained locked on 22 September 2026, so every workflow in the suite is written and unexecuted. No codec source moves here before CI executes and passes here.

## Predecessor parity extensions — 10 October 2026

Added bounded mapping tables/continuations, ordered APP/COM and SPIFF metadata, extended dimensions, explicit predecessor syntax/default compatibility, and subsampled line decoding with declared plane sampling. The [parity record](Documentation/Engineering/CodecMigration/Parity.md) distinguishes normative output, known-producer legacy input, hardened malformed-input rejection and remaining qualification. New codec code is native; CharLS mapping support remains an isolated pinned test oracle. No release, consumer cutover or predecessor change is implied.

## Migration completion audit — 12 October 2026

PR 14 merged as `f481f6031279b8ca5c51f559df33cc66a9e4e06b`. The separately tested DICOM-padding candidate `3f16daf61f88bc136b6db478fd13abac234af4f5` remains in draft PR 15. The audit reconciles stale toolchain/platform/HP statements and records one remaining inactive-DRI compatibility gap, controlled performance/peak-workspace and physical-device gates. Milestones 4–5, stable release and consumer cutover are not complete. The seven common contracts, historical evidence, versions and fixture provenance are preserved.

## Migration qualification follow-up — 12 October 2026

Runtime checkpoint `4008f213cc749514300de55dfc17b389fbd3b561` closes the inactive-DRI compatibility gap exposed by the earlier same-day audit. The final local suite has 80 tests in ten suites; debug, release, ASan and TSan pass. The follow-up adds bounded concurrent resource evidence and repeats advisory release measurements without relaxing acceptance thresholds. See [the updated completion audit](Documentation/Engineering/CodecMigration/Completion.md) for final hosted results and unresolved requirements. Physical Watch testing is explicitly excluded from this task, not claimed as performed. Historical evidence and common contracts remain unchanged.

## Intermediate Milestone 4 optimisation and workspace accounting — 14 October 2026

Production checkpoint `940da40b867cd14f7888492162c13e237609d991` replaces hot-loop context array mutation with a noncopyable packed owner, uses bounded inline scheduling and native-endian sample views, fuses lossless precision validation, and removes redundant descriptor construction and completed-lease cleanup. Near-lossless and HP validation, resource limits, cancellation and exact sample semantics remain enforced. The four host and native macOS 26.0 test configurations each pass 103 declarations in 18 suites; exact OS 26.0 simulators and resource workloads also pass.

At the later `c330b73` checkpoint, [workspace accounting](Documentation/Engineering/CodecMigration/WorkspaceAccounting.md) completes the scoped source inventory and 89-operation requested-heap attribution; universal heap/stack/allocator totals remain unknown. The powered 63-case campaign is complete with unresolved decode regressions, recorded in [the closeout](Documentation/Engineering/CodecMigration/Milestone4Closeout.md) and [final evidence](Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-14.json). All physical-device tests remain pending; Milestone 5 is deferred. The owner performs CI verification and merge in GitHub after the branch is pushed. Historical results and failed diagnostic attempts retain their original scope.

## Final Milestone 4 implementation checkpoint — 14 October 2026

Pushed source `c330b731e250d6b4c054c1c6a91fa9894e32a8c3` additionally avoids redundant singleton-plane uniqueness, sampling-array and single-plane overlap containers. Canonical frame admission retains original failure diagnostics without allocating temporary descriptors. Row-entry checks cover the first bounded lossless scan and short column-zero decode run; subsequent scans and long-run post-parse checks remain. New tests verify invalid component mappings and observable cancellation boundaries.

All four host and native arm64 macOS 26.0 configurations pass 108 declarations in 20 suites. The hardware-virtualised native guest also passes CLI (73 payload/103 process), independent consumer and resource checks. Five exact OS 26.0 simulator consumers, four resource profiles and SDK builds pass. The powered 63-case campaign is complete; remaining decode regressions keep performance qualification open. [The closeout](Documentation/Engineering/CodecMigration/Milestone4Closeout.md) and [final evidence](Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-14.json) record those outcomes. Historical 103/104-declaration checkpoints retain their source scope. All physical-device tests and Milestone 5 remain pending; the owner verifies CI and merges in GitHub.

## Native sample-interleaved decode qualification — 21 October 2026

Production checkpoint `bee49a2ad47eae4ea149bdced2043b7a45df3dae` selects borrowed native UInt16 component writers once for compatible sample-interleaved decode. General layout fallbacks and bounded cancellation remain unchanged. New tests cover odd origins, precision/NEAR combinations, fallback layouts, sentinels and the actual write frontier.

All 110 declarations in 21 suites pass separately in debug/release/ASan/TSan on the host and native arm64 macOS 26.0 (25A354) guest. Both CLI suites, independent/resource consumers, five exact OS 26.0 simulator consumers, four resource profiles and SDK builds pass. The refreshed 89-operation workspace matrix fully attributes observed codec requested-heap allocations, including 352 bytes of bounded descriptor growth in 18 profiles and no pixel copy. Universal heap/stack/allocator totals remain unknown.

The [performance record](Documentation/Engineering/CodecMigration/Milestone4Performance.md) and [intermediate hashed evidence](Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21.json) retain the controlled measurements, all triggered investigations and their final disposition. The earlier 14 October evidence remains historical. Physical-device testing is pending by owner direction; Milestone 5 is deferred. The owner verifies CI and merges the pushed branch.

## Bounded setup performance qualification — 21 October 2026

Production checkpoint `e6a6436c692f5af226bffceb70b7ee65c774edf3` removes redundant singleton mapping, header scan tracking and owned-admission work, and initialises bounded decoder gradient intervals directly. Public APIs, limits, lifecycle and executor policy remain unchanged. All 120 declarations in 24 suites pass separately in four host/native macOS 26.0 configurations; CLI, exact OS 26.0 simulator/resource and SDK checks pass.

The final 89-profile requested-heap matrix is fully attributed. Algorithm-state peaks are unchanged from `bee49a2`; metadata traffic and inspection peaks decrease. The fixed 128-pair short comparison places 20 of 24 metrics within the measured gate, including all preparation metrics. Four pinned decode comparisons and the incremental 16-bit noise decode finding remain unresolved; faster deep results do not waive them. [Current qualification](Documentation/Engineering/CodecMigration/Milestone4Performance.md) retains final-source evidence and limitations. Physical-device testing remains pending, Milestone 5 is deferred, and the owner verifies CI and merges.

The source-pinned final ASan mutation run passes at least one hour per owned/into/inspect entry with 981 seeds and 24,076,372 total iterations. All counters reconcile, stderr is empty, and original ZIP digests plus extracted payloads are verified. The final 15-case larger campaign places all 60 pooled and 240 paired timing ratios below 1.05; its one size flag is proven to be 44 SPIFF header bytes with identical entropy and two successful full-sample cross-decodes. These results do not close the short decode findings.
