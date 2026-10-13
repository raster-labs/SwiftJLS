# Powered representative performance — 13 October 2026

**Measured improvements do not close PERF-01..03.** Residual regressions remain, and this powered developer workstation was monitored rather than physically isolated. No latency or size waiver is recorded. This is engineering evidence, not a marketing comparison.

## Source, scope and method

Final SwiftJLS: `36fb97e0a654c0d18802b666df2b07d24cb0637a`; pinned JLSwift: `15aa75164145414f3d5ffb801401c52d40cc5bcc`. Both release consumers use the identical current `Consumer.swift`, Swift 6.4 on Apple M4 Max/Mac16,5 with 64 GiB and macOS 27.0.1. Source/binary hashes and exact build/run commands are in [the evidence manifest](results/milestone4-powered-2026-10-13.json).

The owner selected representative larger RGB cases instead of the full 144-case grid. Final coverage is 24 scalar cases (37×23, 512², 2048², 4096×3073; 12/16 bits; flat/ramp/seeded noise) and 39 RGB cases: all 36 combinations at 512² (12/16 bits, three patterns, NEAR 0/3, all three interleaves), plus 4096×3073 12-bit flat lossless sample interleave, 4096×3073 16-bit noise lossless sample interleave and 2048² 12-bit noise NEAR 3 sample interleave. This does not qualify every large colour combination.

Each case has four alternating producer blocks, five warm-ups and five observations per producer/block: 20 observations per operation/producer. Full expected-sample checks precede timing; NEAR 3 checks the allowed absolute error. Encode, owned decode, preparation and directly measured preparation-plus-encode distributions include median, p95, range and throughput. Preparation starts from the same canonical UInt16 samples. Predecessor immutable-image validation occurs during preparation, while SwiftJLS validates borrowed meaningful-bit samples during encode. Summed medians are not used as combined timings.

The explicit development profile permits successor workspace up to 1 GiB and total memory up to 2 GiB, with other limits unchanged. The predecessor has no corresponding admission API. This permits the largest RGB conservative admission; it does not change production defaults. RSS includes canonical input, public input objects, output and runtime. Workspace/allocation/copy counters in benchmark records remain unknown.

## Final predecessor comparison

Ratios below are successor/predecessor median latency; lower is faster. Scalar rows use the 18 cases of width ≥512, excluding tiny harness cases from the overview. RGB rows include all 39 selected cases. Raw data includes every case, all 20 samples, p95, spread and individual paired-block ratios. Counts show both pooled medians above 1.05 and cases above 1.05 in every paired block; the latter helps distinguish repeated effects from noise without pretending to be a confidence interval.

| Cases | Operation | Ratio range | Median >1.05 | Every block >1.05 |
| --- | --- | --- | --- | --- |
| 18 scalar | Encode | 0.802–1.468× | 16 | 15 |
| 18 scalar | Owned decode | 0.498–1.200× | 8 | 8 |
| 18 scalar | Preparation + encode | 0.376–1.235× | 6 | 6 |
| 39 colour | Encode | 0.083–15.531× | 17 | 17 |
| 39 colour | Owned decode | 0.559–2.168× | 34 | 34 |
| 39 colour | Preparation + encode | 0.103–1.524× | 13 | 13 |

The largest differences are not explained away by preparation timing. In particular, flat RGB encode and decode still require investigation beyond the access-path improvements. Existing full-range scalar noise profiling also points to kernel/bit-writing work, where meaningful-bit scans are already skipped. A fresh ten-second CPU sample of the final 2048², 16-bit flat line-interleave binary shows activity in the interleaved run-detection loop and component accessors (InterleavedKernel.swift:54–61). Its consumer and sampler both exit 0. Sampling combines repeated encode/decode and is diagnostic only; compiler-folded accessor symbols do not precisely apportion costs. These are investigation leads, not quantified proof that every residual cost is necessary for safety.

Largest absolute median regressions among cases exceeding 5% in all four blocks (seconds, rounded):

| Case | Operation | Predecessor | Successor | Added time |
| --- | --- | --- | --- | --- |
| 4096×3073, 16-bit noise, RGB, NEAR 0, interleave 2 | decode | 1.474859 | 1.610114 | 0.135256 |
| 4096×3073, 12-bit flat, RGB, NEAR 0, interleave 2 | encode | 0.009382 | 0.132539 | 0.123157 |
| 4096×3073, 16-bit noise, scalar, NEAR 0, interleave 0 | encode | 0.379176 | 0.494928 | 0.115753 |
| 4096×3073, 12-bit noise, scalar, NEAR 0, interleave 0 | encode | 0.406361 | 0.501158 | 0.094796 |
| 4096×3073, 16-bit noise, scalar, NEAR 0, interleave 0 | prepare_encode | 0.423218 | 0.514895 | 0.091677 |

