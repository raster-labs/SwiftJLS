# Focused candidate validation

Completed on 21 October 2026 with explicit
`DEVELOPER_DIR=/Library/Developer/CommandLineTools`, Apple Swift 6.4
`swiftlang-6.4.0.34.1`. The isolated snapshot is exact `bee49a2` plus the three
retained patches; production and the earlier combined-only evidence are unchanged.

| Check | Result | Retained record |
| --- | --- | --- |
| Release gradient, descriptor and parser groups | 17 tests in 4 suites passed | `focused-release.json`, `.log`, `.xml` |
| Address Sanitizer gradient group | 3 tests in 1 suite passed | `gradient-asan.json`, `.log`, `.xml` |
| Original Consumer release build | Exit 0 | `benchmark-build.json`, `.log` |
| Source and Consumer identity recheck | Unchanged | `build-identity.json` |

The composed patch SHA-256 is
`7f53b5b238deed2d634e0be889fb2a05ff20e31cea9e60652d3af2057ed3123a`.
The release Benchmark SHA-256 is
`7f618c0cf8fe1c31bee5a36b212c0dc2943e89fd366b4228a966f63d83aa5231`.
The original Consumer SHA-256 remains
`27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34`.
Exact per-file identities, fixture tree and commands are in the JSON records.

The initial materialisation/API mismatch and missing test-plugin build attempt
remain preserved as diagnostics; neither executed a test. The successful test
commands explicitly load the installed `TestingMacros` plugin. ASan address
checking is enabled and leak checking is disabled, as recorded in the commands.

This is focused correctness/build evidence only. No benchmark timing, full-suite
qualification, production promotion or performance acceptance was performed by
this validation driver.
