# Candidate 004 Linux workspace and copy audit

Accepted **scoped** evidence. Candidate 004 source receipt `4a1b7554778f6f551186f8497d93f599d001d4fe1090eeba6972dcb2436adfed`; base `4f6661a4ccec277d02e42b9228c7b574dfbf15cd`. All 38 production and 31 test Swift files plus Package.swift, probes, fixtures and measurement inputs matched the frozen snapshot and live checkout before/after collection (2,923 files). The codec Package.swift is pinned separately from the receipt’s benchmark-arm Package.swift. No repository changes or shared-container start/stop/kill were performed.

The existing Swift 6.4 arm64 image and private libunwind 1.8.3 recipe were used. The built WorkspaceProbe SHA256 is `805c3545c1a96303bfb4081a64ec5dbebffacdbe3dba52a7d5b816d6d7b79597`. The failed partial matrix and successful fresh matrix used this same executable. Fresh matrix command exited 0; all 89 profiles/267 traced commands passed. Independent replay of all 89 raw profiles with both original and corrected classifiers (178 replays) reproduced the reports and preserved simultaneous heap totals. All sample/fixture reports match the previous factory 002 profiles. There are 23 owned pixel allocations, zero across the other 66 operations, and zero unattributed codec allocations.

| Phase allocation category | Candidate 004 calls | Factory 002 calls |
|---|---:|---:|
| Algorithm |1662|1662|
| Compressed buffers |447|447|
| Metadata/descriptors |1948|1968|
| Pixel owners |23|23|
| Storage control |78|78|
| Runtime/unattributed |254|254|
| Unattributed codec |0|0|
| Total |4412|4432|

Each of 20 encodes removed one 128-byte metadata Set allocation (20 calls/2,560 requested bytes in total). The retained baseline stack identifies `JPEGMetadataEncoding.init`’s Set literal. All other categories’ phase allocation calls and requested bytes are unchanged; this statement does not equate their differing baseline or peak values. Largest simultaneous requested-heap phase peak is 6,287,007 bytes for `512-3-0-owned`, comprising 3,969,112 retained baseline bytes plus 2,317,895 bytes above baseline. This is neither algorithm-only workspace nor RSS.

The original classifier stopped the first matrix after 10 profiles: the new private `OwnedImageStorage.init(reservedByteCount:allocationID:lease:)` UInt8 pixel array was mistaken for a storage-control allocation by an older fallback. Its exact allocator/array/constructor chain and source lines 65–72 establish the category. The external correction requires that immediate seven-frame chain; it passes existing controls plus wrong allocator/type/intervening frame/constructor/size controls. Across the fresh raw matrix it moves 16 pixel calls (5,140,094 requested bytes) from the old control label without altering any raw totals. Corrected classifier SHA256: `a1d97dca4c65b025992a5fed0a259ad2e76a412c6e202b293ccf70c80b5799d6`. AG alone owns any eventual repository publication; verify byte identity to this file when published.

CopyProbe exited 0 and independently reconciled 20 rows: 10 ordinary zero-copy readings and 10 injected full-capacity positive controls, all samples within NEAR. Binary SHA256 `e5ad978d9ab40ef91cb070a986dd7f7de8c870e9ef47ae64c81dfed58a928847`. Copy telemetry observes ordinary memcpy/memmove source reads and cannot establish absence of inlined copies.

All failures are retained: initial zero-command package-field preflight failure; first 10-profile classifier failure; external replay-adapter input-shape failure before a corrected collection started. The latter was repaired by supplying the existing replay function its required list of lines, without changing the classifier. No failed sample was dropped from an accepted matrix.

Raw profiles, commands, consumer outputs, source maps, binary hashes, original and corrected classifiers, source proof, strict reconciliation and exact per-profile deltas are retained here. `complete.json` pins the compact key receipts; `reconciliation-summary.json` contains machine-readable results. Build directories/binaries remain in this audit workspace; archive tooling can omit duplicate build trees while preserving identity receipts and raw profiles.

Requested bytes exclude allocator overhead, stack, VM mappings and RSS; category peaks occur at different instants. The source/scoped heap accounting evidence is complete for this fixed matrix; universal `peakWorkspaceBytes` remains nil. Apple RSS, physical-device and deferred milestone 5 gates are unchanged. All validation/replay processes exited before the heavy-work release to the platform agent.
