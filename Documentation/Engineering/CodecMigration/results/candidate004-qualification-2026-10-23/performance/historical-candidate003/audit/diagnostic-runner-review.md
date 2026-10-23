# Diagnostic runner review — 23 October 2026

**Not yet collection-ready.** Read-only code/identity audit; no runner, analyser, benchmark, build or synthetic-control execution. The scripts remained stable over this review; generated schedule and preparation/host-readiness receipts are still required. Antigravity may continue editing; bind approval to its later final hashes.

## Readiness blocker

Runner `conditions`/`admit_conditions` at lines202–236 logs `ps` CPU and checks only AC power and thermal/performance warnings. It neither requires the accepted plan's two bounded10-second instantaneous readiness inventories/reviewed receipt nor stops when identified interfering work returns. This repeats the specific weakness in045/052: an active host can be admitted as long as power/thermal pass. Implement or explicitly bind an external reviewed readiness receipt plus its predeclared named-workload recurrence checks before collection. Do not invent a CPU percentage retrospectively, kill unrelated processes or silently filter contaminated rows. Current source has no such external gate argument/binding.

No generated schedule existed at initial inventory (and the end status is recorded in companion JSON). Complete deterministic preparation, identity-only and synthetic controls, retain their receipts, then freeze runner/analyser/schedule and host admission before collection. Missing preparation is pending work, not a defect in schedule generation.

## Accepted structure and provenance

- Fixed72 rounds x6cases x4arms=1728processes; all24 permutations x3, seed2026102301; rotation/reversal and18-per-position/36-per-pair assertions match the plan. Generation and analyser use the same order algorithm. No adaptive sampling/retry/filter path.
- Exact old three-change7f618, factoryb4d9a, identical factory-copy A/A, candidate003bd1719 pins; 38-file production and31-file test constants exactly equal prepare receipt773497da. Live/snapshot comparison guards reject added/missing/changed Swift files. Consumer27e4ca75 and packageb8c00c41 match receipt. Binary/receipt/event hashes guarded at start/end. Frozen003 identities were independently checked in `diagnostic-provisional-identity.json`.
- Commands preserve37x23, fixed12/16bits/patterns,5warmups/5observations, END_TO_END1 and original caller/operation order. Export/import environment overrides are removed. Frozen Consumer verifies samples before timing, exact emitted bytes after each encode, and runner validates complete geometry/fidelity/resource-profile/size fields and all finite positive observation arrays.
- Fresh output required. Every completed process retains raw stdout/stderr/exit immediately with fsync before validation; parsed rows are also fsynced. All previous events remain on failure; a running owned subprocess is terminated in its own process group and partial output is retained in interrupted.json. No unrelated process is killed. Source/script drift or failed sample/size assertions prevent completion.
- Runner/schedule/analyser copies are frozen before timing, hashes checked pre/post analysis; measurement-complete is separate from complete. Analysis remains descriptive, no bootstrap/qualification claim.

## Nonblocking hardening observations

The analyser's missing raw-profile validation is already enforced by runner lines555–566, so it is not a collection hole when this exact runner is used. Adding replay checks is still useful and was already requested. Its optional fresh_encode still permits zero then divides by reference medians; guard these derived ratios as unavailable while preserving primary observations/deltas (prior report). This is robustness for degenerate timer subtraction, not evidence that actual samples will have zero durations. Two extra contrasts/fresh_encode are explicitly descriptive and do not change later48-family inference.

The declared task-store hash is carried in the producer receipt but not re-hashed by source_guards; the file and receipt were independently verified. With binaries frozen, this is optional provenance hardening rather than a timing-validity blocker. The campaign does not need repeated compiler inspection or more source tests to resolve this runner review.

## Reviewed hashes

- `diag72_runner.py`: `f690e457efa60bb6ca8ad6c49747e2271b961153ddc994a4c438043d78fa52cc`
- `diag72_analyse.py`: `b7a4249b3d518e70583e6a98adc4742b8a64b6b1c5d102b23707bc96d2bd20c9`
