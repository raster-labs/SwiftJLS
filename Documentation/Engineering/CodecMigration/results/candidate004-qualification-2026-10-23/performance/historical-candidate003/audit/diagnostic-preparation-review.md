# Diagnostic preparation review — provisional

Read-only inspection of candidate003 and `diag72_analyse.py`; no script execution, synthetic test, build, benchmark or repository edit. Runner/schedule were absent at the one initial inventory; no collection-readiness decision is possible yet. No polling performed.

Reviewed analyser SHA (unchanged start/end): `b7a4249b3d518e70583e6a98adc4742b8a64b6b1c5d102b23707bc96d2bd20c9`.

Accepted by source inspection: 72 rounds x 6 cases x 4 arms, all24 permutations exactly3 times, seed2026102301, rotated/reversed case order, 18 occurrences per arm-position, 36/36 pair order, five warmups/five observations, all360 observations per arm/case/operation used in pooled medians, per-round paired/order/permutation/time spread, and explicitly descriptive output with no confidence interval or acceptance claim. Two extra contrasts and per-observation derived fresh_encode are descriptive extensions; they do not replace the four primary operation cells or the later48-family gate.

Two narrow observations for the preparation gate:

1. `verify_schedule` (85–141) checks IDs/order but not the actual fixed case geometry/settings; `compute_summary` (291–306) checks labels, size, counts and hash but never compares raw width/height/bits/pattern/components/near/interleave to canonical cases. Thus different-profile records with the same case IDs could be summarised under these case labels. The final runner may provide this guard, but it was not available to verify; preferably make replay independently reject wrong profiles as the frozen516 analyser does.
2. `fresh_encode` permits zero differences (318), then performs unconditional divisions for pooled, paired and subgroup ratios (349,356,370,382,395). A zero reference median can abort the entire summary even when all four primary operation arrays are valid. Because this is optional derived timing, retain raw zeros/deltas and report affected ratios unavailable; do not filter records or replace zero with an epsilon. Actual current microsecond timings are not asserted to trigger it.

Candidate provenance: receipt `773497da52574028720c492695a4f09a550323ace57ed95c6d9ff9db280eca97`; candidate Benchmark `bd171975e50f6b3557df7b5fda39ce431f8b4098ee163f40b2db1ca65fa142ad`. All38 production source files exactly match across live repo, frozen full repo and candidate arm. Four checked binary files, all patch hashes, Package.swift, unchanged ordinary Consumer, build-event file and compiler task-store match receipt pins. Factory and A/A binary hashes are identical `b4d9a137...`. Fourteen preparation events are retained. Identity result: `diagnostic-provisional-identity.json` (zero mismatches). This is identity verification, not an additional test execution or source semantic acceptance.

Next review waits for the frozen runner, generated schedule and preflight receipts to check condition/interference admission, exact command/fidelity mapping, partial-evidence retention, immutable start/end guards and stopping behaviour. Collection remains unauthorised by this review.
