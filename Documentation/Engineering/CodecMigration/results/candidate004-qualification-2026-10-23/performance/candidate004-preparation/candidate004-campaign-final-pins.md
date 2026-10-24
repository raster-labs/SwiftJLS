# Candidate004 final preparation delta

Accepted with no findings. The shared helper changes only the synthetic snapshot key to `live_conditions_observed_only` and adds `admission_status: observed_only_not_preflight_readiness`. Reversing these two text changes reproduces the previously accepted helper hash exactly. Both final runners change only their helper hash pin. All schedules and analysers are unchanged. Seven regenerated synthetic/identity control receipts pass with the new identities; start/end file hashes are stable. No checks were rerun and no timing was started.

Final helper: `41d857d93c6442ad31c446a2ee82ce86bcd3730bf5f3989f5a1e721108e1b5ea`; short runner: `9fa61c411f6c66d0f6553017344b1391928d03045dfe36f5757c878a3471b3af`; larger runner: `8dc2c61bbbe96471fdf3e48f0653bc864605d8732880b924fe3763487b13ad53`. Freeze receipt: `1cae31cfed8c536263531d42e8a92e09354f0ff8051819d933314e9bdfd4fb20`. The adjacent JSON records every final pin.

Preparation is accepted; collection still requires completed validation jobs and a fresh coordinated quiet-window preflight accepted and bound by root. All prior acceptance conditions remain unchanged.
