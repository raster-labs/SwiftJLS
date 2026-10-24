# Candidate004 Apple platform qualification

The frozen candidate004 passed four simulator SDK library/consumer builds and the Watch arm64_32 module compile, all targeting26.0. Actual SDK versions were iOS27.1 and tvOS/visionOS/watchOS27.0. Five exact26.0 simulator consumers passed (iPhone, iPad, tvOS, visionOS and watchOS); four non-Watch simulator resource workloads each passed32 frames with expected owned/supplied allocation and copy reports.

Native arm64 execution in the existing hardware-virtualised macOS26.0 build25A354 guest passed152 tests in each of debug, release, ASan and TSan. Source contains27 named suites; XML has28 classnames because top-level tests have their own classname. The four already-tested host bundles were reused with distinct copied executable hashes; host tests and CLI checks were not repeated. Native runtime/resource consumers and73 CLI payload checks passed.

The first guest attempt failed the CLI process gate before checks because the minimal payload omitted Scripts/install-cli.sh. ManPages/swiftjls-cli.1 was present. Original native-results, payload manifest, logs and driver receipts are preserved. A separate CLI-only payload added the unchanged installer, verified against base/live/snapshot bytes and the contemporaneous host023 process report; its unchanged CLI binary passed103 process checks. No unit, resource or payload checks were rerun for this repair.

The VM was stopped after both attempts. All simulator states were restored, including the preexisting booted iPhone. No source or fixture was modified. The platform source map is explicitly candidate004 with no new commit attribution. [platform-results.json](platform-results.json) binds exact source, bundle, output and receipt hashes; [pins.json](pins.json) records the full input map. Scripts and exact command logs are retained here. The runtime driver’s transient assertion edit/restoration and independent final-marker audit are retained in runtime-final-marker-review.json.

This result does not close physical-device qualification, performance acceptance, universal workspace accounting or milestone5.
