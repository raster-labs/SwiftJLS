# Qualified raw-call allocation probe

This development-only executable observes allocator calls during the synchronous
`QualifiedMonochromeDecoder` public operations. It is not a production dependency,
an allocation guarantee for the common owning API, or a general memory profiler.

Build and run an ordinary release executable on **Linux with glibc**:

```sh
swift build -c release --package-path Examples/QualifiedAllocationProbe --scratch-path /scratch/qualified-probe-build
python3 Examples/QualifiedAllocationProbe/run.py --binary /scratch/qualified-probe-build/release/QualifiedAllocationProbe --fixtures Tests/SwiftJLSTests/Fixtures --output /scratch/qualified-probe-results --explicit-standard-defaults
```

`run.py` runs cold inspection and cold decode in separate fresh processes, then
the complete selected matrix in a third process. Every process must first pass
nine C allocation-entry positive controls and a Swift raw-allocation control.
The first qualified API call is explicitly labelled. Process/runtime startup,
fixture reading, decoder construction and caller-buffer preparation happen
before that call; “cold” does not mean a new operating-system page cache.
All process outputs are retained, including failures, without automatic retries.
Each process has a 120-second timeout (overridable with `--timeout-seconds`);
timeouts preserve partial output, fail qualification and do not suppress the
other scheduled processes. The runner independently reconciles counter totals,
positive controls, operation pairs and summaries before reporting a pass.
macOS and non-glibc hosts emit an unsupported record and exit nonzero.

Counters are thread-local and cover `malloc`, `calloc`, `realloc`, `memalign`,
`posix_memalign`, `aligned_alloc`, `valloc`, `pvalloc` and `reallocarray` exported
by the executable. Direct glibc forwarders avoid allocation while resolving
symbols. Positive controls use volatile function pointers and observable writes,
so ordinary optimisation cannot remove them. The Swift control checks that a
runtime allocation crosses the executable interposer as well. Any observed
allocation, counter overflow, incorrect outcome/sample or damaged canary fails
the corresponding operation. All cases are still reported before the final exit.

Only the public call and immediate value return are inside each begin/end scope.
Input, output, scratch and cancellation context are prepared beforehand. Outcome
inspection, exact sample comparisons, guards, input-integrity checks, JSON and
owner destruction follow the scope. Input, scratch and output each have guards.
Late cancellation uses a threshold derived from a separately measured successful
count-only callback baseline. The callback touches only its independent scalar
context; it never reads the borrowed input/output/workspace. Partial output is
verified after the cancelled call returns. Any callback/runtime
allocation on the measured thread would count; none is silently subtracted.

The matrix covers standard-oracle scalar fixtures for 8–16-bit precision,
2–7-bit zero/one-pixel cases, explicit presets, NEAR and row restarts; bounded
RESET values unsupported by the legacy profile are asserted as rejections.
Other low-MAXVAL default cases are listed explicitly as excluded because the
selected `jlswift0101` thresholds differ from the standard oracle. Separate
qualified-API tests cover those legacy semantics. Four additional 17×13 fixtures
have an exact `d175452` predecessor oracle for 2/7-bit noisy inputs and final-preset
selection, plus 8-bit NEAR=127; their provenance is distinct from independent
standard conformance.

`--explicit-standard-defaults` inserts an explicit standard LSE preset into all
28 high-NEAR fixtures whose implicit standard thresholds differ from this legacy
profile. Selection uses the threshold formulas, never previous test outcomes.
Only the 15-byte LSE segment before SOS changes; entropy, restart bytes and
independent expected samples remain unchanged. The output retains original and
adapted streams, expected samples, hashes, thresholds and reason in
`adapted-inputs/adaptations.json`. Operation labels and records identify the
adapter, and the runner verifies all adapted operation pairs and provenance.
This measures explicitly signalled standard presets, not compatibility with the
original implicit-default streams. Omitting the flag retains the raw matrix,
including its known profile disagreements. Keep each run in a fresh directory;
the initial raw 858-operation campaign with ten decode failures is historical
evidence, not replaced by an adapted pass. The current matrix includes the fourth
legacy oracle and therefore contains 430 cases / 860 operations.

The probe also checks
monochrome palettes (including width-three rejection and mapped-precision
failure), strict missing/short selected-table failures, legacy continuation/extended-dimension fixtures, opaque APP/COM,
leading fill and DICOM padding, every prefix truncation of a small fixture,
late entropy failure, compressed/decoded/workspace/output denial, and immediate
and post-write cancellation. Fixture manifests and expected samples are read
from the repository; standard continuation headers are explicitly converted to
the chosen predecessor syntax outside observation.

This evidence cannot see allocations on other threads, hidden/internal glibc
allocation paths, direct memory mappings or stack storage. Counts are allocation
attempts and requested bytes, not peak live memory. The probe does not establish
an arbitrary caller callback as allocation-free. Run ASan separately for memory
safety; sanitizer-interposed allocation results are not qualification evidence.
