# Shared-service inspection scope clarification

The frozen helper phrase “outside timed Consumer” means that selected Docker identity inspection is performed by the parent harness, outside the Consumer executable and its instrumented public-API calls. It does **not** guarantee that inspection happens outside every measurement interval.

The larger runner waits with `process.communicate(timeout=1)` and may take a condition snapshot after ten seconds while the Consumer is still running (`larger15_runner.py`, lines416–423). The RSS runner has the same periodic during-process policy. A snapshot can therefore overlap a Consumer warmup or retained observation and can add shared-host CPU, scheduling or I/O work. Recorded `started_utc`, `completed_utc` and `inspection_seconds` retain the inspection interval; they do not establish its exact causal effect on an individual timing sample.

The same existing snapshot and identity-admission policy applies to every producer arm. This does not imply an identical number or placement of overlapping inspections for every process. All observations remain retained under the frozen schedules and acceptance criteria. No idle-host, zero-overhead, process-isolation or per-call subtraction claim is made.

This addendum clarifies wording only. It does not change the frozen helper, collectors, source/binaries, guards, schedules, statistical criteria or running campaign, and does not waive any outcome. The completed short campaign remains bound to its original helper and protocol.
