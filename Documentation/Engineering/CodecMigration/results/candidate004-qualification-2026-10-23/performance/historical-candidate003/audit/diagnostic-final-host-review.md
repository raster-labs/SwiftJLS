# Diagnostic final host/source-guard review

Read-only review; no script/test/build/benchmark execution. Root reports the user has paused other builds/tests. The full-command/VM/simulator guard delta is acceptable for a fresh independently reviewed preflight, subject to the explicit environmental limits below. **The task-store path error was corrected during this review; source review now supports fresh root preflight.**

## Source-guard error — corrected during review

At runner f5a82a7c lines892–898, both `Scripts/Benchmark/TaskStore.swift` in the live repo and `Sources/Benchmark/TaskStore.swift` in the arm snapshot are invented paths. Neither represents the producer's `task_store_sha256`. Root preflight failed on the first before any timing/windows. The actual artifact is the XCBuildData `task-store.msgpack` referenced by the pinned preparation receipt. Validate that receipt first, then hash its exact `task_store_path` and compare with its recorded value and producer d493aa21 pin. Do not create source files or silently relabel compiler data. All other paths inspected in source_guards are the established source/test inventories, Consumer, Package.swift, binaries and preparation receipt/events; no additional invented path found there.

The real task-store file exists and matches `d493aa210299a0b39942c5db5b7bfbbeedfb28e69e99370c0dd69bbb9632a2a5` (read-only hash verification). The subsequent runner `13a1894a68c414bc1b142ad8823b0f5f6712d23371ba64caea00b355c82030db` removes both invented source paths, validates the preparation receipt first, reads its exact task_store_path, and compares its actual hash to both receipt and producer pins. This closes the path defect by source inspection. Root should re-run identity/preflight against this final hash; synthetic tests alone cannot cover filesystem path identities. Preserve the failed root preflight as already recorded.

## Host-guard acceptance scope

Full command matching now covers the rejected Angular/headless-browser workload and common build/test/profiler commands. The actual Virtualization.Framework worker, simulator RuntimeRoot paths, SimMetalHost and active simulator app/test bundles are explicitly inspected. The guard rejects unrecognised/ephemeral containers and additional/non-Colima VMs while retaining an explicit shared-Colima and quiescent-booted-simulator exception. It does not kill unrelated processes. Prior preflight receipts/failures are archived; a new receipt clearly distinguishes automated admission from pending Codex root acceptance.

These exceptions are operating conditions, not proof of zero interference. A known container name/command does not establish that no job runs inside it. The user pause plus fresh endpoint CPU observations and root's actual host review remain necessary. Endpoint CPU deltas omit exited processes and are window-average survivor estimates; the receipt now states this limit. No extra arbitrary CPU gate is requested. A hard-coded PID987 in the descriptive exception note is not an identity proof; use observed inventory when reporting. This wording weakness is nonblocking if the reviewed observed inventory identifies the actual VM.

The analyser remains620005cf with the earlier profile/zero-derived-ratio corrections. The diagnostic schedule remains the accepted1728-process schedule; no method/count change. No unresolved material script defect found in the reviewed corrected revision. Root retains collection authority after fresh independent preflight.

## End hashes

- `diag72_runner.py`: `13a1894a68c414bc1b142ad8823b0f5f6712d23371ba64caea00b355c82030db`
- `diag72_analyse.py`: `620005cf7e973e9d769f10bf68b538e26f0e5bdd25d5df369f3936bf7f686bae`
- `schedules/diag72-4arms-001.json`: `1212ee2f04ba9320f2ba7598836d85d2c7069664a536a9d89b652ba1faaeef52`
