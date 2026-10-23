# Correction Receipt for Rejected Draft `candidate004-source-investigation-and-publication-inventory.json`

- **Local original rejected draft path:** `/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/candidate004-source-investigation-and-publication-inventory.json`
- **Local original rejected draft SHA-256:** `791574c014bdb2fd1bef2fde430a40606d107c0235c2aa901e51c55e58c8a6bb` (`12052` bytes, retained byte-for-byte at the local scratch path above)
- **Public archive derivative path:** `source/rejected-draft/candidate004-source-investigation-and-publication-inventory.json` (`12409` bytes, SHA-256 `ca1b1a9f05c7c1e5b24759f26decc8f1ffa5621123d2bb4248595fd893f58767`; labelled `redacted_public_derivative: true` with `local_original_sha256` and `local_original_bytes` metadata and `/publication_inventory_plan/archive_sections_inventory/4` encoder-token redaction)
- **Disposition:** Local original (`12052` B) is preserved untouched in local scratch and represented in the public archive by its labelled redacted derivative (`12409` B); neither is used or propagated as qualification authority.

## Authoritative Corrections

### `C1_no_image_descriptor_change`
- **Rejected draft statement:** Claimed ImageDescriptor.init was modified to compute max sampling factors in a direct loop without KeyPath/LazyMapSequence.
- **Authoritative fact:** Sources/SwiftJLS/ImageDescriptor.swift (ba12d371e2583578a726aabde85fc244648821984bcf630ff365ec2a33e1cd26) is unchanged from base commit 4f6661a4ccec277d02e42b9228c7b574dfbf15cd. Do not credit an invented ImageDescriptor rewrite.

### `C2_jpeg_metadata_encoding_three_key_predicate`
- **Rejected draft statement:** Described the JPEGLSMetadata.swift change as checking duplicate extension IDs with a direct quadratic loop.
- **Authoritative fact:** Sources/SwiftJLS/JPEGLS/JPEGLSMetadata.swift (f44b40588d5f1f59b90c7f4b3a8d2ed9c968fe700bbe535248bcb5d65597d8ef) replaces the 128-byte supported-key Set construction in JPEGMetadataEncoding.init with a private three-key predicate JPEGMetadataEncoding.isSupportedKey(_ key: String) -> Bool checking key == JPEGLSMetadata.key || key == JPEGLSMetadata.spiffKey || key == JPEGLSMappingTables.key, evaluated via image.metadata.requiredKeys.allSatisfy(Self.isSupportedKey) and image.metadata.entries.keys.allSatisfy(Self.isSupportedKey). No duplicate-extension quadratic-loop change was made.

### `C3_gradient_table_seven_adjacent_ranges`
- **Rejected draft statement:** Described JPEGLSRegularMode.swift gradientTable initialisation as three contiguous range assignments.
- **Authoritative fact:** Sources/SwiftJLS/JPEGLS/JPEGLSRegularMode.swift (8397f5465973a78b316842fc6bbc7345a1df4a7d65ea2f3a8916977c6f072356) initialises the encoder gradientTable for near < t1 using seven adjacent ranges ([0, t3-t2+1) -> -3, [t3-t2+1, t3-t1+1) -> -2, [t3-t1+1, t3-near) -> -1, [t3-near, t3+near+1) -> 0, [t3+near+1, t3+t1) -> 1, [t3+t1, t3+t2) -> 2, [t3+t2, 2*t3+1) -> 3) via Array(unsafeUninitializedCapacity:), preserving the encoder's original near-first branch fallback when near >= t1.

### `C4_bitstream_reader_aligned_window_expression`
- **Rejected draft statement:** Described the JPEGLSBitstreamReader.readUnaryCount change as complemented-buffer (~bitBuffer).leadingZeroBitCount.
- **Authoritative fact:** Sources/SwiftJLS/JPEGLS/JPEGLSBitstreamReader.swift (5f71d419cb389235dbc756d3a1c0df6f888c860427f40f867250b9f031202485) defines alignedWindow() returning bitBuffer &<< (64 &- bitsInBuffer) (with caller let window = alignedWindow(); let zeros = min(window.leadingZeroBitCount, bitsInBuffer) followed by guard zeros <= maximum - count), reducing the buffered-window-to-bounded-zero machine sequence from 13 instructions in candidate_003 to 6 instructions (ldr/neg/lsl/clz/cmp/csel) in candidate_004.

### `C5_diag72_002_process_count_1728`
- **Rejected draft statement:** Listed diag72-002 completed process count as 1,296.
- **Authoritative fact:** Completed candidate_003 diagnostic run campaigns/runs/diag72-002 has 1,728 process records (72 rounds x 6 cases x 4 arms = 1,728 processes), verified by diag72-002-independent-results.json and diag72-002-result-review.md.

### `C6_larger15_campaign_inventory`
- **Rejected draft statement:** Listed a non-existent campaigns/runs/larger15-002 (480 records, 12/15).
- **Authoritative fact:** Under candidate_003 (campaigns/runs/), only the stopped partial larger15-001 (32 retained records) exists; it does not qualify candidate_004. Under candidate_004 (campaigns_004/runs/larger15-001), the completed 120-process larger15 guard (15 cases x 4 paired blocks x 2 arms = 120 processes) passed all 60 pooled case/operation ratios <= 1.05 (max 0.9525338096826315 for 512x512-p16-ramp-c3-n0-i0 encode), verified by candidate004-larger-independent-results.json and candidate004-larger-result-review.md.

### `C7_bounded_source_review_scope`
- **Rejected draft statement:** Asserted that candidate_003/candidate_004 already eliminated all genuinely redundant general work.
- **Authoritative fact:** No absolute claim is made that all possible redundant work is eliminated. The independent bounded source review (remaining-setup-source-review.md) and disassembly check found no further justified safe production change within contract boundaries.
