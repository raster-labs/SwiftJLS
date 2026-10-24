# 001 — preparation and encoding cost review

Reviewed clean `4f6661a4ccec277d02e42b9228c7b574dfbf15cd`. AG remains sole implementation writer. [Identity receipt](001-preparation-encode-source-review.json) pins reviewed files to HEAD and the actual retained three-change source snapshot; the checkout was clean at both checks. No builds, tests, profiling or timing were run. These are bounded optimisation candidates, not an explanation or waiver for measured regressions.

## Actual path and prior evidence

`Scripts/Benchmark/Consumer.swift:73–89` constructs planes/descriptor, calls public `ImageDestination.allocate(descriptor:)`, then its raw `write` closure. It does **not** call `writeUInt16`, so optimising that helper cannot improve these cases. Preparation includes the destination's destruction before return; the fresh Image survives the await through encode. The measured combined interval is makeImage plus public encode (Consumer:136–145).

`Encoder.encode` (CodecAPI.swift:170–181) keeps @concurrent execution, cancellation/operation limits and component dispatch. ScalarCodec.swift:50–98 validates the descriptor, metadata, precision and budgets before constructing the writer/kernel. The new private factory is only scalar-owned **decode** (ScalarCodec:240–241), so it does not accelerate public makeImage preparation.

Current JPEGMetadataEncoding and regular-mode encoder source are byte-identical to the retained three-change arm. OwnedImageStorage differs from that arm only by the added decode factory; its ordinary allocation/reservation implementation is unchanged. These costs therefore are opportunities to reduce total work, not established causes of the historical delta. Prior048/050/052 zero-ICC and instrumentation results remain unchanged: no proven zero-ICC benefit or isolated executor attribution. Do not repeat those ablations or alter public executor policy.

## Ranked candidates

### 1. Remove the encode metadata membership sets

[JPEGLSMetadata.swift:164–169](/Users/pushparaj/projects/SwiftJLS/Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift:164) constructs a three-string supported Set on every encode, and constructs Set(entries.keys) under preservation. Replace with a private exact predicate for the same three keys, using requiredKeys.allSatisfy and entries.keys.allSatisfy. Keep metadata.validate first, the required-key check before the preserve/discard check, the same unsupportedFeature error, and all ancillary/SPIFF/mapping parsing and budget arithmetic afterwards. Required unsupported keys must still fail under discard; optional unsupported keys may pass only under discard.

This has concrete existing allocation evidence: accepted workspace89-linux-005-replay-043 `17-1-0-encode/operation.json`, stack541, records one128-byte `_SetStorage` allocation through JPEGMetadataEncoding per measured encode. This is Linux requested-heap evidence, not a Mac latency estimate. Empty metadata avoids both key walks after the change without a fixture-specific path or process-global cache.

**Focused criteria:** existing MappingMetadataTests (ancillary, SPIFF, maps, required/discard) plus exact error assertions for optional unknown keys under preserve/discard, required unknown keys under both policies, missing required value and metadata-limit precedence. Include empty Data values and malformed supported metadata to ensure validation/parsing was not accidentally skipped. No byte/signalling/fidelity change.

### 2. Initialise encoder gradient intervals directly

[JPEGLSRegularMode.swift:99–119](/Users/pushparaj/projects/SwiftJLS/Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift:99) zero-fills an Int array then branches and stores for every element. Decoder already uses direct constant intervals. For NEAR<T1, initialise the encoder's same array once with seven adjacent ranges via unsafeUninitializedCapacity, without a temporary segment array:

```
[0, T3-T2+1)           -3
[T3-T2+1, T3-T1+1)     -2
[T3-T1+1, T3-NEAR)     -1
[T3-NEAR, T3+NEAR+1)    0
[T3+NEAR+1, T3+T1)      1
[T3+T1, T3+T2)          2
[T3+T2, 2*T3+1)         3
```

