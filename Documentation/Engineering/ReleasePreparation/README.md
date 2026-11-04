# Milestone 5 evidence — 4 November 2026

The library-only Milestone 5 preparation work is implemented. The [item-by-item closeout](Checklist.md) maps the original assignment to evidence; DICOMKit integration remains pending by owner direction. [RELEASE.md](../../../RELEASE.md) defines its checks and open gates. Stable publication, physical-device qualification and application cutover remain uncompleted.

Baseline: SwiftJLS `a9bf9e95933fc8135bbcc3922d6ce831ddfe2057`, migrated from JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; qualified extension baseline `d17545284a23e93f3d884a18f1046c4e305daa35`. Suite policy 0.10.0 governs. The seven common documents, supplied compiler-upgrade documents and historical evidence remain unchanged. Codec source, root package manifest and fixtures remain byte-identical to the committed baseline; unrelated uncommitted optimisation work is excluded in a separate worktree.

The reusable compiler runner now tests the actual native codec through the maintained independent consumer, with tools 6.2 and macOS 26.0 in its generated manifest. Its former Milestone 1 stub assertion and OS 27 floor could not validate the current library. An explicitly named dependency also permits differently named worktrees. Archived copies remain historical.

Retained [core](results/core/report.json) and [local-consumer](results/local-consumer/report.json) reports preserve their exact commands and source hashes. Initial host checks use Apple Swift 6.4.2 (`swiftlang-6.4.2.1.9`), Xcode 27.2 (`27B52`), arm64 macOS 27.0.1 (`26A434`). They are host results, not physical-device or minimum-OS execution:

| Command | Outcome |
| --- | --- |
| `python3 Scripts/validate-swift64.py --checks consumer --output /tmp/SwiftJLS-m5-consumer-validation` | Exit 0; native independent consumer checks all six padded 12-bit samples, destination identity and declared zero hand-off copies/pixel allocations. |
| `python3 Scripts/validate-swift64.py --checks debug,release --jobs 2 --output /tmp/SwiftJLS-m5-core-validation` | Exit 0; 17 commands exit 0; clean/incremental builds and 157 test declarations pass in each configuration, zero failures/skips. |

The full [preparation report](results/consumption-002/report.json) passes on committed `68b0b6385bca135e1532a7e22ceb00992af549b9`: all 23 commands exit 0, the documented local consumer and all three consumers in each of the local-SemVer/hosted-revision packages run successfully, both lockfiles resolve exactly that commit, and all 103 CLI process checks plus 73 payload checks pass. The [independent audit](results/consumption-002/independent-audit.json) verifies source/tree hashes, both lockfiles, every CLI result and absence of source-repository tags. Seven negative unit controls pass. All eight checked-in example manifests parse successfully; their explicit dependency names support arbitrary checkout directory names.

The [first attempt](results/consumption-001/report.json) failed at its lockfile assertion: SwiftPM records a file URL as an absolute path with `localSourceControl` kind. The runner now validates that normalisation and the source-control kind explicitly; the hosted URL still requires exact URL equality. This is a harness correction, with the failed evidence preserved.

The [committed-source provenance audit](results/provenance-68b0b638.json) exits 0: 2,819 fixture/generator hashes, seven contract hashes, 20 migration records and 57 original-source comparisons all pass. The eleven retained provenance controls detect deliberate corruption and preserve previous evidence. [Device discovery](results/device-discovery-summary.json) reports no connected devices; none was tested.

Initial hosted CI exposed two preparation problems. Git rejected the container-mounted checkout as having different ownership; the job now trusts only its exact `GITHUB_WORKSPACE` path, with [failure artifacts](results/ci-preparation-68b0b638/) retained. Swift 6.2 also timed out type-checking the existing extended-dimension expected-sample expression in `QualifiedMonochromeTests`; the expression is split into typed intermediates without changing expected values or assertions. These CI results are separate from the passing host checks above. No new sanitizer, hour-long mutation, independent oracle, controlled benchmark, allocator, minimum-OS or physical-device run is implied by the checks above. Those historical and open gates remain in [the qualification audit](../CodecMigration/Completion.md).

The initial GitHub API check returned private reporting `enabled: false` on 4 November. The owner selected that channel; the later verification recorded below confirms it is enabled. The release-preparation support proposal is concrete but awaits maintainer acceptance in the release task. The remaining policy review is a release gate, not a failed codec test.

