# Storage evidence tools

These tools are development-only. No instrumentation or dependency enters the library target.

`python3 Scripts/StorageEvidence/mutate-layouts.py --output /tmp/layout-evidence -- [extra Swift flags]` copies package sources/tests into an isolated temporary directory. It first runs four ordinary-release expectations without mutations, then runs eight deliberately broken encode/decode stride/order variants. Each must execute tests and fail. Build errors, empty test runs and surviving mutations fail the script. The checkout is never modified. Final source hashes, commands, issue/expectation counts and summaries are retained alongside each log.

The focused run detected all eight variants: scalar encode/decode stride produced 2/1 failing expectations, scalar encode/decode order 1/1, component encode/decode stride 2/1 and component encode/decode order 1/1. An earlier focused test compared two outputs that were both wrong under a global byte-order mutation. It was strengthened with fixed-configuration codestream goldens already decoded exactly by CharLS; their hashes and provenance are in `Tests/SwiftJLSTests/Fixtures/storage-goldens.json`. The final report records ten aggregate failing expectations. This is mutation sensitivity evidence, not allocation/copy telemetry.

On Linux, `python3 Scripts/StorageEvidence/trace-files.py --binary PATH --output DIRECTORY` uses `strace` across all consumer threads. Markers emitted around the actual 12/16-bit in-process routes delimit the observation interval. Runtime/system reads remain in the report; any application file open or write/create/remove in the interval fails. Optional validation exports happen after each interval. The command, raw syscall traces, consumer stdout/stderr and classified events are retained. File observation does not measure pixel allocation/copy counts, and no sanitizer heap figures are used.

