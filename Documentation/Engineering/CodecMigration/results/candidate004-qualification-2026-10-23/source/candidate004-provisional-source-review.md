# Candidate004 provisional source review

The one-expression reader change is correct under the existing private buffered-bit invariant. The initial focused failure is a test oracle error, not evidence of a production mismatch. This is provisional: live source/tests changed during inspection and differ from the retained first candidate004 snapshot. No Swift builds, tests or timing were run by this reviewer.

## Correctness proof

`refill()` adds8 or15 only while the count is at most48, so the buffer count cannot exceed63. `readBits` consumes only after its availability guard. Unary consumption removes no more than the current count; an exhausted window is refilled and guarded positive before the sole `alignedWindow` call. Thus that helper sees1…63. For such b, `(x & ((1<<b)-1)) << (64-b)` equals `x << (64-b)`: every discarded high bit shifts beyond bit63. The same proof permits `x &<< (64 &- b)` with no changed reachable result. That form should be checked in actual compiled code; no speedup is inferred. End-of-scan padding masking, prefix limits, refill semantics and all cancellation checks remain unchanged.

## Retained failed test

The initial snapshot wrote `0xDEAD_BEEF` with count31, then compared the decoded value directly with the unmasked input. `writeBits` explicitly masks to the requested width, and the independent raw-bit construction likewise emits only bits30…0. Correct decoded value is `0x5EAD_BEEF`. The97-test/16-suite XML/log report exactly one issue at the direct expected-value assertion; neither raw-bit assertions nor `actual == bitRef` reported a mismatch. Live test already uses the correct31-bit value. Preserve the failed log/XML and initial source identity.

## Boundary test gap

The mixed-stream comments do not reflect its actual eager-refill state. Independent bit packing gives403 bytes with FF7F pairs at offsets0,2,4,23 but no FF00 pair; the unary window-size model reaches63 but never1. FF00 is independently covered by the separate limit vectors, so there is no general stuffing gap. Add or verify a direct one-valid-bit reader case: `[FF]`, consume7 bits, then unary maximum0 returns0 and padding validates; complementary `[FE]`, consume7 bits, then unary maximum1 reaches premature end rather than treating consumed high ones as a terminator. Algebraic b=1 coverage already exists but does not invoke the actual reader boundary.

## Machine-code evidence

The retained first004 Benchmark SHA is `a4e5b2f0a038f661e5c4d3191fd28069b6ade1b49e9300fe293d1fa1e44a8c9e`, independently rehashed. Its receipt removes the old mask-building/use `lsl/cmp/csinv/and`. On the ordinary non-refill path through bounded-zero selection, old code has13 instructions and initial004 has14; entering the old path after refill skips its negative-count check (12). New signed subtraction/conversion/oversized-shift handling offsets the removed mask work. Whole-function125→131 instruction counts are not a hot-path performance claim. Live source subsequently changed the shift expression, so this receipt must not be attributed to that newer source.

The snapshot003→first004 Swift source/test inventories differ only in `JPEGLSBitstreamReader.swift` and `BitstreamWriterTests.swift`. Exact reviewed hashes and evidence links are in the adjacent JSON. Final source freeze, assembly provenance and successful corrected validations remain required before acceptance; no measured performance conclusion is made.
