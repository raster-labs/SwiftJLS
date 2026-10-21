# Native sample-writer diagnostic

Diagnostic only; not promoted. The CLT release consumer builds, all 110 release declarations pass, and eight focused component/native declarations pass in release and ASan, with zero failures or skips. See `build-results.json` and `expanded-test-results.json`. No timings have run: AC admission failed after building, and the candidate waits for the parent to confirm a powered timing window.

## Concrete change and proof

The common sample-interleaved decoder loop is generic over its synchronous sample writer. Packed full-resolution UInt16 planes select the existing native-endian writer once per scan. General component access currently repeats the sample-width, packed-row, byte-order and raw-buffer handling for up to four neighbour reads and one store per regular sample. No claim is made yet about generated-code or measured improvement.

Descriptor admission proves every active sample address and scan geometry. Header admission permits subsampling only for line scans. The native selection additionally checks every view's width, height, sample width, pixel stride and packed row length, then obtains the existing guarded native layout. That layout keeps unaligned raw loads/stores: an odd owner base remains valid. The same regular/run loop, context, entropy reads, checkpoint placements and final scan validation remain. Non-native, padded, sparse and byte layouts take the general writer specialization.

There is one additional bounded array of up to four writer descriptors on eligible layouts, with no pixel allocation or copy. Account for that descriptor allocation if promoted; do not infer improved workspace from timing. The diagnostic is deliberately separate from rejected bit-reader and forced-inlining alternatives.

## Focused validation before promotion

1. Build this codec and `consumer/` only after the parent signals the timing window is clear. Use the explicit Swift 6.4 Command Line Tools toolchain and the same release flags as the frozen c330 consumer. Retain build logs and independent binary hashes; do not replace either original benchmark executable.
2. Run the existing complete component fixture/layout suite (including reference, HP, mapped/legacy, 8/12/16-bit, NEAR 0/3, planar and pixel destinations in both byte orders), then the complete test suite if the candidate is promising.
3. Run the two added `SampleNativeDecodeTests` regressions before promotion: full-resolution three-component entropy, widths 1/17/65, at least three rows, flat/run-interruption/ramp/noise, NEAR 0/3, 12/16-bit; compare every decoded sample for packed native planes on an odd buffer base against padded/opposite-endian/sparse planes and verify sentinel gaps. Verify cancellation at row entry and within long run fills leaves all later samples untouched. ASan and TSan are required after source promotion.
4. Compare identical public consumers against frozen c330 and pinned predecessor, alternating processes. Priority cases: 512x512 RGB sample-interleaved 12-bit ramp NEAR 0, ramp NEAR 3, noise NEAR 3. Controls: flat/sample, 16-bit sample ramp/noise, line and non-interleaved paths, plus the selected larger sample cases. Preserve encode timings too. No noisy one-shot or improvement on only one case is promotion evidence.
5. If retained, rerun final source-dependent qualification and workspace attribution. The current c330 archive/campaign remains a separate checkpoint.

`codec/Tests/SwiftJLSTests/Fixtures` is a read-only link to the unchanged repository fixture directory. Sources and test Swift files are independent copies. `candidate.patch` changes only InterleavedKernel.swift; `provenance.json` pins original/candidate source and identical consumer hashes.