The focused test-expression follow-up retains its [host command report](results/swift62-test-expression/host-commands.json), [Linux commands](results/swift62-test-expression/linux-commands.json) and [test-only patch](results/swift62-test-expression/test-only.patch). The Swift 6.4.2 host passes all 15 qualified-monochrome tests. Linux Swift 6.2.4 compiles the full corrected test target with Swift Build, but that engine then fails to launch its expected `.xctest` executable (`posix_spawn`, exit 1). This failed engine run is retained as a tooling limitation; it is not counted as a test pass or hidden behind another engine. Native-engine verification is recorded separately.

The final [test-expression report](results/swift62-test-expression/report.json) records 15/15 passing tests on the Swift 6.4.2 host with Swift Build and 15/15 on Linux ARM64 Swift 6.2.4 with the native engine, zero failures/skips. The first native attempt failed while copying resources through a macOS bind mount; the passing run uses container-local copied source/fixtures. Swift 6.2 Swift Build also fails the independent-consumer link with a missing `SwiftJLS.o`; that result remains unqualified. The release-preparation runner now accepts an explicit engine selection, and CI names the Swift 6.2 compatibility engine (`native`) separately from primary Swift 6.4 (`swiftbuild`). No automatic retry/fallback hides these failures.

The hosted macOS runner at the next checkpoint uses Swift 6.3.3/Xcode 26.6, despite its old job label. It found the same type-check complexity in the neighbouring mapping-table expectation; that expression now also uses typed intermediate values, preserving all five mapping inputs, the mask and the exact-array assertion. Its [focused evidence](results/swift63-test-expression/report.json) retains the original failure and passing 15-test host check. The CI job label now says “selected Xcode toolchain”, matching what it actually records.

The [Swift 6.4 Linux preparation artifact](results/ci-preparation-76500941/) confirms all seven consumer/example runs before the manual-discovery check failed: the minimised Ubuntu image diverts `/usr/bin/man` to a notice that exits zero without searching for manuals. CI now exposes the installed `/usr/bin/man.REAL` as `/usr/local/bin/man` when present, inside that disposable job container. The staged manual path/content assertions remain unchanged. This setup failure is retained separately from codec or packaging failures.

The [Linux manual-check verification](results/linux-cli-man/report.json) builds the ordinary release CLI using pinned native ARM64 Swift 6.2.4 and passes all 103 process checks with the real `man-db` executable. It preserves image/source hashes, exact arguments, installation logs and both original CI manual-stub failures. All environment changes are inside disposable containers; the host manual installation and test assertions are unchanged.

Hosted Linux Swift 6.4.2 with the explicit Swift Build engine passes the complete preparation check at `69f31fe8bf79ba679df6482ea9c2b78572a89751`: 23 commands, nine committed input hashes, both exact dependency locks, seven example/consumer executions, 103 CLI process checks and 73 payload checks. The [independent audit](results/ci-swift64-69f31fe8-independent-audit.json) records run/job/artifact identities and verifies the real manual reader, unchanged source tags and `release_ready: false`. [The downloaded artifact contents](results/ci-swift64-69f31fe8-evidence.zip) are repacked losslessly for retention; this archive has its own digest in SHA256SUMS.json.

The corresponding hosted Swift 6.2.4 x86_64 Linux/native-engine preparation also passes all 23 commands, both exact locks, seven consumer/example runs and 103 process plus 73 payload checks at `69f31fe8`. Its [independent audit](results/ci-swift62-69f31fe8-independent-audit.json) verifies nine committed input hashes and preserves the separate engine identity; [artifact contents](results/ci-swift62-69f31fe8-evidence.zip) are repacked losslessly. Both macOS jobs, all Linux core/compiler jobs, Apple SDK jobs and CharLS passed at that checkpoint. The sole remaining CI failure was the existing allocation-detector matcher described below; this checkpoint is not reported as an entirely passing CI run.

