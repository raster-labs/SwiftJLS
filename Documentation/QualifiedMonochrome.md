# Caller-workspace monochrome decoding

`QualifiedMonochromeDecoder` is an advanced synchronous API for applications that supply both decoded pixels and algorithm scratch. It returns `QualifiedOutcome` values rather than throwing. It is separate from the common `Decoder`, which retains storage owners across asynchronous execution and manages publication and invalidation.

Select `.jlswift0101` explicitly. The implementation is adapted from JLSwift `d17545284a23e93f3d884a18f1046c4e305daa35`; it is not a dependency on the predecessor package. This profile is intended for known predecessor assets. Use the common `Decoder` for its standard interpretation, metadata preservation, layout flexibility and owning lifetime contract.

## Interpretation and output

The profile accepts one non-interleaved monochrome scan with unsigned 2–16-bit precision, near-lossless coding, supported presets, sequential row restarts and predecessor mapping/extended-dimension conventions. Output is tightly packed, host-endian `UInt16`. Input metadata is scanned without preserving ancillary payloads.

The profile explicitly retains predecessor implicit defaults (including low MAXVAL and high NEAR), final LSE preset selection (including after SOS), X-before-Y extended dimensions preceding SOF, and mapping continuations without the standard width field. The point-transform field is reported as metadata; this compatibility profile does not shift reconstructed samples. Do not infer a standard point-transform fidelity guarantee from a successful result. HP colour transformations and multi-component images are rejected. Missing selected mapping tables, indices outside supplied tables, unsupported markers/extensions and malformed entropy are rejected more strictly than in the pinned predecessor. Standard-width mapping continuations and other interpretation profiles remain available through the common decoder's separately documented controls.

Implicit defaults can differ from standard streams even at 8-bit and higher precision when NEAR is large. This profile also retains the predecessor minimum Golomb escape width of two bits. It cannot identify a producer from the stream: select it only for known predecessor assets. Explicit standard presets resolve the verified high-NEAR threshold differences, but do not make this a general standard profile.

Inspection validates the complete header, marker and restart envelope. It does not decode or certify the entropy payload. Decoding may fail after writing some samples; only a successful result permits use of the output.

## Borrowing and admission

Keep input immutable and keep input, output and scratch alive and disjoint throughout each call. Cancellation callbacks must not mutate input or access mutable output/scratch. Output and scratch require exclusive access. Supply raw trivial scratch aligned to `workspaceAlignment`, with at least `workspaceByteCount` bytes. The scratch binding may change. Output must be suitably aligned, initialised `UInt16` storage with capacity for every sample. No borrowed pointer escapes, but the unsafe API cannot prove the lifetime or validity of arbitrary pointers supplied by an application. Never carry these borrows across `await`.

The limits independently constrain encoded bytes, pixels, dimensions, output capacity, workspace capacity, combined memory and a monotonic deadline. Full supplied capacities count, including unused output/scratch suffixes. Invalid limits produce a failure value. Larger limits require an explicit caller choice. A caller cancellation hook is a synchronous C function plus an optional context pointer; keep the context alive and synchronise it if another thread modifies it. The hook must itself avoid allocation if the application requires an allocation-free call chain. The API does not query Swift task cancellation or create a task.

An application can allocate reusable buffers outside the operation, then borrow them synchronously:

```swift
let decoder = QualifiedMonochromeDecoder(profile: .jlswift0101)
let scratch = UnsafeMutableRawPointer.allocate(
    byteCount: QualifiedMonochromeDecoder.workspaceByteCount,
    alignment: QualifiedMonochromeDecoder.workspaceAlignment)
defer { scratch.deallocate() }

let result = encoded.withUnsafeBytes { input in
    samples.withUnsafeMutableBufferPointer { output in
        decoder.decode(input, into: output,
            workspace: .init(start: scratch,
                count: QualifiedMonochromeDecoder.workspaceByteCount))
    }
}
switch result {
case .success(let info):
    // Only now publish the first info.sampleCount reconstructed samples.
    consume(samples, info)
case .failure(let failure):
    // Discard partial output. Format/log failure facts outside the codec call.
    handle(failure.code)
}
```

Here `encoded` is the caller's `Data`, `samples` is a sufficiently sized and initialised `[UInt16]`, and `consume`/`handle` are application functions. `Array` copy-on-write or buffer creation belongs to caller setup; this example alone is not proof that an entire application transaction allocates nothing. An application requiring tighter control can retain raw allocations and pass scoped spans directly.

## Memory evidence and limits

The selected core has no owning input, output, context, palette or parser containers and no throwing adapters. Its scratch payload is defined by `workspaceByteCount`, rather than inferred from an image dimension. The common decoder still uses its own bounded workspace and continues to report unknown universal workspace totals as `nil`.

Fixed stack controls, allocator/runtime bookkeeping, thread stacks and application callbacks are separate from caller scratch. Source bounds and observed allocator counts must not be represented as a universal heap-plus-stack guarantee. The development-only `Examples/QualifiedAllocationProbe` exercises ordinary Linux allocation observation with positive controls; sanitizer runs verify memory safety separately. Exact validation scope and remaining release gates are recorded in [the recent-fix validation record](Engineering/CodecMigration/RecentFixes.md).
