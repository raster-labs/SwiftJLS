# Isolated singleton mapping candidate

Base source: `bee49a2ad47eae4ea149bdced2043b7a45df3dae`. Production sources are
unchanged. Only `ImageDescriptor.swift` and two focused tests in
`DescriptorTests.swift` differ in the snapshot. `candidate.patch` and
`source-identity.json` record the exact change and all source/test hashes.

The candidate skips Set insertion only when image components, planes and the
sole plane's components each have exactly one element. The existing component
range check remains first. PlaneDescriptor has already rejected negative
indices, so a successful singleton range check proves the sole mapping is zero:
uniqueness and full coverage follow. All other shapes retain the original Set
insertion and final cardinality guard. The image's nonempty-planes guard still
precedes the singleton predicate; short-circuit evaluation also protects its
indexing. All geometry, precision, semantic, arithmetic, alignment, overlap and
resource checks remain in their original order.

Tests preserve exact errors, including an invalid singleton component `[1]`
combined separately with four alignment failures, and a geometry failure that
must precede mapping. A valid/invalid matrix exercises 8/16/32-bit layouts,
padding, offsets, packed/multiple planes, duplicate and missing mappings,
overlap, alignment and the decoded-byte limit. Existing descriptor tests also
run. No storage lifetime, public API, cancellation or deadline checks change.

`build.py` builds the unchanged original Benchmark consumer with explicit
Command Line Tools, release configuration and four jobs; it then runs the
focused release DescriptorTests using the established Swift Build/TestingMacros
configuration. `build-results.json` retains commands, exits, counts and logs;
`build-identity.json` is written only after both stages succeed and records the
fresh benchmark binary, toolchain and source/consumer hashes.

`allocation-target.json` preserves the existing Linux x86_64 Swift 6.4
measurement: owned 17×17 scalar decode at the base revision requested one
80-byte metadata/descriptor Set allocation at ImageDescriptor's insert. The
candidate makes this singleton insertion unreachable. Candidate heap reduction
has not been measured; 80 bytes is not claimed as a macOS allocator result.
There is no algorithm-state or pixel-buffer change.

No timing is authorised by the build script. Benefit remains unknown; this is
an unpromoted experiment, not performance qualification or a gate waiver.

The build and focused release tests completed: 11 DescriptorTests plus the
substring filter's one HeaderDescriptorTests declaration, all passing. The
original evidence driver expected only 11 total; its postcheck was corrected
to verify the exact 11+1 suite counts using retained XML. Both actual build/test
commands exited zero. The original driver and correction note are retained in
`attempt-history`; no test rerun was needed.

## Prepared timing protocol

`run-comparisons.py` and four immutable schedules were prepared before timing and subsequently completed once. See `conclusions.md`, `combined-summary.json` and the four completion records; the initial readiness record is preserved as preparation history.
The fixed comparison order is short/bee, short/pinned, long/bee, long/pinned.
Each comparison has six scalar 37×23 cases, 16 paired process blocks per case,
balanced first-producer order and rotating/reversed case order: 192 processes
per comparison, 768 total. Short uses 5 warmups/5 observations; long uses
20,000/1,000. All four original operations are retained. No outcome-based
repeat, drop, stopping rule or automatic waiver is allowed.

After the coordinator releases the timing window, use for each fixed pair:

```sh
python3 run-comparisons.py --mode short --reference bee --check-only
python3 run-comparisons.py --mode short --reference bee --output timings/short-bee
python3 run-comparisons.py --mode short --reference pinned --output timings/short-pinned
python3 run-comparisons.py --mode long --reference bee --output timings/long-bee
python3 run-comparisons.py --mode long --reference pinned --output timings/long-pinned
```

The runner verifies exact source, patch, original consumer and all three binary
identities before and after every comparison. It retains partial results on
errors or lost AC power. Analysis includes all paired ratios/deltas, block
spread, producer-order groups and intervals treating the process pair as the
unit; serial observations are never treated as independent replicates. Interval
assumptions and shared-host temporal-correlation limits are explicit.
