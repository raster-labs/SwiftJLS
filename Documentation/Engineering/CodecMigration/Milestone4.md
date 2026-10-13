# Milestone 4 qualification follow-up — 13 October 2026

**Milestone 4 remains incomplete.** The owner assigned Milestone 4 and requested documentation updates, leaving Milestone 5 for a later task. This follow-up closes a benchmark measurement-boundary gap and repeats available software checks; it does not substitute passing tests for the outstanding performance, workspace or platform gates.

## Baseline and implemented work

- Starting main: `571fd7c905f7ef70b4f494513ecf979d620bebd5`, merged PR 15. Both the DICOM-padding and inactive-interleaved-DRI fixes are present. Active documents now reflect the merge.
- Predecessor comparison: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`.
- Suite policy 0.10.0, tools 6.2 minimum, primary Swift 6.4, Swift 6 language mode, Apple OS 26.0 deployment floors. The seven common documents and their hash manifest are unchanged.
- No production codec, public API, manifest, fixture or unit-test change. `VERSION` remains `1.1.0-dev.2`; no release, tag or consumer cutover is performed.
- The benchmark now measures input preparation and preparation plus encode from identical canonical UInt16 samples, alongside the existing encode/decode timings. This includes the predecessor validation previously outside encode timing. Generation and sample verification remain outside timing. Raw observations, medians, p95 and paired ratios are retained; no latency threshold or safety check changes.
- Runner controls reject incomplete, invalid or stale observations and accidental evidence overwrite. The new CI smoke workflow builds both independent consumers against the pinned predecessor and current successor. See [benchmark instructions](../../../Scripts/Benchmark/README.md).

## Executed software checks

The local host is Apple Silicon Mac16,5 with 64 GiB memory, Apple Swift 6.4 (`swiftlang-6.4.0.34.1`) and macOS 27.0.1. The initial test runs used Command Line Tools. The user installed Xcode 27.0 (27A266a) during this task; subsequent Apple builds use its SDK 27.0 and deployment targets 26.0. These results are not exact OS 26.0 or physical iOS-family device qualification.

| Check | Result |
| --- | --- |
| Debug, release, AddressSanitizer and ThreadSanitizer | 80 declarations in each run, zero failures and zero skips; each command exits 0 |
| Payload CLI | 73 checks pass |
| Process/help/manual/staged-install CLI | 103 checks pass |
| Standalone public API consumer | Passes |
| Concurrent resource consumer | 32 scalar/RGB NEAR 0/3 transactions pass, with sample and caller-allocation checks |
| Benchmark measurement smoke | Six scalar and 36 colour profiles pass for both libraries, four alternating blocks each; separate and combined timing arrays are present |
| Runner controls | 11 positive/negative controls pass |
| Xcode 27 Apple builds | Four signed simulator consumers and the arm64_32 Watch module compile for deployment target 26.0; runtime execution remains pending installation |

Exact commands, source hashes, logs, xUnit results and smoke artifacts are recorded in [the evidence manifest](results/milestone4-2026-10-13.json). Initial default-engine discovery failed because the bundled Testing macro plugin was not loaded. An explicit native-backend diagnostic also failed because it could not locate Testing. Both failures are retained. All four successful test runs use the default Swift Build engine and explicitly load `/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib`; language/concurrency checking remains enabled. The release benchmark consumer builds used the native backend, recorded separately from the successful default-engine library tests.

Smoke runs overlapped software validation on a battery-powered developer machine. They qualify harness correctness only; their timing ratios must not be used to resolve the existing performance regressions. The existing three one-hour mutation campaigns and independent interoperability evidence remain scoped to unchanged production sources; no redundant long campaign was run for benchmark/documentation changes.

## Gates still open

| Gate | Required completion evidence |
| --- | --- |
| Controlled performance, PERF-01..03 | Powered, idle hardware with recorded thermal/load conditions; full representative scalar and colour runs, including source preparation; investigate confirmed regressions above the contract threshold and record any explicitly accepted safety/correctness cost |
| Per-operation workspace | Complete accounting separating algorithm workspace, compressed buffers, metadata, runtime and stack storage. Existing Heaptrack group peaks do not close this gate; `peakWorkspaceBytes` remains unknown |
| Exact minimum runtimes | Execute required OS 26.0 runtime checks. Passing newer-minor simulators or building for deployment target 26.0 is not an exact-minimum runtime pass |
| Physical-device admission | Representative required non-Watch devices and provisioning. Xcode is now available, but `devicectl` reports no physical devices. Physical Watch testing retains its earlier task exclusion and is unexecuted |

The Xcode download window initially contained OS 27.0 simulators only. An explicit iOS 26.0 (23A343) download was started to obtain the exact minimum; a download is not a runtime pass. Instruments failed to attach to its allocation test process, and development-tool authorisation is currently disabled. This failed collection supplies no allocation measurements.

These are uncompleted gates, not approved waivers. Milestone 5, vulnerability-reporting/support-policy setup, stable publication and programme rollout remain for the later release task. The current work does not mark either milestone complete.
