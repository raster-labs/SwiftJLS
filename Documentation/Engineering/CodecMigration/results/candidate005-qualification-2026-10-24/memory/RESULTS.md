# Candidate005 Linux workspace and copy results

Collection and independent replay completed successfully on 24 October 2026, before timing. Source receipt `87bda184d21845362608a5a0b2198a9d6840a4324c5bdf2e8f6c5d9978e299e6` binds all 2,985 source, test, fixture, probe and tool files; the postflight identity guard passed. Shared services remained running. No failed attempt or classifier modification occurred.

- All 89 raw workspace profiles replay exactly with the unchanged corrected classifier; all 267 recorded profile commands exited zero, and all sample verifications passed. There are no unattributed codec allocations or live codec baseline bytes.
- The 23 owned decodes each allocate one final pixel buffer. The other 66 operations allocate no owned pixel buffer. All categories, simultaneous operation totals and baseline deltas reconcile.
- CopyProbe has 20 passing rows: ten ordinary zero-source-copy cases and ten positive controls moving exactly the source capacity. All decoded samples meet NEAR. Its interposition does not observe inlined copies.
- Maximum-table scalar NEAR encode has 143,891 requested algorithm heap bytes above its 48-byte live algorithm baseline (143,939 live peak). Candidate004's corresponding peak is 917,497 bytes larger. The change matches `(2*65535+1)*(8-1)` exactly; the fresh observed above-baseline bytes include 112 bytes beyond the 143,779-byte context/table/row source payload.
- The 129-range restart inspection removes 18 metadata/control allocation calls and 4,608 cumulative requested bytes versus candidate004. Its metadata/control live peak is 1,008 bytes lower. This is consistent with reserving the directory once; it is separate from prediction state.
- The largest whole-operation requested-heap peak across the measured profiles is 6,283,207 bytes for `512-3-0-owned`, with a 3,969,192-byte baseline and a 2,314,015-byte increase. Category maxima are not added together.

`completion.json`, `reconciliation-summary.json`, command receipts and every raw `workspace89/profiles/*/allocations.gz` remain available. The Linux WorkspaceProbe binary is `4862ff99dd9941e7b24c2ffda8b6e339503a3f5dddefb2eb43e92167199d38fa`; CopyProbe is `82f8a1c9f3ca584e4badc579648e1c067e9434f1e29046d5e73d7fae65d5cb0a`.

This supports the source-level bounded-workspace and no-extra-image evidence for these operations. It does not measure allocator usable-size overhead, codec-only stack, VM residency, concurrent calls, every possible input, or Apple RSS. `peakWorkspaceBytes` remains nil and the existing empirical `pure_algorithm_workspace_complete` field remains false. RSS needs its own prespecified experiment and disposition. Physical-device qualification and milestone5 remain pending.
