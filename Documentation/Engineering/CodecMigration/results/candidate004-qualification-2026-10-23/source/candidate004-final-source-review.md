# Candidate004 source acceptance

No actionable correctness findings in the frozen wrapping-shift candidate. This accepts source and tests; it does not infer a measured performance improvement.

All 38 production Swift files match the live repo, frozen package and linked benchmark arm. All 31 test Swift files match live/frozen copies, and Package.swift/VERSION match candidate003. Only JPEGLSBitstreamReader.swift and BitstreamWriterTests.swift differ from candidate003. These inventories were stable at the review start and end; exact maps are in candidate004-final-source-start.json and candidate004-final-source-review.json.

The new expression `bitBuffer &<< (64 &- bitsInBuffer)` is equivalent for every reachable helper call. Refill adds at most15 while count≤48; reads only reduce after checking availability; unary refill is guarded positive. Thus count and shift are both1…63. Wrapping operators cannot alter those results. No input admission, entropy bound, pointer, ownership, cancellation, error or padding validation code changed. Padding still masks low remaining bits.

The test now compares each bulk read with both the width-masked input and independently constructed source bits. It deliberately retains the out-of-range 31-bit literal to verify writer masking. FF7F and FF00 occurrence assertions support the comments. Direct FF/FE one-byte vectors exercise exactly one remaining valid bit after consuming seven high ones: terminating1 succeeds and validates the end; zero reaches end-of-stream rather than stale high-bit termination. The error assertions check the error type rather than enum equality; source inspection confirms that valid maximum and exhausted-buffer path has only prematureEndOfStream as its JPEGLSError. Existing broad end padding/prefix limit behaviour is retained. No blocking coverage gap remains.

The Benchmark binary SHA begins1db8b6a3fd92 and matches the assembly receipt. Independent llvm-objdump output exactly reproduces all117 recorded instructions. The ordinary buffered-window-to-bounded-zero sequence is six instructions (`ldr/neg/lsl/clz/cmp/csel`), versus13 in candidate003 (12 when refill already proved nonnegative). Removed mask/shift guards do not reappear in this sequence. Function size alone is not the performance conclusion; controlled measurements remain separate.

Observed focused XML results are97 release,45 ASan and37 TSan cases, each with zero failures/errors. Recorded commands exited0. These are AG execution receipts; this reviewer ran no builds or tests. Original failed candidate004 remains separately archived as candidate_004_archived_20261023T104028Z, including its unmasked-expectation error.

Reviewed source hashes: reader5f71d419cb389235dbc756d3a1c0df6f888c860427f40f867250b9f031202485; tests a6b13c6d22bc7a13453f8d2bf86e0685a7902b92828d841f882d3c1c8502bc79. The adjacent JSON contains full binary and receipt identities and the independently reproduced disassembly paths.
