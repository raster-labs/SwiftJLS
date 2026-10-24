# Fixed128-round short confirmation

One predeclared campaign completed:1,536 processes,128 complete paired rounds across six37×23 scalar cases, five warmups and five measured observations per process. The original Consumer, candidate7f618c0c… and pinned predecessor b117c48d… remained unchanged. All132 condition observations showed AC and no recorded thermal/performance warnings.

The original ratio-of-pooled-medians estimand is retained:640 observations per producer per metric. Whole paired rounds were jointly resampled across six cases, four operations, both producers and all five observations;64 reference-first and64 candidate-first round IDs were sampled with replacement for each of50,000 bootstrap draws, seed20261021. Case order was rotated/reversed; producer-first order was consistent across all cases in each round.

Two-sided nominal95% familywise Bonferroni percentile intervals cover the24-metric family, using quantiles1/960 and959/960. The fixed interpretation is upper<=1.05 within the measured gate, lower>1.05 confirmed regression, otherwise unresolved.

Outcome: 14 within the measured gate; 10 unresolved; 0 confirmed regressions. Neither absence of confirmed regression nor the pooled point estimate alone closes the gate.

| Case | Operation | Pooled ratio | Familywise interval | Fixed interpretation |
|---|---|---:|---|---|
| p12-flat | encode | 0.87844 | 0.85304–0.90685 | within_measured_gate |
| p12-flat | decode | 1.04076 | 1.01072–1.06849 | unresolved |
| p12-flat | prepare | 1.00000 | 0.96296–1.02532 | within_measured_gate |
| p12-flat | prepare_encode | 1.01744 | 0.99420–1.03226 | within_measured_gate |
| p12-ramp | encode | 0.84672 | 0.82803–0.86249 | within_measured_gate |
| p12-ramp | decode | 1.00077 | 0.97954–1.01852 | within_measured_gate |
| p12-ramp | prepare | 1.01299 | 0.98701–1.05921 | unresolved |
| p12-ramp | prepare_encode | 0.91988 | 0.90091–0.93692 | within_measured_gate |
| p12-noise | encode | 0.72854 | 0.71617–0.73952 | within_measured_gate |
| p12-noise | decode | 1.03649 | 0.94719–1.13164 | unresolved |
| p12-noise | prepare | 1.03896 | 1.01266–1.06579 | unresolved |
| p12-noise | prepare_encode | 0.81215 | 0.79639–0.82490 | within_measured_gate |
| p16-flat | encode | 0.90212 | 0.87500–0.94056 | within_measured_gate |
| p16-flat | decode | 1.05691 | 1.02695–1.08967 | unresolved |
| p16-flat | prepare | 1.01250 | 0.98750–1.05128 | unresolved |
| p16-flat | prepare_encode | 1.03134 | 1.01127–1.05271 | unresolved |
| p16-ramp | encode | 0.83945 | 0.82060–0.85890 | within_measured_gate |
| p16-ramp | decode | 0.96502 | 0.95150–0.98991 | within_measured_gate |
| p16-ramp | prepare | 1.02564 | 1.00000–1.07895 | unresolved |
| p16-ramp | prepare_encode | 0.93294 | 0.92053–0.94714 | within_measured_gate |
| p16-noise | encode | 0.70621 | 0.69198–0.71999 | within_measured_gate |
| p16-noise | decode | 1.02652 | 0.94498–1.10843 | unresolved |
| p16-noise | prepare | 1.05263 | 1.01282–1.08000 | unresolved |
| p16-noise | prepare_encode | 0.79024 | 0.77617–0.80221 | within_measured_gate |

Both flat decode metrics remain unresolved:12-bit1.04076 [1.01072,1.06849],16-bit1.05691 [1.02695,1.08967]. The other unresolved metrics are12/16noise decode, preparation for12ramp/12noise/16flat/16ramp/16noise, and16flat prepare-plus-encode.

All raw outcomes, marginal intervals, paired round ratios, first-producer groups and eight consecutive16-round temporal groups are retained. Frozen algorithm self-tests passed. Independent post-run verification recomputed all48 pooled medians and3,072 paired metric ratios from raw JSON, checked408 bootstrap ratios against a scalar calculation, and verified all50,000 resamples retained64/64 strata.

These nominal bootstrap intervals rely on exchangeable independent rounds within order strata and finite resample approximation; a single host/session may retain temporal correlation. They are scoped measured evidence, not a universal host/platform guarantee. No observations were dropped, no metric was replaced, no count extension or measurement rerun occurred.

Frozen plan/hash: `plan.json`; schedule: `schedules/short-pinned.json`; analysis and tests: `analyse.py`, `analysis-self-test.json`; source/binary guard: `identity-check.json`; raw/conditions and all analysis: `results/`; independent checks: `results/verification.json`.