## Improvement against the preceding SwiftJLS source

A separate focused experiment compares old SwiftJLS `1b4964dc0205ac9a529e07df9742878f40853e29` with the final source, using the same new consumer/budget and four alternating blocks. This baseline is SwiftJLS, not JLSwift. It isolates the combined contiguous-validation and packed-row changes; an earlier validation-only experiment is also preserved. Medians below do not establish improvements for unmeasured profiles.

| RGB case, NEAR 0 | Encode ratio | Decode ratio | Preparation + encode ratio |
| --- | --- | --- | --- |
| 512×512, 12-bit flat, interleave 1 | 0.784× | 0.930× | 0.838× |
| 512×512, 16-bit flat, interleave 1 | 0.734× | 0.923× | 0.793× |
| 2048×2048, 12-bit flat, interleave 1 | 0.762× | 0.898× | 0.781× |
| 2048×2048, 16-bit flat, interleave 1 | 0.747× | 0.898× | 0.753× |
| 512×512, 12-bit noise, interleave 2 | 0.960× | 0.936× | 0.961× |
| 512×512, 16-bit noise, interleave 2 | 0.962× | 0.934× | 0.958× |
| 512×512, 12-bit ramp, interleave 0 | 0.870× | 0.949× | 0.871× |
| 512×512, 16-bit ramp, interleave 0 | 0.849× | 0.949× | 0.855× |

The flat encode medians improve roughly 22–27%; paired observations and their spread are retained. Other cases improve less. Views still borrow caller memory; the new boolean and address calculation introduce no sample owner or hand-off copy. Invalid meaningful bits and cancellation remain checked.

## Conditions and limits

All three final runs sampled AC power and no recorded thermal/performance warnings. Sampling every 30 seconds cannot exclude short disturbances. No local compilation, sanitiser or profiler ran concurrently with these final benchmark processes; ordinary workstation activity and lightweight documentation work remained. The first RGB load average was still elevated after earlier builds, so powered does not mean a fully isolated idle laboratory.

| Run | Condition samples | Sampled CPU idle range | One-minute load, first → last |
| --- | --- | --- | --- |
| RGB grid + largest | 24 | 69.70–85.35% | 41.92 → 3.31 |
| Scalar | 16 | 65.41–84.39% | 2.73 → 3.75 |
| Larger near-lossless | 8 | 75.44–83.81% | 3.46 → 3.49 |

Memory-pressure, VM swap counters and full conditions are retained. Lower process RSS does not establish lower algorithm workspace or compensate for latency regressions. The separate ordinary-build heap/copy evidence in [Milestone4.md](Milestone4.md) retains its own attribution limits.

## Size and historical attempts

Small flat RGB streams show percentage increases above 1%. The successor preserves explicit RGB interpretation using a 44-byte SPIFF header/directory. Near-lossless predecessor output can also include a 15-byte LSE segment absent from the successor, giving a net 29-byte difference. A separate marker/export and bidirectional sample-check experiment records the exact segments for all twelve flat 512² cases; all twelve entropy payloads are byte-identical, and all 24 cross-decodes pass sample checks. The observed differences are confined to headers. This metadata is a semantic API difference, not a compression speed benefit. Noise streams can differ in entropy decisions as described in [earlier validation](Validation.md); byte identity across producers is not promised, and the new measurements do not invent a waiver for size thresholds.

Initial powered runs used the preceding production source and old default-limit consumer: 24 scalar and 84 completed RGB cases, plus an interrupted partial case and a largest-RGB resource-admission failure. The latter returned `resourceLimitExceeded` before timing; the development executable reported an uncaught top-level error. It is not a codec memory-corruption finding. These records and the intermediate consumer/runner hashes remain distinct from final-source measurements. The full original RGB grid was intentionally stopped when the owner selected representative large-image coverage. Incomplete observations are excluded from completed counts.

The final current-source record consists of exactly 24 + 39 completed cases, with no failed final comparison command. Performance, complete per-operation workspace, exact native macOS minimum and required physical-device gates remain open; Milestone 5 is deferred.
