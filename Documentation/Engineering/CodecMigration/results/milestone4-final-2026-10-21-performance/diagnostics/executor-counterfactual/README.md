# Short-regime executor counterfactual — diagnostic only

This snapshot starts from the complete unpromoted short-path candidate (composed
patch `7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a`).
Only the owned `Decoder.decode(_:options:)` signature changes: `@concurrent`
and `async` are removed. Its body remains byte-identical, including cancellation,
input admission and the call into the unchanged scalar/component decode path.
The supplied-destination decode API, encoder, kernels, storage and resource
checks are unchanged. The original Consumer and its package are byte-identical.

The one-line patch, exact inverse check, unchanged body digest, full source/test
inventory and parent binary identity are in `source-identity.json`. Fixture
materialisation is deferred until the exclusive build window; `build.py` then
uses the pinned Git fixture tree, builds the original Consumer once and checks
all samples in each of the six 37×23, 12/16-bit flat/ramp/noise cases. The emitted
single-observation preflight durations are retained but are not performance
evidence. Compiler diagnostics, including the expected no-op `await` warning,
are retained verbatim in `benchmark-build.log`.

This counterfactual deliberately violates the required executor policy. It is
never a permitted production optimisation, source promotion or automatic waiver.
Its removal of an asynchronous boundary can also change ABI, inlining and linked
code layout, so measured differences cannot automatically be labelled pure
executor-switch cost. A separate coordinated runner owns any controlled short
comparisons and preserves all operations and outcomes.
