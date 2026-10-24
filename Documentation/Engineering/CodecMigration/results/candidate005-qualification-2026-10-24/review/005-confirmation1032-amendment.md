# Fixed candidate005 confirmation: pre-data amendment

Ready for root review and fresh preflight. Root explicitly confirmed that no candidate005 benchmark runner had launched; only the20-second host preflight had run. The old `campaigns005`516-round package remains unchanged and unexecuted. This is a prospective replacement, not an optional extension of collected observations.

New package: `/Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/campaigns005-confirmation`.

- Fixed1,032 joint short rounds, six order strata×172,18,576 processes,5,160 observations per case/operation/arm. Each arm344 times in each position; each relative order516 times. Original six cases, all four operations, three frozen binaries, public API boundary, five warmups/five individual observation positions,48-endpoint family,5% threshold,50,000 resamples and seed20261022 remain unchanged. Twelve descriptive temporal groups now contain86 rounds each.
- Planning rationale uses historical004 only: previous decode interval half-width≈0.067, projected≈0.047 after doubling independent rounds. This is a heuristic with no guaranteed power/coverage improvement under shared-host temporal correlation. Candidate005 outputs were unavailable when the count changed.
- Larger15 and RSS528 runners/analyser/metrics/guards remain byte-identical; larger deterministic schedule changes only its package-local original-plan pathname. RSS schedule is byte-identical. Source/binary identity JSON is byte-identical; candidate005 binary remains349a14b524218fde633cd415e9972fdcdd7062601ba8578eb71380383b81c177.
- Short runner/analyser synthetic self-tests pass. An independent full18,576-record synthetic schema control exercises all48 endpoints and verifies1,032 rounds,5,160 samples,172-round permutation groups,516-round relative-order groups and12×86 temporal groups. That schema-only control uses seven draws in memory; the unchanged production default remains50,000. Numeric AST comparison allows only sample-count-derived replacements and verifies unchanged statistical decision constants. Larger/RSS identity-only controls pass. No benchmark/live preflight was run by the amendment task.

Final pins:

| Artifact | SHA-256 |
| --- | --- |
| campaign-freeze.json | 71487cb4d5272ef0791e04aeeada506ec94ade2fa244f3ec2791539674b0a948 |
| short1032_runner.py | ff9c6a39df23aab13a2d22b697b29f87f12cc6a71aeeadbe541d22ff0a952197 |
| short1032_analyse.py | af066d2b3ade7595a46d100b82db1871242de742fbb27cc711e75571ce90ee41 |
| schedules/short1032-3arms-005.json | 9a33492bb539f7cfc921a9c137b56bb9e5e7c2db21cfaba84d8b46985b997ab9 |
| schedules/larger15-guard-005.json | 2917a3271166bce6e716c3d44a1e30a37ebdbb6da9adbb531086b067b545a89b |
| schedules/rss528-4arms-005.json | c5fda4b42f75d9942d50eac17e20a6ce8f1c3d4ffa4b468b9fecb35df9b2c207 |

Use the established NumPy Python executable. After root reviews this package and fresh `preflight.py --output <fresh absolute receipt>`, authorised sequential launch interfaces are:

1. `short1032_runner.py --output /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/campaigns005-confirmation/runs/short1032-001`
2. `larger15_runner.py --output /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/campaigns005-confirmation/runs/larger15-001`
3. `rss528_runner.py --output /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/campaigns005-confirmation/runs/rss528-001`

Shared services remain running; automated guard status does not prove host idleness. Fixed count and stopping rules from plan003 remain: no interim outcome-dependent decisions, exclusions, further extension or automatic repeat. Source/build/receipt changes stop collection. Every complete/incomplete prior campaign and the old unexecuted516 preparation stays preserved. Detailed controls are in `005-confirmation1032-controls.json`; source audit inputs are bound by package freeze and `protocol-amendment.json`.
