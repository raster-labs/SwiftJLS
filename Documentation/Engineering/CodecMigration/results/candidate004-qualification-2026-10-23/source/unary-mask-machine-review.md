# Frozen candidate003 unary-mask machine review

**The mask is retained in the real frozen release binary.** [Machine receipt](unary-mask-machine-review.json) binds binary `bd171975e50f6b3557df7b5fda39ce431f8b4098ee163f40b2db1ca65fa142ad`, the corresponding snapshot/linked reader source, exact command and unchanged before/after binary hashes. [Focused disassembly](unary-mask-candidate003-disassembly.txt) is retained; command exits0 with empty stderr. No build, benchmark, profiling or repository edit was performed.

`readUnaryCount` starts at0x10002cb54. After loading bitBuffer, the valid-window path executes:

```
10002cb8c  lsl   x15,x11,x13       // x11=-1, x13=bitsInBuffer
10002cb90  cmp   x12,x13           // x12=64
10002cb94  csinv x15,x11,x15,eq   // low-bit mask, including shift-width handling
10002cb98  and   x14,x14,x15       // mask buffered bits
10002cb9c  neg   x15,x13
10002cba0  lsl   x14,x14,x15       // left align; register shift uses low6 bits
10002cba4  clz   x15,x14
```

This is actual common-path work, so the source equivalence proposal in decode-followup-source-review.md is not already eliminated by this compiler. It does not establish a latency effect, explain the unresolved comparison or waive a performance gate. Only the redundant mask may be changed; the final left shift, unary maximum/end checks, stuffing, reset/seek and padding validation remain required. Candidate004 source/tests and machine-code delta still need independent review after AG provides them.
