# Final Milestone 4 evidence plan — 21 October 2026

This directory is a fresh checkpoint. The 14 October archive remains historical
and must not be overwritten. Scripts are prepared; preparation is not execution.

## Before timing

The build owner supplies `benchmark-build.json` from actual successful builds,
including the later frozen source commit, exact production source/package file
hashes, pinned predecessor, original consumer hash, binary paths/hashes, explicit
Command Line Tools selection and build-command provenance. A source fingerprint
must bridge a precommit build to the committed tree; assigning a later SHA alone
is insufficient. Preserve failed attempts. Do not build during a timing window.

The original c330 successor binary is preserved at
`work/m4-benchmark/frozen-c330/Benchmark`. The new campaign uses the original
separate-process consumer for both producers and the same default CLT release
build mechanism. The same-process diagnostic is separate historical diagnostic
evidence and is never substituted for the original consumer.

Run the identity check before an authorised exclusive timing window:

```sh
python3 work/m4-final-2026-10-21/run-powered.py --phase full --check-only
python3 work/m4-final-2026-10-21/run-powered.py --phase tiny --check-only
```

## Campaign and analysis

```sh
python3 work/m4-final-2026-10-21/run-powered.py --phase full
python3 work/m4-final-2026-10-21/analyse-powered.py --phase full
python3 work/m4-final-2026-10-21/run-powered.py --phase tiny
python3 work/m4-final-2026-10-21/analyse-powered.py --phase tiny
```

The full campaign retains 24 scalar cases and the owner-selected 39 RGB cases,
four alternating producer blocks, five warmups and five observations per producer
per block. The six scalar 37×23 repeats cover flat/ramp/noise at 12 and 16 bits,
using four alternating blocks, 20,000 warmups and 1,000 observations. Preserve
end-to-end preparation boundaries, full sample verification, all raw timings,
pooled medians/p95/spread, all paired ratios, sizes, and whole-process RSS.

The driver records AC status every two seconds and thermal/load/memory telemetry
approximately every 30 seconds, with before/after samples. A detected loss of AC
or monitoring failure terminates the complete benchmark process group and leaves
an incomplete failed record. This is sampled monitoring, not proof of uninterrupted
electrical or thermal isolation. Interrupted results stay separate and cannot be
silently completed by mixing runs. Output paths must be fresh.

The analysis rejects incomplete grids and mismatched source/consumer/binary
identity. It reports all pooled latency/RSS increases above 5% and encoded-size
increases above 1%, with paired-block evidence and absolute latency deltas.
RSS is not algorithm workspace. Analysis assigns no acceptance or waiver.

Historical original-process tiny outliers remain preserved. The fresh combined-
process c330 diagnostic has below-threshold ratios in that context, but does not
identify an async mechanism or independently waive the original baseline. Current
qualification requires the promoted-source full campaign and all six tiny repeats.

## Final compact archive

After validation and measurements finish, archive into a new
`Documentation/Engineering/CodecMigration/results/milestone4-final-2026-10-21/`
with a sibling manifest JSON. Derive outcomes and declaration counts from actual
records; reject missing mandatory data. Include:

- Frozen source/test trees, package/version hashes, contract hashes and exact
  source-to-build provenance, including the original pinned predecessor.
- Final local debug/release/ASan/TSan logs and XML; actual CLI, independent
  consumer, Apple SDK/simulator/resource and native macOS 26.0 records. Preserve
  unavailable/failed attempts; exact runtime execution is not physical testing.
- Original Consumer.swift, build and runner sources, exact case lists, build
  records, raw full/tiny measurements, all condition/failure records, analysis and
  explicit dispositions. Include the 21 October same-process diagnostic as a
  separately labelled c330 context experiment.
- Current-source workspace measurement records for all 89 operations, their
  reconciled ledgers, classifier controls, measured native descriptor allocations
  and measurement-run provenance. Never relabel an old profile as a new binary
  measurement; current-source workspace evidence is mandatory for this archive.
- A size and SHA256 entry for every compact evidence file; verify the completed
  archive against that manifest. Exclude executables, build trees, VM disks and
  raw large profiler traces; retain compact source, logs, ledgers and provenance.

Physical-device testing remains pending. Milestone 5 remains deferred. The owner
retains GitHub CI verification and merge; archive integrity is not CI acceptance.
