# Async-boundary diagnostic observations

Both preserved controls and the unchanged production successor retain executed call boundaries in the emitted binary. The first unforced adapter was optimized away; it has no timing evidence and is retained as a failed control attempt.

This run does not establish a stable additive async-boundary cost. Async versus matched sync gives positive pooled deltas for 12-bit encode/decode but negative deltas for 16-bit encode/decode. Paired blocks change sign in the 16-bit cases, and the synchronous adapter also shifts materially against the original producer. Code-shape, specialization and process-execution effects remain confounded; no amount of the production regression is assigned to dispatch, and no waiver follows.

The controls preserve an ordinary module call using @inline(never), with an additional @concurrent boundary only in the async control. No production API, sample handling or safety checks changed. Emitted swift_task_switch calls establish an executor-boundary operation, not a physical thread-hop count. Main-campaign results retain their original baseline and are not replaced by these diagnostics.

All 64 condition samples were retained: 64 report AC power; 64 report no recorded thermal or performance warnings. These observations do not establish thermal isolation.

Each table cell is pooled ratio (delta microseconds), numerator versus denominator. The full JSON retains all four paired-block ratios and deltas for every comparison.

| Precision | Operation | Async/sync | Sync/original | Async/original | Successor/original | Successor/async |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 12 | encode | 1.0144 (+0.125) | 0.7518 (-2.875) | 0.7626 (-2.750) | 0.9892 (-0.125) | 1.2972 (+2.625) |
| 12 | decode | 1.1154 (+1.250) | 0.8150 (-2.458) | 0.9091 (-1.208) | 1.0282 (+0.375) | 1.1310 (+1.583) |
| 12 | prepare | 0.9863 (-0.042) | 0.9733 (-0.083) | 0.9600 (-0.125) | 0.8533 (-0.458) | 0.8889 (-0.333) |
| 12 | prepare_encode | 1.0071 (+0.083) | 0.9129 (-1.125) | 0.9194 (-1.042) | 0.9355 (-0.833) | 1.0175 (+0.208) |
| 16 | encode | 0.7446 (-2.958) | 1.0651 (+0.708) | 0.7931 (-2.250) | 1.0766 (+0.833) | 1.3575 (+3.083) |
| 16 | decode | 0.8481 (-2.000) | 1.0395 (+0.500) | 0.8816 (-1.500) | 1.0987 (+1.250) | 1.2463 (+2.750) |
| 16 | prepare | 0.9600 (-0.125) | 1.0135 (+0.042) | 0.9730 (-0.083) | 0.8784 (-0.375) | 0.9028 (-0.292) |
| 16 | prepare_encode | 0.9126 (-1.125) | 1.0334 (+0.417) | 0.9431 (-0.708) | 0.9967 (-0.042) | 1.0567 (+0.667) |
