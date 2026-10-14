# Final performance observations

Source: `c330b731e250d6b4c054c1c6a91fa9894e32a8c3`. No acceptance decisions or waivers are assigned.

The main campaign and deep-warm diagnostic remain separate. RSS includes the entire process and is not algorithm-workspace accounting.

## scalar

Lossless scalar public API. Owned decode, release without sanitizers. Four alternating process blocks, each with 5 warmups and 5 timed iterations. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.

| Case | Operation | Predecessor µs | Successor µs | Delta µs | Pooled ratio | Four paired ratios |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 37×23 p16 flat c1 NEAR0 i0 | decode | 15.500 | 18.125 | +2.625 | 1.1694 | 1.0804, 1.1280, 1.1212, 1.2642 |
| 37×23 p16 noise c1 NEAR0 i0 | decode | 33.208 | 35.104 | +1.896 | 1.0571 | 0.8946, 0.9862, 0.9745, 1.0584 |

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
| 512×512 p12 noise c3 NEAR3 i2 | decode | 29533.521 | 31059.979 | +1526.458 | 1.0517 | 1.0553, 1.0398, 1.0680, 1.0501 |
| 512×512 p12 ramp c3 NEAR0 i2 | decode | 12347.875 | 13466.437 | +1118.562 | 1.0906 | 1.1102, 1.0808, 1.1461, 1.0799 |
| 512×512 p12 ramp c3 NEAR3 i2 | decode | 11943.167 | 12654.167 | +711.000 | 1.0595 | 1.0607, 1.0524, 1.0306, 1.1798 |

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

## final-flat-deep-warm

Lossless scalar public API. Owned decode, release without sanitizers. Four alternating process blocks, each with 20000 warmups and 1000 timed iterations; small-image steady-state repeat. Initial sample verification outside timing. Host is a developer workstation; no claim of isolated thermal/power control.

| Case | Operation | Predecessor µs | Successor µs | Delta µs | Pooled ratio | Four paired ratios |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| 37×23 p12 flat c1 NEAR0 i0 | encode | 10.667 | 11.500 | +0.833 | 1.0781 | 1.1605, 1.0820, 1.0000, 1.3062 |
| 37×23 p12 flat c1 NEAR0 i0 | decode | 12.625 | 13.792 | +1.167 | 1.0924 | 1.1593, 1.0714, 1.0312, 1.1575 |
| 37×23 p16 flat c1 NEAR0 i0 | encode | 8.875 | 11.625 | +2.750 | 1.3099 | 1.3667, 1.2991, 1.3005, 1.2694 |
| 37×23 p16 flat c1 NEAR0 i0 | decode | 11.979 | 13.750 | +1.771 | 1.1478 | 1.2731, 1.1603, 1.1459, 1.1081 |

### Encoded size above 1.01

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

### Whole-process peak RSS above 1.05

| Case | Predecessor bytes | Successor bytes | Ratio |
| --- | ---: | ---: | ---: |

No observations exceed this reporting threshold.

## Recorded conditions

Power observations: {"ac": 45}. Thermal observations: {"no_recorded_warning": 45}.

No recorded warning is distinct from proof of thermal isolation. The JSON report preserves every sampled power/thermal output and load observation. Unclassified or unavailable observations require review.

