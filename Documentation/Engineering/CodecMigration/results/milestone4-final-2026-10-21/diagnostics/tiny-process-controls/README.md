# Tiny process and binary controls

Prepared only; execution requires the parent timing-window approval. This diagnostic never builds, edits production, or marks performance accepted.

Run from the repository after all current timing finishes:

```sh
python3 work/m4-final-2026-10-21/diagnostics/tiny-process-controls/run.py --output work/m4-final-2026-10-21/diagnostics/tiny-process-controls/results-1
```

The default sequence is canonical/isolated, canonical/canonical, then pinned/pinned. Each compares 37×23 flat 12/16-bit cases with four alternating process pairs, 20,000 warmups and 1,000 measured observations. All four operation timings are retained. Ratios are explicitly right/left; each row identifies the actual producer and frozen SHA-256. The self-controls deliberately run the same binary in separate processes. New output paths are mandatory; AC is required and checked every ten seconds and at control boundaries. Binary hashes are checked before and after execution.

`build-forensics.json` records identical production/consumer text, fresh canonical objects, matching source/object ordering, and the actual compiler commands extracted from saved SwiftBuild task records. Both use CLT Swift 6.4, CLT macOS 27 SDK, macOS 26 targets, `-O` and whole-module optimisation. Package identities differ; the consumer also differs in testing-plugin loading syntax. The candidate build-request mentions an Xcode SDK, but actual compiler arguments and dependencies use CLT. No cause for the latency difference is established.

These controls measure process repeatability and whether a difference follows the binary. They cannot silently waive earlier regressions or replace final-source primary timings.
