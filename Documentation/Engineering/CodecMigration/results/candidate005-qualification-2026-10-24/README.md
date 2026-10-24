# Candidate005 qualification evidence

This archive preserves preparation, an interrupted environment-guard attempt, final measurements, software qualification, independent reviews and the authored disposition. Prior archives are immutable. Measurements are identified by exact source and binary receipts, not by the base commit alone.

Raw timing/event JSONL is unchanged and losslessly gzipped. Condition derivatives preserve numeric fields/list positions while removing unrelated process arguments; original hashes are retained. Shared services remained active. The interrupted 468-process attempt is retained separately and never pooled into final results. Physical qualification and milestone5 retain their authored status.

Portable numerical replay (no new measurements):

```sh
python3 tools/replay-performance.py --archive .
python3 memory/replay-workspace.py --archive memory
```

The optional `--bootstrap` argument repeats the frozen 50,000-resample short/RSS analyses and requires NumPy. Historical collection drivers retain original local paths as provenance; they are not advertised as directly portable. Full host tests require the repository fixtures matching the archived source pins; only probe-required fixtures are duplicated here. Binaries, build trees and private VM access files are excluded.
