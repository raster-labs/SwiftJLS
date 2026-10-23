# Remaining setup review after candidate004

Read-only review, 23 October 2026. Source identities are in `remaining-setup-source-review.json`; the preparation files and reader still match the accepted candidate004 identities. No implementation, build, profiling or timing was performed.

**Recommendation: no additional production change is justified by this source review alone.** The remaining uncertain comparisons are not proof that a particular setup operation regressed or dominates. Preserve the completed confirmation and investigate the independently observed host interference before attributing it to source.

## Actual benchmark boundary

`Scripts/Benchmark/Consumer.swift:39–46` constructs canonical UInt16 samples outside timing. `makeImage` at73–89 creates plane/shape descriptors, allocates a destination, and copies those canonical values into bytes. `prepare_seconds` at136–142 includes that work and destination cleanup; it excludes the later encode. All three patterns follow the same preparation code, same sizes, and same allocation/control path for a given shape. It does not run the sample formula or sample-precision helper inside this timed fill. Thus there is no source-backed flat/ramp-specific setup branch to remove.

The earlier useful reductions are already present: singleton descriptor sets are bypassed (`ImageDescriptor.swift:106–150`); fresh owned storage is initially reserved before publication (`ImageStorage.swift:74–94`); owned publication avoids repeated full public Image validation (`Image.swift:213–217`); metadata membership avoids constructed sets; encoder gradients use direct intervals. Empty metadata collections here do not establish another populated heap container.

## Remaining preparation costs are not proven redundant

`Image.swift:170–180` must admit the descriptor under the destination's own limits. A descriptor may have been constructed under different limits. `ImageStorage.swift:78–94` preserves allocation cancellation, decoded/memory bounds, fresh allocation and lease UUIDs, and zeroed storage. These are public storage semantics, not optional benchmark setup. `Image.swift:191–232` retains metadata-before-single-use ordering, exclusive fill, post-fill cancellation, sealing, final cancellation and cleanup. Public `destination.storage` can be retained, used concurrently or reentered, so a published destination cannot adopt the lock-free private decoder factory.

The two storage lock/lease admissions at `ImageStorage.swift:108–123` cover distinct borrow and seal operations. Combining them would require a new internal lifecycle operation and a proof of concurrent/reentrant failure and cancellation behaviour; it is not simply deleting a redundant check. There is currently no measured evidence that justifies that extra lifecycle design. Replacing UUIDs, dropping zeroing/checkpoints, or changing the Consumer would not meet this review's scope.

## Decode reaches the changed reader

`Consumer.swift:94–95` calls the ordinary public async Decoder, not QualifiedMonochromeDecoder. `CodecAPI.swift:207–210` dispatches to `ScalarCodec.decode`; `ScalarCodec.swift:231–234` constructs JPEGLSBitstreamReader and calls decodeFlatRegion. The kernel reaches readUnaryCount through its Golomb decoder at `JPEGLSScalarKernel.swift:805`. Candidate004's aligned-window change therefore is on the benchmark path. The independently verified instruction reduction proves a mechanism, not an elapsed-time improvement.

Owned scalar decode already uses the private fresh allocation/fill/seal factory (`ScalarCodec.swift:240–241`). Its remaining metadata/capacity checks, bounded header scan, kernel initialization, final scan validation, publication and deadline/cancellation checks cannot be discarded solely because this fixture has no metadata. The owned entropy reader still copies the scan into an Array (`JPEGLSBitstreamReader.swift:51–52`); replacing that retention model would be a separate borrow/lifetime redesign, not a narrow new duplicate-setup fix, and is not recommended to fit this unresolved noise comparison.

A falsifiable follow-up is the already assigned bounded profile: establish whether descriptor admission, UUID/storage lifecycle, or entropy decode actually occupies material time in the original boundary. If none does, retain the current source rather than invent a fixture-specific fast path. No claim is made about which component dominates from source alone.
