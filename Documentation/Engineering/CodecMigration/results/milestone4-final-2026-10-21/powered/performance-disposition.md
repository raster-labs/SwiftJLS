# Final performance observations

Source: `bee49a2ad47eae4ea149bdced2043b7a45df3dae`. No acceptance decisions or waivers are assigned.

The main campaign and six-case deep-warm repeat remain separate. Historical original-process outliers are preserved; earlier same-process context results identify no async mechanism and assign no waiver. RSS includes the entire process and is not algorithm-workspace accounting.

## scalar

Lossless scalar public API. Owned decode, release without sanitizers. Four alternating process blocks, each with 5 warmups and 5 timed iterations. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.

| Case | Operation | Predecessor µs | Successor µs | Delta µs | Pooled ratio | Four paired ratios |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 37×23 p12 flat c1 NEAR0 i0 | decode | 17.688 | 20.104 | +2.417 | 1.1366 | 0.8099, 1.2016, 1.2308, 1.1991 |
| 37×23 p12 flat c1 NEAR0 i0 | prepare | 3.979 | 4.229 | +0.250 | 1.0628 | 0.9710, 0.9894, 1.1584, 1.1957 |
| 37×23 p12 noise c1 NEAR0 i0 | decode | 30.958 | 33.229 | +2.271 | 1.0734 | 1.0209, 1.0179, 0.9865, 1.3691 |
| 37×23 p12 noise c1 NEAR0 i0 | prepare | 3.042 | 3.500 | +0.458 | 1.1507 | 1.3611, 1.2174, 1.1351, 1.0676 |
| 37×23 p16 flat c1 NEAR0 i0 | decode | 15.063 | 18.167 | +3.104 | 1.2061 | 1.2080, 1.3892, 1.1511, 1.1425 |
| 37×23 p16 flat c1 NEAR0 i0 | prepare | 3.333 | 3.625 | +0.292 | 1.0875 | 1.1282, 1.1125, 1.1375, 0.9286 |
| 37×23 p16 noise c1 NEAR0 i0 | prepare | 3.396 | 3.604 | +0.208 | 1.0613 | 1.1154, 1.1169, 0.9892, 1.2105 |
| 37×23 p16 ramp c1 NEAR0 i0 | prepare | 3.208 | 3.687 | +0.479 | 1.1494 | 1.0519, 1.2714, 1.1294, 1.0118 |

### Encoded size above 1.01

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

### Whole-process peak RSS above 1.05

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

## colour

RGB public API; selected_cases records the executed subset of the NEAR 0/3, three-interleave grid. Owned decode, release without sanitizers. Four alternating process blocks, each with 5 warmups and 5 timed iterations. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.

| Case | Operation | Predecessor µs | Successor µs | Delta µs | Pooled ratio | Four paired ratios |
| --- | --- | ---: | ---: | ---: | ---: | --- |

No encode/decode/prepare/preparation-plus-encode pooled ratio exceeds 1.05.

### Encoded size above 1.01

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |
| 512×512 p12 flat c3 NEAR0 i0 | 536 | 580 | 1.0821 |
| 512×512 p12 flat c3 NEAR0 i1 | 482 | 526 | 1.0913 |
| 512×512 p12 flat c3 NEAR0 i2 | 339 | 383 | 1.1298 |
| 512×512 p12 flat c3 NEAR3 i0 | 515 | 544 | 1.0563 |
| 512×512 p12 flat c3 NEAR3 i1 | 483 | 512 | 1.0600 |
| 512×512 p12 flat c3 NEAR3 i2 | 340 | 369 | 1.0853 |
| 512×512 p16 flat c3 NEAR0 i0 | 755 | 799 | 1.0583 |
| 512×512 p16 flat c3 NEAR0 i1 | 557 | 601 | 1.0790 |
| 512×512 p16 flat c3 NEAR0 i2 | 414 | 458 | 1.1063 |
| 512×512 p16 flat c3 NEAR3 i0 | 596 | 625 | 1.0487 |
| 512×512 p16 flat c3 NEAR3 i1 | 513 | 542 | 1.0565 |
| 512×512 p16 flat c3 NEAR3 i2 | 370 | 399 | 1.0784 |
| 4096×3073 p12 flat c3 NEAR0 i2 | 2115 | 2159 | 1.0208 |

### Whole-process peak RSS above 1.05

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

## final-tiny-deep-warm

Lossless scalar public API. Owned decode, release without sanitizers. Four alternating process blocks, each with 20000 warmups and 1000 timed iterations; small-image steady-state repeat. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.

| Case | Operation | Predecessor µs | Successor µs | Delta µs | Pooled ratio | Four paired ratios |
| --- | --- | ---: | ---: | ---: | ---: | --- |

No encode/decode/prepare/preparation-plus-encode pooled ratio exceeds 1.05.

### Encoded size above 1.01

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

### Whole-process peak RSS above 1.05

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

## Recorded conditions

Power observations: {"ac": 604}. Thermal observations: {"no_recorded_warning": 49, "not_sampled": 555}.

No recorded warning is distinct from proof of thermal isolation. The JSON report preserves every sampled power/thermal output and load observation. Unclassified or unavailable observations require review.

