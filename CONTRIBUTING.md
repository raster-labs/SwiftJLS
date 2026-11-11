# Contributing

Start with `AGENTS.md` and `IMPLEMENTATION.md`. The native codec, owning-memory paths and Milestone 5 library preparation are implemented (`2.0.1`, tagged `v2.0.1`); [the release record](Documentation/RELEASE-v2.0.1.md) and [the completion audit](Documentation/Engineering/CodecMigration/Completion.md) track the remaining physical-device and downstream consumer gates. Keep pull requests focused and preserve independent package consumption.

Application maintainers and coding agents moving from JLSwift should follow [MIGRATION.md](MIGRATION.md). Update that guide and verify its consumer example whenever public APIs, package products, deployment requirements or advertised capabilities change. Keep application migration advice separate from later library implementation milestones.

Every behavioural change needs relevant unit/regression tests. Parser or ownership changes need the matching security/lifetime checks; hot-path changes need controlled benchmark evidence. Public common API changes require the same contract revision in all four repositories and updated example/conformance tests. Codec-specific exceptions need an explicit reason.

New in-house contributions use the MIT licence with SPDX identifier `MIT` where appropriate (contract 0.11.0). Preserve accurate authorship and provenance. Declare third-party source/fixture/tool origins and licences; no unreviewed code import. Do not add private clinical data or secrets. British English is preferred for documentation.

PR descriptions state the problem, resulting behaviour, contract/source revisions, tests actually run, missing environments, memory/copy implications and measured performance where relevant. Do not copy predecessor success counts as successor evidence. Follow `SECURITY.md` for sensitive reports.
