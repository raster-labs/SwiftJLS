# Candidate005 Apple platform validation — frozen, awaiting release

Prepared externally from accepted candidate004 scripts and now bound to the frozen candidate005 root receipt. No platform build, simulator or VM action has run. Source authority is the exact root file inventory: 39 production Swift files, 32 test Swift files, 157 declarations, 28 named suites and 29 XML classname groups. The current host four-mode XML and CLI 73/103 receipts are bound; the CLI manual is supplemented from its separate current source-pins receipt. No standalone source-patch identity or synthetic commit is assigned.

Run only after root explicitly releases post-timing validation, serially:

```sh
SWIFTJLS_PLATFORM_VALIDATION_RELEASE=candidate005 python3 /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/platform-candidate005/run-apple.py
SWIFTJLS_PLATFORM_VALIDATION_RELEASE=candidate005 python3 /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/platform-candidate005/prepare-native.py
SWIFTJLS_PLATFORM_VALIDATION_RELEASE=candidate005 python3 /Users/pushparaj/projects/SwiftJLS-audit/m4-20261024/platform-candidate005/native-driver.py
```

Scope: four SDKs and Watch arm64_32 compilation; five exact 26.0 simulator consumers; four non-Watch 32-frame resource workloads; current native consumers; exact macOS 26.0 guest tests/consumer/resource/CLI gates. Native preparation reuses the accepted current host test bundles and CLI; it does not rerun host tests or rebuild independent oracles. Both ManPages/swiftjls-cli.1 and Scripts/install-cli.sh are required in the payload. All first failures remain retained; output directories must be fresh.

The prior private Tart executable/home and m4-macos26 VM are reused only after checking that the VM is stopped. Drivers capture simulator states, shut down only devices they booted, and stop only their own VM in finally. Availability has deliberately not been queried during timing preparation. Credentials are outside any publication inventory. Physical-device testing is excluded.

Identity/readiness: pins.json, qualification-inputs.json and frozen-preparation.json. Driver mapping now consumes root receipt fields swiftjls_file_sha256/test_file_sha256/declaration_counts_from_source and validation[].tests. No unavailable prerequisite is asserted from stale runtime state; current tool/runtime/VM admission will be checked after release.
