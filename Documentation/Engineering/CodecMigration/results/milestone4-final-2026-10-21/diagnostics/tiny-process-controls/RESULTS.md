# Frozen tiny process controls, 21 October 2026

All three controls completed, with unchanged frozen binaries and AC power throughout. No thermal or performance warnings were recorded in the captured snapshots. This is diagnostic evidence, not regression acceptance. Ratios below are right/left.

| Control | Bits | Operation | Pooled ratio | Four paired ratios | Left/right median µs |
| --- | ---: | --- | ---: | --- | --- |
| binary (isolated/canonical) | 12 | encode | 0.99283 | 1.00000, 1.00719, 0.98561, 0.98929 | 11.6250 / 11.5417 |
| binary (isolated/canonical) | 12 | decode | 0.98813 | 0.99408, 1.00000, 0.97917, 0.99107 | 14.0417 / 13.8750 |
| binary (isolated/canonical) | 12 | prepare | 0.98529 | 0.98551, 1.00000, 0.97101, 0.98529 | 2.8333 / 2.7917 |
| binary (isolated/canonical) | 12 | prepare_encode | 1.00000 | 1.00332, 1.00332, 0.99668, 0.99007 | 12.5417 / 12.5417 |
| binary (isolated/canonical) | 16 | encode | 1.00000 | 0.97241, 1.01767, 1.01724, 0.99291 | 11.8750 / 11.8750 |
| binary (isolated/canonical) | 16 | decode | 0.98830 | 0.95702, 1.00888, 0.98286, 0.99110 | 14.2500 / 14.0833 |
| binary (isolated/canonical) | 16 | prepare | 0.97102 | 0.97101, 0.98551, 0.94366, 1.00000 | 2.8750 / 2.7917 |
| binary (isolated/canonical) | 16 | prepare_encode | 0.98392 | 0.95327, 1.00326, 0.96412, 0.99349 | 12.9583 / 12.7500 |
| canonical-self (canonical/canonical) | 12 | encode | 0.99645 | 0.97552, 1.01444, 0.94898, 1.01252 | 11.7500 / 11.7083 |
| canonical-self (canonical/canonical) | 12 | decode | 0.99120 | 0.96571, 1.00597, 0.95739, 1.00000 | 14.2083 / 14.0833 |
| canonical-self (canonical/canonical) | 12 | prepare | 0.98551 | 0.95714, 1.01471, 0.94444, 1.00000 | 2.8750 / 2.8333 |
| canonical-self (canonical/canonical) | 12 | prepare_encode | 0.98697 | 0.95886, 1.00332, 0.94688, 0.99673 | 12.7917 / 12.6250 |
| canonical-self (canonical/canonical) | 16 | encode | 1.00000 | 0.97561, 1.00000, 1.01423, 1.02827 | 11.7917 / 11.7917 |
| canonical-self (canonical/canonical) | 16 | decode | 0.99408 | 0.97076, 1.00000, 1.01194, 1.00590 | 14.0833 / 14.0000 |
| canonical-self (canonical/canonical) | 16 | prepare | 1.00000 | 0.97102, 1.00000, 1.02985, 1.00000 | 2.8333 / 2.8333 |
| canonical-self (canonical/canonical) | 16 | prepare_encode | 1.00000 | 0.97917, 1.00328, 1.00656, 0.99673 | 12.7500 / 12.7500 |
| pinned-self (pinned/pinned) | 12 | encode | 0.99310 | 0.98616, 1.02422, 0.99654, 0.96599 | 12.0833 / 12.0000 |
| pinned-self (pinned/pinned) | 12 | decode | 0.98485 | 0.98480, 1.01520, 0.98471, 0.95562 | 13.7500 / 13.5417 |
| pinned-self (pinned/pinned) | 12 | prepare | 0.98701 | 1.00000, 0.98701, 0.96104, 0.97436 | 3.2083 / 3.1667 |
| pinned-self (pinned/pinned) | 12 | prepare_encode | 0.98131 | 0.98433, 1.01258, 0.98428, 0.95152 | 13.3750 / 13.1250 |
| pinned-self (pinned/pinned) | 16 | encode | 1.01045 | 1.01399, 1.01761, 1.01748, 1.00345 | 11.9583 / 12.0833 |
| pinned-self (pinned/pinned) | 16 | decode | 1.01238 | 1.00000, 1.04473, 1.01548, 1.01231 | 13.4583 / 13.6250 |
| pinned-self (pinned/pinned) | 16 | prepare | 1.02703 | 1.02740, 1.02703, 1.01333, 0.97436 | 3.0833 / 3.1667 |
| pinned-self (pinned/pinned) | 16 | prepare_encode | 1.01592 | 1.01278, 1.06116, 1.01270, 0.98758 | 13.0833 / 13.2917 |

Direct isolated/canonical decode ratios are about 0.988 at both precisions; the tested binary pair does not reproduce the earlier 14–21% gap. Canonical/self and pinned/self are separate-process negative controls and must not be compared as though collected in the same paired experiment. These results rule out a large stable binary-linked difference within this run, not all possible process/startup effects or all causes. Earlier final-source primary and deep-warm results remain retained; no scheduler or async-dispatch cause is established.

`results-1/environment.json` pins the actual producers, `raw.jsonl` files retain all four operation timing arrays and commands, `summary.json` files retain medians/ranges/paired ratios, and `complete.json` confirms collection plus final hash/power checks.
