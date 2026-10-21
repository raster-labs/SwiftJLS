# Same-process tiny-image diagnostic — 21 October 2026

The unchanged c330b731 successor and pinned 15aa751 predecessor ran in one executable. The current host HEAD a0aa84d is recorded separately and has exactly matching source/package hashes and clean source diffs. The original public wrappers and timing boundaries are retained; both producer orders alternate every observation. Four processes per precision each use 20,000 warmups and 1,000 observations per producer. All 8 processes exited 0.

All 16 before/after observations report AC power with no recorded thermal/performance warning. This is sampled workstation condition evidence, not thermal isolation. No build or other benchmark ran concurrently.

Ratios are successor/predecessor; delta is successor minus predecessor.

| Bits | Operation | Pooled ratio | Delta µs | Four paired-block ratios | Order ratios: predecessor first / successor first |
| --- | --- | ---: | ---: | --- | --- |
|12|encode|0.99303|-0.0833|0.99293, 0.99315, 0.99298, 1.00341|0.99654 / 0.99296|
|12|decode|1.03021|+0.4167|1.02134, 1.03264, 1.03049, 1.03812|1.03021 / 1.02711|
|12|prepare|0.89610|-0.3333|0.90132, 0.89744, 0.88312, 0.91026|0.89610 / 0.89610|
|12|prepare_encode|0.95963|-0.5417|0.95912, 0.95468, 0.95625, 0.97121|0.95963 / 0.95652|
|16|encode|1.00000|+0.0000|1.00350, 0.99652, 1.00345, 1.00000|1.00000 / 1.00351|
|16|decode|1.03333|+0.4583|1.02744, 1.03030, 1.04204, 1.03333|1.03647 / 1.03021|
|16|prepare|0.90789|-0.2917|0.89474, 0.90790, 0.90789, 0.90789|0.90789 / 0.90789|
|16|prepare_encode|0.96885|-0.4167|0.96562, 0.96562, 0.96904, 0.97508|0.97500 / 0.96273|

| Bits | Operation | Predecessor median / p95 µs | Successor median / p95 µs |
| --- | --- | ---: | ---: |
|12|encode|11.9583 /14.1250|11.8750 /14.3333|
|12|decode|13.7917 /16.1250|14.2083 /16.8333|
|16|encode|11.9583 /14.1250|11.9583 /14.0417|
|16|decode|13.7500 /16.0000|14.2083 /16.5833|

Decode medians are approximately 3.0–3.3% higher in this diagnostic, with all four paired blocks below 5%; encode medians are essentially equal. The direction persists under either first-producer order. Preparation and preparation-plus-encode are lower for both precisions.

These observations show that the larger historical tiny-case ratios are sensitive to the measurement context. They do not identify scheduler, allocator, cache or code-layout contributions: both libraries/images coexist here and the executable layout differs from the original separate-process campaign. Do not infer a physical thread-hop count. This diagnostic does not replace the original baseline, establish production performance acceptance, or automatically waive any recorded regression. Raw samples, full distributions/order stratification, conditions and before/after identity proofs remain authoritative.