The [copy-mutation classifier report](results/copy-mutation-classifier/report.json) preserves the original baseline/mutant archives and the failed detection. The trace already contains exactly ten injected sample-array allocations; the private `OwnedImageStorage` initializer carries a Swift file discriminator that the old literal matcher missed. The corrected matcher accepts only the exact owner initializer with an optional 32-hex private discriminator. Helper, array and owner frames must still occur in the same allocation stack, the helper must appear in the allocation section, and the total must be exactly ten. Six additional negative-control tests pass; original artifact replay gives zero for the baseline and ten for the mutant. The injected Swift helper and production ScalarCodec bytes are unchanged. Fresh final-head CI, including the actual mutation, remains required after this correction.

Final engineering head `c843b44e5f004be97b17663010d0cc369026d704` passes all **16 hosted checks**: the [15-job contract matrix](https://github.com/raster-labs/SwiftJLS/actions/runs/41791870547) and [independent CharLS oracle](https://github.com/raster-labs/SwiftJLS/actions/runs/41791870548). The [final independent audit](results/ci-c843b44e-independent-audit.json) verifies both compiler preparation reports and the fresh ten-allocation mutation result against committed inputs. [Downloaded evidence](results/ci-c843b44e-evidence.zip) is retained as a lossless repack. This subsequent documentation-only closeout preserves all executable sources, tests and workflows from that head; any later hosted run remains separately identified.

A later 4 November [API verification](results/private-reporting-enabled.json) now confirms GitHub private vulnerability reporting is enabled. No setting was changed by this task and no test advisory was submitted. The prior disabled records remain historical. Physical-device qualification, maintainer acceptance of the proposed support policy, owner review/merge and a separately authorised stable publication remain outstanding. Milestone 5 preparation is implemented and tested; full milestone/release acceptance is not declared complete.

## Library-only completion follow-up

The owner subsequently left DICOMKit integration pending and requested completion
of all other library preparation tasks. [The checklist](Checklist.md) records
every original Milestone 5 item and distinguishes completed engineering work
from the still-open device and release acceptance decisions. Separate integration
and optimisation worktrees are preserved and excluded. All sixteen hosted checks
also passed on `53cea07be57fb030451a87bead9a3c3c0e863f04`;
[the retained snapshot](results/ci-53cea07b.json) identifies that revision and
its original Apple fallback coverage limitation.

The final audit fixes three direct-compiler workflows that omitted the eleven
qualified decoder files. They now select all 39 production sources and typecheck
an imported qualified decoder. [Local evidence](results/apple-sdk-source-coverage/README.md)
contains 14 commands: thirteen successful commands and the expected missing-API
negative-control failure, with complete visionOS/Watch SDK compile/link checks
at the 26.0 deployment floor. The lossless archive retains all inputs, logs and
outputs; this is compile evidence, not physical-device execution.

[SBOM qualification](SBOM/README.md) now covers library and CLI builds from clean
`53cea07b`: all four derived documents pass official schema validation, both
SPDX documents pass the official semantic model, and twenty negative/preservation
controls pass. An independent fresh replay reproduces the four derived documents
byte-for-byte and all twenty controls. Original SwiftPM producer defects and
previous Swift 6.4 records remain unchanged; only explicitly labelled derived
outputs are qualified. Their product inputs remain byte-identical in this
workflow/documentation follow-up.

The final hosted CI result for this follow-up is tracked in
[PR 18](https://github.com/raster-labs/SwiftJLS/pull/18/checks) at its exact head.
Physical-device admission, maintainer acceptance of the prepared support policy,
owner review/merge and separately authorised stable publication remain open.

Final library engineering head `16adfe068c3913f35b9cc72e3006be5a152d7665`
passes **all 21 hosted checks**: 15 contract/compiler/SDK/packaging checks,
CharLS, four Apple simulator runtime jobs and Watch architecture compilation.
[The final receipt](results/ci-16adfe06.json) records exact run and device-runtime
identities. Hosted simulators execute available OS 26.x runtimes, not the exact
26.0 minimum; Watch `arm64_32` IR confirms a four-byte `Int` and the qualified
public API typechecks. [Independent artifact review](results/ci-16adfe06-independent-audit.json)
verifies both 23-command preparation reports, nine committed inputs each, exact
locks, all CLI cases and the actual ten-allocation injected-copy trace.
[The lossless evidence archive](results/ci-16adfe06-evidence.zip) retains original
GitHub artifact ZIPs, full Apple job logs, API job identities and audit attempts.
The following documentation-only evidence commit preserves all workflows,
scripts, tests and product inputs from that passing engineering head; its own
required CI remains visible at the PR checks link above.
