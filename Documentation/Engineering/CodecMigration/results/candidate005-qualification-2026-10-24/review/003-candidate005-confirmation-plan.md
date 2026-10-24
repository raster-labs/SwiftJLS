# Candidate005 prospective confirmation — 24 October 2026

Status: method preregistered before candidate005 outputs; source/build pins remain pending final validation receipt and independent root acceptance. Preparation never launches benchmarks. The candidate contains real source changes (atomic lifecycle bookkeeping, compact gradient tables, and the final reviewed parser-budget correction); it is not another same-source candidate004 attempt.

All historical evidence remains: candidate003 47/48, candidate004 45/48 (three unresolved, zero confirmed regressions), both original Apple RSS campaigns, and every interrupted attempt. New results cannot erase those outcomes. This is one fixed confirmation of a distinct final source, not a sequential confidence sequence or a claim of 95% coverage across all adaptively selected historical candidates. No outcome-dependent exclusions, extensions, optional repeats, changed thresholds, or passing-summary selection are permitted.

## Fixed performance scope

- Original `Consumer.swift` SHA-256 `27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34`; five interleaved warmups and five individually timed observations in their original positions. `SWIFTJLS_BENCHMARK_END_TO_END=1`; original public API/main-actor caller boundary and resource profile.
- Short: six 37×23 p12/p16 flat/ramp/noise cases; four operations; candidate005 versus frozen pinned binary `b117c48d…` (source15aa7516) and three-change binary `7f618c0c…` (bee49a2 plus archived patch). Exactly 516 joint rounds, six arm-order strata ×86 rounds, 9,288 processes. Original seed/order/case rotation unchanged. Original analyser copied byte-for-byte: 50,000 complete joint-round bootstrap draws, preserving all five samples, seed20261022. Primary 48-endpoint Bonferroni two-sided family: upper≤1.05 passes; lower>1.05 confirms measured regression; otherwise unresolved. Original24-family and marginal intervals are descriptive only. All48 must pass for complete short-scope acceptance.
- Larger: original15 cases, four balanced paired blocks, candidate005 versus pinned,120 processes,60 pooled operation ratios. Unchanged5+5 and historical encoded-size expectations, including the known +44-byte cases. Preserve per-pair/order summaries, all fidelity checks and size changes. This is the previously authorised representative guard, not the full144-case grid. New source requires this new guard; earlier004 result cannot substitute.

## Fixed RSS scope

Exactly **528 complete four-arm blocks (2,112 processes)**: all24 permutations repeated22 times, shuffled once with seed20261022, each arm132 times per position and264 times per relative order. Labels are frozen62309d3, frozene66f7da, candidate005, and candidate-copy (the identical candidate path/binary, never rebuilt or pooled). Both old baseline binaries are reused exactly:

- 62309d3c59b04c5896d6ea076aae5ce06f5f33e3; binary `64f270f9370b9537b315e08419c50beadb026cc68e4f2812a3cd53a0a9db5257`.
- e66f7da0d663756bae2d1495454d59b028228f7f; binary `71601d9d0b603ba4a4fc69dcff8558e9c428c5cec4023c07d5bafec3f16f2a47`.

Original512×512 p12 noise, c1/n0/i0,5+5, encoded410542bytes. Endpoint remains Consumer `peak_process_rss_bytes` (`getrusage` full-process peak): no allocator subtraction, caller-buffer subtraction, pressure relief, post-release substitution, or narrower phase endpoint.

Reuse the original four directed contrasts: e66/623, candidate/623, candidate/e66, candidate-copy/candidate. Jointly resample whole four-arm blocks, unstratified as originally specified,50,000 draws, seed20261022; two-sided Bonferroni4 intervals at [.00625,.99375]. Chunking only temporary array gathering preserves the RNG matrix/estimator. Candidate passes the finite criterion against both baselines only when each upper≤1.05 **and each ratio of overall observed maxima≤1.05**, with no A/A review flag. This is not a maximum paired-block ratio. Copy the original A/A rule exactly: review when its interval excludes unity **or** its median/max ratio deviates by more than5% (or the explicit interval bounds indicate >5% shift); A/A review blocks acceptance. Four-way intervals are a separate prespecified RSS family, not a joint52-endpoint guarantee. This finite fixture/process experiment cannot establish a universal memory maximum or waive algorithm-workspace accounting.

Planning-only sample rationale: the retained24-block002 candidate-versus-baseline intervals have worst half-width about0.1197. The rough inverse-square-root projection to528 blocks is about0.0255. This heuristic is not a power guarantee: RSS is discrete/bimodal and the unchanged maxima check does not shrink with sample size.528 ensures exact24-order balance and is fixed before new outputs. Old96 Consumer processes took22.66seconds, implying about498seconds for2112 before condition-check overhead; actual duration may vary.

## Host, admission and stopping

Shared host throughout: keep Colima and other shared services running; never suspend/disable TimeChamp. The accepted004 helper retains AC/thermal and named-workload checks and its recognized resident-service exceptions. Its labels such as `quiescent_shared_colima_vm` are legacy guard classifications, **not proof of host/VM idleness**; Dockerstats and cumulative host CPU are different scopes. Unknown/video/background activity remains evidence, not silently filtered away. No newly invented total-CPU threshold.

After all validation/builds finish, request the existing coordinated pause of task-owned heavy work, take a fresh two×10-second preflight, review raw process/full-command/VM/CPU evidence, then root explicitly authorises each sequential campaign. Survivor-process CPU deltas miss processes exiting between samples. Do not run build, bootstrap, audit replay or another campaign concurrently with collection. Retain per-process stdout/stderr, raw5-sample vectors/RSS, schedule, timestamps, source/binary/script/receipt hashes and condition records immediately. Any nonzero process, fidelity/size/schema failure, source change, AC/thermal/guard violation or timeout stops collection and retains incomplete evidence. A stopped run is not resumed or replaced automatically. Methodological disposition of a genuine environment interruption must be recorded independently of outcomes before any new authority. Complete unresolved outcomes remain unresolved; no automatic new campaign follows.

## External interface

Preparation entry point:
`campaign-preparation/prepare-candidate005-campaigns.py --receipt /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/candidate005-001/prepare-and-validate-receipt.json --output /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/campaigns005`

Run with `/Users/pushparaj/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3`. The receipt must contain the final four passing host configurations, all source/test pins, original Consumer identity, and final Benchmark path/hash. Preparation checks the existing baselines, copies unchanged methods, deterministically writes three schedules, and emits `campaign-freeze.json`; root must audit/freeze that result before launch.

Safe non-collection controls after preparation: each runner `--check-only`, short runner `--self-test`, RSS runner `--self-test`, larger runner `--self-test`, and `short516_analyse.py --self-test`. `preflight.py --output <fresh receipt path>` observes the host for20seconds and does not collect benchmarks. Never run the copied `diag72_runner.py` entry point: it supplies only the frozen host functions for this package.

Authorised launch interfaces (fresh directories only; commands do not themselves imply authorisation):

- `short516_runner.py --output campaigns005/runs/short516-001`
- `larger15_runner.py --output campaigns005/runs/larger15-001`
- `rss528_runner.py --output campaigns005/runs/rss528-001`

Each complete run produces `raw.jsonl`, `events.jsonl`, `conditions.jsonl`, `summary.json`, and `complete.json`; interruptions produce `interrupted.json`. Short runs also retain frozen analyser/schedule copies. RSS exact replay after all timing ends: `rss528_analyse.py --raw <rss run>/raw.jsonl --output <fresh replay.json>`. No production edits, builds, real preflight or timing have been performed by this preparation task.
