# Unpromoted native sample-writer candidate

This candidate is not production and was not performance-tested. Production remains `c330b731e250d6b4c054c1c6a91fa9894e32a8c3`. The explicit CLT release consumer built, all 110 release test declarations passed, and eight focused component/native declarations passed in release and ASan, with zero failures/skips.

AC power was present before the build but changed to battery before benchmark admission. The power guard rejected the timing launch; no benchmark process or candidate timing observation ran. `timing-admission.json` preserves the battery observation. `timed-binaries.json` contains preparatory identity hashes only, not executed timing evidence.

`candidate.patch` and `provenance.json` identify the separate source copy and two new regressions. The first failed compilation omitted an extracted helper's reader parameter; its original patch, provenance and compiler log are preserved in `attempt1-compile-failure/`. The corrected build/test commands and results are separate. The candidate adds one bounded native-writer descriptor array of at most four elements and cannot be promoted without controlled timing and final source-dependent qualification/accounting.

Only compact source patches, reproduction scripts/manifests, test XML/logs and admission evidence are retained here. No binary, full source tree, build tree or timing output is archived. Reproduce from the pinned c330 source plus `candidate.patch`; the copied consumer is identical to the production benchmark consumer. Full fixtures remain identified by the original Tests Git tree rather than copied into this diagnostic.
