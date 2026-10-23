# Decoder follow-up — source mechanism, not regression attribution

Read-only review during larger timing. [Source hashes](decode-followup-source-review.json) pin the inspected files. No build, consumer, compiler/disassembly inspection, profile or timing was run. Interop preparation/execution is paused until final source selection.

Parent reports47/48 short endpoints passing, with `p12-noise` decode versus three-change unresolved at median0.985996 and family48 interval[0.921371,1.067329]. Those statistics are the parent's current result, not independently recomputed by this source audit. They do not establish a confirmed slowdown. Candidate003 changes only encoder metadata/table setup and the public allocated-destination construction; scalar-owned decode still takes the unchanged fresh factory. Reader/context/kernel/regular-decoder files are unchanged from base4f6661a. No fixture-specific path or threshold waiver is justified.

## One bounded opportunity: redundant unary-window mask

`JPEGLSBitstreamReader.swift:204–206` computes:

```
let mask: UInt64 = (1 << UInt64(bitsInBuffer)) &- 1
return (bitBuffer & mask) << UInt64(64 - bitsInBuffer)
```

For b=bitsInBuffer and1<=b<=63, shifting UInt64 left by64-b discards every bit at index>=b. Therefore `(x & ((1<<b)-1)) << (64-b)` is exactly `x << (64-b)` for every bitBuffer value, including consumed high-bit garbage. Removing only the mask expression cannot change any decoded bit.

The sole caller is `readUnaryCount` (around265–269), after refill/guard establishes b>0. Refill starts an iteration only at b<=48 and adds at most15 bits, hence b<=63; readBits/unary only reduce it. No new pointer, buffer, cache, owner, allocation, arithmetic domain or cancellation interval is introduced. Do not remove the separate end-of-scan padding mask: it has different semantics. Retain unary maximum checks, early-end errors, stuffing, reset/seek accounting and all decode checkpoints unchanged.

**Required first falsification:** after the timing window, inspect the frozen release implementation of readUnaryCount/alignedWindow. LLVM may already remove the redundant mask. If there is no corresponding machine work, discard this candidate without a build/benchmark campaign. If retained, a one-expression source change removes actual per-unary work across scalar/component streams, rather than altering API policy or special-casing noise.

**If implemented:** focused reader regression against an independent bit-by-bit oracle should cover high consumed bits remaining in bitBuffer, mixed unary/readBits consumption, FF00/FF7F stuffing near refill boundaries, one remaining valid bit, maximum-prefix acceptance and one-bit-over rejection, truncated zero prefix and unchanged scan padding. Include existing lossless/near, restart, malformed and external-oracle paths. Controlled comparison remains necessary; no source-derived speedup estimate is defensible.

## Other inspected costs

The bitstream reader owns `[UInt8](data)` and a class; scalar decode also constructs bounded context and decoder-table storage per scan. These are real costs, but replacing their ownership model or inline context layout would exceed this one-expression proposal and repeat previously rejected broad experiments. The context's pixelCodingState already coalesces record reads; its checked noncopyable ManagedBuffer lifetime remains useful. Decoder table intervals are already initialised directly. Prior027 repeated-admission proposals and001 encoder/preparation candidates are not new noise-decoder mechanisms; do not recycle them as a causal explanation.

This brief offers one falsifiable common-path simplification and no implementation authorisation. Final-source software/platform/interop evidence must remain tied to whichever candidate is actually accepted.