Validated1<=T1<=T2<=T3<=65535 and NEAR<T1 prove a complete nonoverlapping partition, including empty intervals/equal thresholds, on32-bit Int too. Keeping these seven ranges preserves even the old private table endpoints; quantizeGradient's unchanged outer checks still return±4. Preserve the **encoder's own** existing branch loop for NEAR>=T1: its near-first precedence differs from the decoder reference in this internal case, so blindly sharing the decoder fallback is incorrect. Preserve allocation budget, constructor error checks and all kernel checkpoints. This affects both standalone/fresh encoding; no preparation-only effect is promised.

**Focused criteria:** independent encoder branch oracle, all small ordered threshold triples and near values, every sample gradient for defaults2...16, equal thresholds, NEAR==T1/>T3 fallback, maximum table, and Int.min/max outer clamps. Existing GradientTableTests only test the decoder and are not sufficient alone. Use aggregate first-mismatch assertions per profile rather than hundreds of thousands of individual expectations; retain public lossless/near fixtures and exact encoded-byte comparisons.

### 3. Preparation-specific: initialise fresh owned storage already reserved

[Image.swift:173–176](/Users/pushparaj/projects/SwiftJLS/Sources/SwiftJLS/Image.swift:173) creates a new OwnedImageStorage then its private destination initializer calls reserveWrite (line160). [ImageStorage.swift:55–73](/Users/pushparaj/projects/SwiftJLS/Sources/SwiftJLS/ImageStorage.swift:55) creates `.available` state, then takes the atomic admission gate and mutex solely to switch the still-unpublished object to `.writing` with a new UUID-backed lease. There is no external reference or callback between these operations.

A narrowly internal fresh-reserved factory could return `(OwnedImageStorage, StorageWriteLease)` with initial state already `.writing`, lease stored, and operationActive=false. The private destination initializer accepts that same lease. Preserve descriptor/combined-limit preflight before allocation; Task cancellation then byteCount limits before UUID/zero-array allocation; fresh allocationID and fresh UUID lease; no extra storage reference or pointer escape. After destination publication, **all** atomic/mutex/lease checks remain unchanged. Public OwnedImageStorage.init still creates available state and public reserveWrite stays unchanged. Do not replace UUIDs, bypass storage gates for later operations, merge unrelated locks, or skip final cancellation. This removes one uncontended construction-time CAS+mutex+release sequence, not the public lifecycle or its control allocations. Benefit is unmeasured and may be small; candidate1 is lower risk.

**Focused criteria:** public allocate exposes storage already reserved (second reservation rejects before fill); abandonment invalidates; successful fill preserves allocationID and samples; forged/foreign lease rejects; throwing/post-fill-cancelled writes invalidate; external providers retain one reserve callback and full validation; existing metadata-preflight retry and limits/cancellation-order tests remain unchanged. Existing OwnershipTests cover public concurrent/reentrant reserve semantics; add one allocated-destination boundary test because a fresh-reserved constructor is a distinct path.

## No further scalar mapping-set saving

ImageDescriptor.swift:104–116 already recognises one component/plane/slot and bypasses mapped.insert; line148 bypasses mapped.count. Its empty `Set<Int>()` does not create a populated table on this scalar path. PlaneDescriptor:33 similarly bypasses component uniqueness allocation for one component. Do not claim this optimisation again or weaken general layout mapping/overlap checks. Revalidating descriptor limits at encode is necessary because operation limits may be stricter than construction limits; current validate already checks only immutable cached extent/dimension/ICC values.

Recommend AG prepare1 and2 as narrow separately reviewable patches, with3 contingent on its construction proof and direct preparation evidence. Keep original Consumer, all operations, matched baselines, source/binary pins and preserved failed/uncertain outcomes. Only controlled candidate results can establish that the preparation/combined gates improved or closed; existing Linux allocation evidence alone cannot establish Mac timing acceptance.
