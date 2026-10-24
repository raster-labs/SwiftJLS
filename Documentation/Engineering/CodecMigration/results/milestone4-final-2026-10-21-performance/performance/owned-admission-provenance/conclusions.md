# Distinct owned-admission candidate measurements

All three predeclared campaigns completed once: 1920 processes; 188 AC observations with no recorded thermal/performance warnings. Source, patch, original Consumer and binary identities passed before and after each campaign. No promotion, count extension, excluded outcomes or automatic waiver.

Ratios are new admission candidate / reference. The direct short comparison uses the previous three-change candidate; both other comparisons use the pinned predecessor. E=encode,D=decode,P=prepare,PE=prepare plus encode.

| Comparison | Case | E | D | P | PE |
|---|---|---:|---:|---:|---:|
| direct-short16 | p12-flat | 0.91864 | 0.93813 | 0.83333 | 0.94949 |
| direct-short16 | p12-ramp | 0.94562 | 0.95884 | 0.90323 | 0.98556 |
| direct-short16 | p12-noise | 0.99742 | 0.95197 | 0.93082 | 1.00903 |
| direct-short16 | p16-flat | 0.92907 | 0.95256 | 0.88485 | 0.95194 |
| direct-short16 | p16-ramp | 0.96488 | 0.97958 | 0.89809 | 0.97340 |
| direct-short16 | p16-noise | 1.01303 | 1.13532 | 0.88050 | 0.98688 |
| pinned-short128 | p12-flat | 0.84740 | 1.03547 | 0.90625 | 0.97971 |
| pinned-short128 | p12-ramp | 0.82996 | 0.99461 | 0.93421 | 0.91190 |
| pinned-short128 | p12-noise | 0.70980 | 1.02663 | 0.94737 | 0.79803 |
| pinned-short128 | p16-flat | 0.85484 | 1.04755 | 0.90000 | 0.99717 |
| pinned-short128 | p16-ramp | 0.80763 | 0.98410 | 0.94156 | 0.92511 |
| pinned-short128 | p16-noise | 0.69508 | 1.07208 | 0.94805 | 0.78799 |
| pinned-deep16 | p12-flat | 0.97213 | 0.97538 | 0.82895 | 0.93354 |
| pinned-deep16 | p12-ramp | 0.85616 | 0.90924 | 0.78378 | 0.83497 |
| pinned-deep16 | p12-noise | 0.76301 | 0.91429 | 0.83099 | 0.75499 |
| pinned-deep16 | p16-flat | 0.98264 | 0.98148 | 0.81579 | 0.94322 |
| pinned-deep16 | p16-ramp | 0.94463 | 0.89650 | 0.86111 | 0.85266 |
| pinned-deep16 | p16-noise | 0.74633 | 0.89202 | 0.84507 | 0.73107 |

The unchanged128-round familywise rule yields 20 within the measured gate, 4 unresolved and 0 confirmed regressions.

| Case | Operation | Pooled ratio | Familywise interval | Classification |
|---|---|---:|---|---|
| p12-flat | encode | 0.84740 | 0.82562–0.88089 | within_measured_gate |
| p12-flat | decode | 1.03547 | 1.01351–1.06906 | unresolved |
| p12-flat | prepare | 0.90625 | 0.87831–0.93671 | within_measured_gate |
| p12-flat | prepare_encode | 0.97971 | 0.96392–0.99853 | within_measured_gate |
| p12-ramp | encode | 0.82996 | 0.80335–0.85925 | within_measured_gate |
| p12-ramp | decode | 0.99461 | 0.97558–1.00929 | within_measured_gate |
| p12-ramp | prepare | 0.93421 | 0.90909–0.97333 | within_measured_gate |
| p12-ramp | prepare_encode | 0.91190 | 0.89538–0.93062 | within_measured_gate |
| p12-noise | encode | 0.70980 | 0.69197–0.73081 | within_measured_gate |
| p12-noise | decode | 1.02663 | 0.93276–1.14643 | unresolved |
| p12-noise | prepare | 0.94737 | 0.91026–0.97368 | within_measured_gate |
| p12-noise | prepare_encode | 0.79803 | 0.78320–0.81562 | within_measured_gate |
| p16-flat | encode | 0.85484 | 0.83121–0.88065 | within_measured_gate |
| p16-flat | decode | 1.04755 | 1.01351–1.07418 | unresolved |
| p16-flat | prepare | 0.90000 | 0.87654–0.93038 | within_measured_gate |
| p16-flat | prepare_encode | 0.99717 | 0.97753–1.01857 | within_measured_gate |
| p16-ramp | encode | 0.80763 | 0.79456–0.83180 | within_measured_gate |
| p16-ramp | decode | 0.98410 | 0.96126–1.00292 | within_measured_gate |
| p16-ramp | prepare | 0.94156 | 0.92208–0.97368 | within_measured_gate |
| p16-ramp | prepare_encode | 0.92511 | 0.91327–0.93501 | within_measured_gate |
| p16-noise | encode | 0.69508 | 0.67941–0.71072 | within_measured_gate |
| p16-noise | decode | 1.07208 | 0.96103–1.15160 | unresolved |
| p16-noise | prepare | 0.94805 | 0.92208–0.97368 | within_measured_gate |
| p16-noise | prepare_encode | 0.78799 | 0.77723–0.79802 | within_measured_gate |

The primary short analysis is byte-identical to the prior frozen method: original pooled-median estimand, seed20261021,50,000 joint whole-paired-round bootstrap resamples,64/64 producer-first strata,24-metric family and Bonferroni tail quantiles1/960 and959/960. The prior dataset is separate and was neither extended nor replaced.

All144 pooled medians and3,840 paired metric ratios were independently recomputed from raw JSON. The primary128 verification also checked408 scalar bootstrap ratios and the full draw digest/stratum balance. All marginal intervals, block/order/temporal spread and raw outcomes remain in `combined-summary.json` and `results/`.

Direct16 and deep16 evidence are distinct contexts and do not replace unresolved primary short metrics. Nominal bootstrap coverage assumes exchangeable independent rounds within strata; temporal correlation within a single host/session and finite bootstrap approximation remain limitations.
