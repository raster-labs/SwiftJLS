# Unpromoted short-operation candidate

This isolated snapshot combines three reviewed changes on exact source
`bee49a2ad47eae4ea149bdced2043b7a45df3dae`: the singleton descriptor mapping
shortcut, bounded parser bookkeeping, and decoder gradient interval fills.
The earlier combined-only snapshot, binary and observations remain unchanged.

`prepare.py` materialises the pinned source and fixture tree, applies the three
retained patches, and copies the unchanged original benchmark Consumer. The
initial materialiser attempted a tarfile API unavailable in the installed
Python; `prepare-initial.py` and `prepare-initial-failure.txt` retain that failed
attempt, which extracted no source files. The corrected materialiser validates
each pinned archive path and permits only regular files and directories.

`source-identity.json` records every production and test Swift file, package and
version digest, fixture Git tree, patch digests, original Consumer/package
digests and explicit Command Line Tools Swift version. `validate-build.py`
checks those identities before and after focused release tests, focused gradient
Address Sanitizer tests, and the original Consumer release build. It retains
commands, logs, XML and the resulting executable identity. These commands do
not benchmark or promote the candidate. Leak checking is disabled for ASan,
matching the established macOS test-runtime configuration; address checking
remains enabled.

The first focused build omitted explicit loading of the installed CLT
`TestingMacros` plugin and failed before any tests ran. Its command and log are
retained as `initial-focused-release.*`, with the original driver saved as
`validate-build-initial.py`. The corrected test commands explicitly select
`swiftbuild` and load that plugin, as in the established validation procedure;
the benchmark executable retains the original release-build configuration.

The decoder change fills nine adjacent intervals only when `NEAR < T1` and
retains the original branch-table construction otherwise. Equal thresholds
produce valid empty intervals. The largest table remains 131,071 Int elements;
no extra segment array, shared parameter change or encoder change is introduced.
The independent test oracle checks every small ordered threshold triple,
default precision/sample-gradient domains and maximum-table/fallback boundaries.

Controlled performance measurement is a separate step owned by the coordinated
benchmark runner. No performance result or production promotion is implied by
source preparation, compilation or focused correctness tests.
