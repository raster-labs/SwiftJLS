# Milestone 5 evidence — 4 November 2026

Milestone 5 release preparation is now assigned. [RELEASE.md](../../../RELEASE.md) defines its checks and open gates. Stable publication, physical-device qualification and application cutover remain uncompleted.

Baseline: SwiftJLS `a9bf9e95933fc8135bbcc3922d6ce831ddfe2057`, migrated from JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; qualified extension baseline `d17545284a23e93f3d884a18f1046c4e305daa35`. Suite policy 0.10.0 governs. The seven common documents, supplied compiler-upgrade documents and historical evidence remain unchanged. Codec source, package manifest and fixtures remain byte-identical to the committed baseline; unrelated uncommitted optimisation work is excluded in a separate worktree.

The reusable compiler runner now tests the actual native codec through the maintained independent consumer, with tools 6.2 and macOS 26.0 in its generated manifest. Its former Milestone 1 stub assertion and OS 27 floor could not validate the current library. An explicitly named dependency also permits differently named worktrees. Archived copies remain historical.

Initial host checks use Apple Swift 6.4.2 (`swiftlang-6.4.2.1.9`), Xcode 27.2 (`27B52`), arm64 macOS 27.0.1 (`26A434`). They are host results, not physical-device or minimum-OS execution:

| Command | Outcome |
| --- | --- |
| `python3 Scripts/validate-swift64.py --checks consumer --output /tmp/SwiftJLS-m5-consumer-validation` | Exit 0; native independent consumer checks all six padded 12-bit samples, destination identity and declared zero hand-off copies/pixel allocations. |
| `python3 Scripts/validate-swift64.py --checks debug,release --jobs 2 --output /tmp/SwiftJLS-m5-core-validation` | Exit 0; 17 commands exit 0; clean/incremental builds and 157 test declarations pass in each configuration, zero failures/skips. |

The preparation/provenance reports will bind their own exact committed candidates. No new sanitizer, hour-long mutation, independent oracle, controlled benchmark, allocator, minimum-OS or physical-device run is implied by the checks above. Those historical and open gates remain in [the qualification audit](../CodecMigration/Completion.md).

The live GitHub API returned private reporting `enabled: false` on 4 November. The owner selected that channel and will have an administrator enable it. The release-preparation support proposal is concrete but awaits maintainer acceptance in the release task. These are release blockers, not failed codec tests.
