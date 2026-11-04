# Release preparation

The library preparation work for Milestone 5, assigned on 4 November 2026, is implemented; see the [item-by-item checklist](Documentation/Engineering/ReleasePreparation/Checklist.md). DICOMKit integration remains pending by owner direction. The library scope covers clean versioned consumption, documentation/examples, migration guidance, provenance and review of release gates. **Stable release readiness remains blocked.** Completing preparation does not waive the physical-device and release gates below, publish a tag, authorise consumer cutover or archive JLSwift.

The candidate is based on SwiftJLS `a9bf9e95933fc8135bbcc3922d6ce831ddfe2057` (merged PR 17), version `1.1.0-dev.2`. The migration predecessor is JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; the qualified caller-workspace extension additionally records `d17545284a23e93f3d884a18f1046c4e305daa35`. Suite policy **0.10.0**, tools **6.2** minimum, Swift **6.4** primary and Apple OS **26.0** floors remain unchanged. Shared contracts retain their individual recorded revisions.

## Repeatable preparation

Commit a clean candidate before running these commands. Use a fresh output directory for each invocation. These commands neither push nor publish:

```sh
python3 -m unittest discover -s Scripts/ReleasePreparation -p 'test_*.py' -v
python3 Scripts/ReleasePreparation/provenance.py --predecessor /path/to/JLSwift --output /tmp/swiftjls-provenance.json
python3 Scripts/ReleasePreparation/provenance-controls.py --predecessor /path/to/JLSwift --output /tmp/swiftjls-provenance-controls.json
python3 Scripts/ReleasePreparation/prepare.py --output /tmp/swiftjls-release-preparation
```

The preparation runner records the candidate commit/tree, input hashes, compiler, command arguments, exits and logs. It builds and runs the maintained independent consumer and the exact Swift blocks in README.md and MIGRATION.md twice: from a disposable bare repository with an exact `1.1.0-dev.2` version requirement, and from the public GitHub URL at the full candidate revision. It checks each lockfile's URL, version, revision and sole dependency. Only the disposable repository receives a temporary tag; the source repository's tags must remain unchanged. The local tag is packaging evidence, **not a published prerelease**. The hosted commit must already be pushed for that portion to pass. `--local-only` explicitly omits hosted consumption and records the omission.

The runner also builds the CLI and runs the existing payload, help, version, diagnostics, pipe, staged installation/update and manual checks. It needs Python 3, Git, Swift, `man` and `mandoc`. Missing prerequisites and failed commands fail the check; logs survive. CI runs this on the exact PR head, including both supported Swift compiler lines. Swift Build is the default and the primary Swift 6.4 engine. The Swift 6.2 Linux compatibility job explicitly selects `--build-system native`: its recorded Swift Build attempts compile the test target but fail test launching, and fail linking the independent consumer. There is no automatic fallback or claim that those engine checks passed; see [the retained failures](Documentation/Engineering/ReleasePreparation/README.md). The provenance audit checks contract/fixture hashes and inventories recorded licences; optional pinned predecessor verification is documented in [the provenance index](Documentation/Engineering/ReleasePreparation/Provenance.md).

The independent consumer checks every padded 12-bit sample, destination identity and declared operation copy/allocation reports. These are regression checks of the owning API, not new allocator measurements. Existing independent [copy/workspace evidence](Documentation/Engineering/CodecMigration/WorkspaceAccounting.md) remains scoped to its original source. No codec, public API, memory lifecycle, fixture or hot path changes are part of Milestone 5; no new performance improvement or memory reduction is claimed.

## Gates before stable publication

| Gate | Disposition and required evidence |
| --- | --- |
| Clean consumption, examples and CLI packaging | Reproducible preparation runner and retained command/lockfile evidence; re-run against the selected release candidate. See [Milestone 5 evidence](Documentation/Engineering/ReleasePreparation/README.md). |
| Public API and migration guidance | [MIGRATION.md](MIGRATION.md), [profile matrix](Documentation/Engineering/CodecMigration/Parity.md), [CLI.md](CLI.md), qualified caller-workspace guide and explicit unsupported profiles remain the acceptance boundary. No `from: "1.1.0"` recommendation before publication. |
| Licence, notices and fixtures | Apache-2.0 in-house implementation; third-party oracle/reference terms remain separate. [Provenance index](Documentation/Engineering/ReleasePreparation/Provenance.md) maps manifests and checks; preserve LICENSE/NOTICE and each fixture's own terms. |
| Library and CLI SBOMs | [Build-associated qualification](Documentation/Engineering/ReleasePreparation/SBOM/README.md) preserves raw producer defects and supplies four explicitly labelled derived documents validated against official schemas, SPDX semantic checks and twenty negative controls. Re-generate for the selected release candidate. |
| Correctness, independent oracles, sanitizers and mutation | Review source-scoped [validation](Documentation/Engineering/CodecMigration/Validation.md). Historical results are not relabelled as new runs. Refresh affected gates whenever runtime source or qualification conditions change. |
| Controlled performance and memory | Candidate005 evidence retains its measured scope and unknown totals. Uncommitted optimisation work in another worktree is excluded and requires its own qualification before inclusion. |
| Platform and physical-device qualification | **Open.** Representative iPhone/iPad, Watch and other required device admission remains unexecuted. Confirm the full native Intel/Linux/Apple matrix at the selected candidate. SDK builds, simulators and virtualised macOS do not replace physical devices. |
| Private security reporting | **Configured.** The later 4 November [read-only API verification](Documentation/Engineering/ReleasePreparation/results/private-reporting-enabled.json) returns `enabled: true` for the owner-selected GitHub channel. No setting was changed or test advisory sent by this task. Recheck channel availability in the actual release review. |
| Supported-version policy | Current unreleased policy is in [SECURITY.md](SECURITY.md). The proposed first-stable policy below requires maintainer acceptance in the explicit release task. |
| Final-head CI and review | All required checks must pass on the final reviewed head. Preparation success alone is insufficient. Owner reviews and merges the PR. |
| Explicit stable release task | **Not assigned.** After all gates close, the owner selects the release commit and authorises publication. No stable tag or GitHub release is created by this milestone. |
| Application rollout/predecessor lifecycle | Separate assignments: application acceptance, dependency cutover, maintenance window and eventual archival. |

## Prepared first-stable support policy

Proposed for maintainer acceptance when `1.1.0` is released: maintain the latest patch of the `1.1.x` line for security fixes; reporters on earlier `1.1.x` patches should reproduce against the latest patch when safe. Development snapshots receive case-by-case investigation without a supported-release guarantee. Publish any future line transition and end of support before withdrawing support. No fixed response or resolution deadline is promised. This proposal creates no support window for an unpublished version.

## Publication handover

In the separately authorised release task, select a clean immutable commit, recheck the gates above and archive its reports. Update VERSION, CLI version, help, manual and release notes together, validate the stable candidate's versioned package consumption, and publish only the approved tag/assets. Any binary distribution includes the matching manual and required notices. Attach the capability/limitation matrix and actionable security/support policy. Verify public version resolution after publication before recommending application adoption. Never retarget a published tag or substitute a local rehearsal for that verification.