`trace-heap.py --binary PATH --output DIRECTORY` records the ordinary release consumer with Linux Heaptrack. CI rebuilds with debug symbols and no sanitizers, then retains allocation stacks, size histogram, whole-process totals, tool version, binary/profile hashes and exact commands. Missing injection data fails collection. The trace includes setup and runtime allocations; reviewing allocation purposes and measuring copied bytes remain separate work. Collection alone is not a zero-copy pass. Heaptrack is an isolated development tool ([upstream documentation](https://github.com/KDE/heaptrack)); it is not a package dependency.

`mutate-copy.py --baseline HEAP_DIRECTORY --output DIRECTORY` builds a temporary source clone with an intentionally hidden full-frame copy before scalar encoding. The ordinary integration consumer must still pass its sample/identity/report checks. The allocator must expose ten UInt8 sample-array allocations within the injected function, absent from baseline; a small closure/error allocation, build failure or consumer failure is not detection. Original and mutated source hashes, commands and both profiles are retained. This establishes sensitivity of the allocator observation, not complete production copy-byte accounting.

`Examples/CopyProbe` interposes Linux `memcpy`/`memmove` while a real encoder borrows its source. Ten normal scalar/near/component/HP/mapping cases must observe zero source-copy bytes, and ten deliberately copying adapters must observe at least their entire source capacity. A real-copy self-test must succeed first. Inlined copies are outside this measurement. The caller-decode checks also retain allocation identity; this probe is development-only and the interposer intentionally refuses qualification on unsupported hosts.

`trace-heap.py` accepts `--scope TEXT` and trailing `-- PROGRAM_ARGUMENTS`. The `CopyProbe Fixtures --heap-only` pass omits deliberate copies, uses caller-supplied decode storage throughout, and adds 98 legacy/extended/mapped/subsampled decodes. `classify-heap.py --heap DIRECTORY --output REPORT --revision SHA --scope TEXT` classifies demangled allocation stacks and fails for sample-owner arrays under scalar/component codec entry points. It retains unclassified byte counts explicitly; it does not infer measured per-operation peak workspace. Owned decode intentionally allocates its output and must not be mislabeled as an extra caller-storage allocation. The first broad collection caught exactly that harness mistake (five initial owned outputs); the corrected probe preallocates those five destinations before entering the codec.

`measure-peaks.py --profile PROFILE.gz --output REPORT.json --revision SHA` replays interpreted Heaptrack 1.5.0 allocation/free events to measure peak simultaneously live requested heap bytes. `--self-test` checks overlapping lifetimes, group peaks, allocation counts and invalid-free rejection. The parser follows the documented implementation of [Heaptrack format 3](https://github.com/KDE/heaptrack/blob/v1.5.0/src/analyze/accumulatedtracedata.cpp); it does not import Heaptrack code. The overall peak and allocation count must agree with the accompanying Heaptrack analysis. Group peaks occur at different times and must not be added. Pixel attribution recognises `OwnedImageStorage` array initialisers; arbitrary sample arrays outside those stacks remain in other groups and still require source/stack review. Pixel array headers/capacity are included. Nonpixel codec heap includes compressed buffers and metadata; runtime/unattributed heap and stack storage are not silently relabelled as algorithm workspace. This improves the earlier stack-count-only evidence, but it does not populate unknown per-operation workspace reports.

[ResourceStress](../../Examples/ResourceStress/README.md) supplies an ordinary-release concurrent workload: four bounded workers and 32 512×512 scalar/colour lossless/near-lossless frame transactions. CI retains both its checked sample/identity/report results and its independent heap profile. The worker bound belongs to the harness; per-operation limits do not become a process-wide scheduler.

`Examples/WorkspaceProbe` marks one public encode, owned decode, supplied decode
or inspect operation after setup. Results stay live through the end marker and
sample verification follows it. `measure-operation.py` replays Heaptrack events
between those markers, retaining baseline live bytes, per-category peaks, phase
allocation calls and every allocation stack. It rejects missing/repeated markers
and invalid frees. Run its `--self-test` before collecting evidence.

The `Per-operation workspace evidence` workflow uses `run-workspace-profiles.py`
to record 89 separate processes: the original 32 combinations of 17²/512²,
scalar/RGB, NEAR 0/3 and four operations; 48 additional line, planar, 16-bit,
maximum-threshold preset, restart and HP1/2/3 operations; and nine fixture
operations covering subsampling, mapping and extended dimensions. Builds use
Swift 6.4 ordinary release with debug symbols. These are measured requested heap
bytes on the hosted Linux runner. Allocation stacks and requested-size histograms
distinguish pixel, compressed, algorithm-state, metadata/descriptor and runtime
paths. Unknown codec stacks remain explicit and prevent
`codec_heap_attribution_complete` from being true. Size-bounded recognisers retain
negative controls so unrelated or larger allocations cannot inherit a category.
Peaks from different categories must not be added.

[WorkspaceAccounting.md](../../Documentation/Engineering/CodecMigration/WorkspaceAccounting.md)
links the full source inventory, per-path bounds and measured allocation evidence.
Complete attribution of observed codec heap does not establish an exact combined
heap/stack/allocator counter. Stack high-water bytes and allocator overhead remain
unknown, `pure_algorithm_workspace_complete` remains false for this measurement,
and production `peakWorkspaceBytes` remains unknown. Keep profile hashes and
source revisions with every reported result.

The separate `Marked workspace stack observation` workflow uses pinned Valgrind
3.27.1 (`b50f9a09ca65cc983c934bd0f50059304f3e939f`) with Massif stack tracking.
Conditional client requests in the development consumer write beginning/end
snapshots. `measure-massif.py` rejects missing or unordered boundaries and zero stack
observations. Short operations without interior snapshots are explicitly marked
as boundary-only observations with unknown transient interior peaks. It reports snapshot maxima for the
marked interval, including the whole runtime's stacks. These are observed peaks,
not exhaustive codec stack high-water guarantees; Massif's extra heap is an
allocator model. Keep this instrumented experiment distinct from ordinary-release
Heaptrack counts and performance timings. A profiler crash is an unsuccessful
measurement, not a zero or a codec pass.

The operation ledger also retains category bytes at the **same instant** as the total requested-heap peak. Those simultaneous values reconcile to the total; independent category maxima do not. The total increase over the live setup baseline is reported separately. Swift generic metadata caches are runtime storage even when a codec call caused their first use. Remaining unattributed allocations retain their stacks and bytes.
