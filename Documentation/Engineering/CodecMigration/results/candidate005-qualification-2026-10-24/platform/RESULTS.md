# Candidate005 Apple qualification

The frozen candidate005 source passed four simulator SDK library/consumer builds, watch arm64_32 compilation, five exact OS 26.0 simulator runtime consumers, and four non-Watch resource workloads of 32 frames each. SDK 27.x compilation targets 26.0; actual runtime execution separately uses 26.0.

The existing hardware-virtualised arm64 macOS 26.0 guest executed 157 tests in each of release, debug, ASan and TSan, with 28 named source suites and 29 xUnit classnames (including top-level tests). All tests passed without failures, errors or skips. The runtime consumer, four resource rows / 32 frames, 73 payload CLI cases and 103 process CLI checks also passed. Guest bundle and CLI hashes match the accepted host products. Host test/CLI validation was reused rather than rerun.

`platform-results.json` reconciles the raw receipts and exact source/binary identities. `summarise-platform.py` independently checks counts, exit codes, success markers, hashes and restored simulator/VM state. The source receipt is 87bda184…; the 39 production files and 32 test Swift files (including fixture generators) remained unchanged.

The first SDK-driver attempt rejected a stale 38-file assertion before invoking any compiler/runtime; its records are retained in `apple-attempt-1`. `driver-correction-001.json` binds the correction to the pinned inventory count. Before native packaging, `driver-correction-002.json` records a variable rename preserving the 157-test assertion. No codec source changed, and no native execution failed.

The VM began and ended stopped. Every simulator started for these checks was shut down afterward; the root-paused iPhone 17 Pro remains shut down until all controlled timing completes. Shared services were untouched.

Publication must exclude `vm-ssh.exp`, `known_hosts`, `native-driver-commands.private.json`, keys/configs, VM files, native payload binaries/frameworks and build trees. `privacy-review.json` records the public command-log derivative: expect echoed a guest username sharing a private authentication literal, so the public copy redacts it while the raw record is retained privately. No credential literal remains in the 37 reviewed public native files.

These checks do not establish physical-device qualification, performance acceptance, a universal workspace peak, or milestone 5 completion.
