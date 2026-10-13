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

The local host is Apple Silicon Mac16,5 with 64 GiB memory, Apple Swift 6.4 (`swiftlang-6.4.0.34.1`) and macOS 27.0.1. The initial test runs used Command Line Tools. The user installed Xcode 27.0 (27A266a) during this task; subsequent Apple builds use its SDK 27.0 and deployment targets 26.0. The subsequent consumer runs below execute on exact OS 26.0 simulators. They do not establish physical-device qualification or exact native macOS 26.0 execution.

| Check | Result |
| --- | --- |
| Debug, release, AddressSanitizer and ThreadSanitizer | 80 declarations in each run, zero failures and zero skips; each command exits 0 |
| Payload CLI | 73 checks pass |
| Process/help/manual/staged-install CLI | 103 checks pass |
| Standalone public API consumer | Passes |
| Concurrent resource consumer | 32 scalar/RGB NEAR 0/3 transactions pass, with sample and caller-allocation checks |
| Benchmark measurement smoke | Six scalar and 36 colour profiles pass for both libraries, four alternating blocks each; separate and combined timing arrays are present |
| Runner controls | 11 positive/negative controls pass |
| Xcode 27 Apple builds | Four signed simulator consumers and the arm64_32 Watch module compile for deployment target 26.0 |
| Exact OS 26.0 runtimes | iPhone 17 Pro, iPad Pro 13-inch (M5), Apple TV 4K (3rd generation), Apple Vision Pro and Apple Watch Series 11 (46mm) simulator consumers all pass |
| Exact OS 26.0 concurrent resources | Four non-Watch simulator profiles each pass 32 scalar/RGB NEAR 0/3 frame transactions; caller destination identity is preserved, with zero reported caller-decode pixel allocations or copy bytes |
| Local iOS 27.0 runtime | iPhone 18 Pro and iPad Pro 13-inch (M5) simulator consumers pass sample, direct-storage, RGB/HP, mapping/metadata, bounded-limit, cancellation and combined legacy checks |
| Hosted PR checks | All 16 pass at both `b44fe03` and `608193a`; exact links are in the supplemental evidence |
| Instruments collection | A debug-signed copy of the ordinary release benchmark successfully records allocations and exits 0; complete workspace accounting remains open |

Exact commands, source hashes, logs, xUnit results and smoke artifacts are recorded in [the evidence manifest](results/milestone4-2026-10-13.json). Initial default-engine discovery failed because the bundled Testing macro plugin was not loaded. An explicit native-backend diagnostic also failed because it could not locate Testing. Both failures are retained. All four successful test runs use the default Swift Build engine and explicitly load `/Library/Developer/CommandLineTools/usr/lib/swift/host/plugins/testing/libTestingMacros.dylib`; language/concurrency checking remains enabled. The release benchmark consumer builds used the native backend, recorded separately from the successful default-engine library tests.

Smoke runs overlapped software validation on a battery-powered developer machine. They qualify harness correctness only; their timing ratios must not be used to resolve the existing performance regressions. The existing three one-hour mutation campaigns and independent interoperability evidence remain scoped to unchanged production sources; no redundant long campaign was run for benchmark/documentation changes.

## Gates still open

| Gate | Required completion evidence |
| --- | --- |
| Controlled performance, PERF-01..03 | Powered, idle hardware with recorded thermal/load conditions; full representative scalar and colour runs, including source preparation; investigate confirmed regressions above the contract threshold and record any explicitly accepted safety/correctness cost |
| Per-operation workspace | Complete accounting separating algorithm workspace, compressed buffers, metadata, runtime and stack storage. Existing Heaptrack group peaks do not close this gate; `peakWorkspaceBytes` remains unknown |
| Native macOS minimum | Exact 26.0 simulator consumer coverage is now complete for iOS/iPadOS, tvOS, visionOS and watchOS. This host remains macOS 27.0.1; the local runs do not establish exact native macOS 26.0 execution |
| Physical-device admission | Representative required non-Watch devices and provisioning. Xcode is now available, but `devicectl` reports no physical devices. Physical Watch testing retains its earlier task exclusion and is unexecuted |

The Xcode download window initially contained OS 27.0 simulators only. Exact iOS 26.0 (23A343), tvOS 26.0 (23J352), watchOS 26.0 (23R353) and visionOS 26.0 (23M336) downloads have completed with exit 0. All five independent runtime consumers pass, including separate iPhone/iPad devices. The non-Watch concurrent resource runs also pass. [The exact-26.0 evidence](results/milestone4-os26-2026-10-13.json) records commands, outputs, compiler/build identity and source/binary/artifact hashes. Watch uses its bounded resource consumer, including resource rejection and cancellation; the four-worker resource workload was not used as a physical Watch memory claim. Earlier iOS 27.0 evidence retains its original scope. No powered, idle benchmark window has been established; the latest power check still reports battery use.

After the user enabled development-tool authorisation, Instruments still could not attach to the ordinary executable. A local copy signed with `com.apple.security.get-task-allow` then produced a successful Allocations trace and target exit 0. Instruments displays allocation statistics and call trees; some symbols remain unresolved. This single scalar 512×512, 12-bit seeded-noise process includes setup and multiple encode/decode boundaries, so it does not provide complete per-operation workspace accounting. The failed attempt is retained alongside the successful recording log, redacted trace contents index and local raw-trace file hashes. See [the Xcode follow-up evidence](results/milestone4-xcode-2026-10-13.json). The raw trace remains local because it contains machine-specific data.

These are uncompleted gates, not approved waivers. Milestone 5, vulnerability-reporting/support-policy setup, stable publication and programme rollout remain for the later release task. The current work does not mark either milestone complete.
