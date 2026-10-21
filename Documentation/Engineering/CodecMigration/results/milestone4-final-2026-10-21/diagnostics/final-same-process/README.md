# Current-source same-process diagnostic

Prepared only. Do not build or execute until the coordinator grants an exclusive
window after the current timing controls. Production sources are unchanged.

Exact sources: SwiftJLS `bee49a2ad47eae4ea149bdced2043b7a45df3dae` and
JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`. There is no allowance for a
different documentation HEAD. Working source/package differences and untracked
source files are rejected; documentation-only working edits are immaterial.

The existing same-process harness is unchanged except that its input guard also
admits ramp and noise. All six scalar 37×23 cases (12/16 bits × flat/ramp/noise)
use four processes each, 20,000 warmups and 1,000 retained observations per
producer per process. Producers alternate first position at each observation;
each block reverses its initial position. Original nonisolated async public
wrappers, sample verification and timer boundaries remain intact. Both own and
cross decodes verify all samples before timing. No CodecBudget bypass exists.

Run in order, only when authorised:

```sh
python3 build.py
python3 preflight.py
python3 compare.py --check-only
python3 compare.py
```

Build uses explicit Command Line Tools and `swift build -c release --jobs 4`.
`build.json` will record exact source/control-file hashes, toolchain, command,
exit status, log hash, linkage and fresh binary hash. `results/` retains command
outputs/exits, all observations, pre/post power/thermal/load observations,
identity checks and six-case summaries. `analyze.py results` can regenerate the
summary without executing codecs. Outputs are created fresh, never overwritten
by build or timing. Correctness-preflight durations are incidental and excluded
from performance evidence.

This changes process layout and allocator/cache interaction by linking both
libraries and keeping both input images alive. Combined RSS is not attributable
workspace. Results supplement the separate-process campaign and do not replace
it or automatically close any performance gate.
