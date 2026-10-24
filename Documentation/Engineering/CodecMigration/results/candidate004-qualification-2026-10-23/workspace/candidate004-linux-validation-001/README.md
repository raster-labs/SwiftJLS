# Candidate 004 Linux validation preparation

Prepared only; requires explicit parent **TIMING COMPLETE**. No build, profiling or Docker-state mutation has been performed. Candidate003 preparation remains intact and unexecuted.

Receipt SHA256: `4a1b7554778f6f551186f8497d93f599d001d4fe1090eeba6972dcb2436adfed`. Base: `4f6661a4ccec277d02e42b9228c7b574dfbf15cd`. The attached source/test maps and benchmark pins come from the frozen receipt, with the independent accepted source-review receipt hashes retained. Full pre/post source, fixture, probe and classifier verification is reserved for execution admission after timing.

Exact command argument arrays: `workspace-command.json` (89 profiles/267 commands) and `copy-command.json` (20 rows). Equivalent shell scripts are adjacent. Both use the pinned Linux image and read-only candidate004 snapshot; workspace builds private libunwind1.8.3 with the original hash and linkage checks. Fresh output subdirectories are `workspace89/` and `copy-probe20/`.

These are Linux scoped heap/copy checks. Apple RSS, universal peak-workspace total, physical-device and deferred milestone5 boundaries are unchanged.
