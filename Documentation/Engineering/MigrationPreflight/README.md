# Migration preparation — 9 October 2026

This is preparation for Milestone 2, not a codec delivery or production cutover.
SwiftJLS still advertises no JPEG-LS encode, decode or inspect capabilities.

## Revisions and scope

- Successor baseline: `91092f78b492e332a7ec200e68b76604088e44fb`.
- Selected predecessor for the next migration baseline: JLSwift
  `15aa75164145414f3d5ffb801401c52d40cc5bcc`. This includes the existing
  contract-layer work and the `0xFF` marker-fill correctness fix.
- Historical inspected predecessor and peeled `v0.9.1` tag:
  `299b9a2e5bfe36ef104a3464a27d6c4c82874cc2`. It remains historical evidence;
  the selected source is not silently substituted into that record.
- Current suite policy and CLI contract: 0.10.0. Other shared documents retain
  their own recorded versions. All seven local contract hashes pass.
- Manifest minimum: Swift 6.2; primary compiler: Swift 6.4; Apple floor: 26.0.
  These follow the policy and manifest, overriding stale OS 27/Swift 6.4-minimum
  statements in the migration guide and agent instructions.

No predecessor implementation or test file has been added to SwiftJLS.
[The inventory](predecessor-inventory.tsv) records source paths, SHA-256 digests
and sizes, not completed migration claims.

## CI precondition and fixes

The [baseline workflow, attempt 2](https://github.com/raster-labs/SwiftJLS/actions/runs/35800202806/attempts/2)
executed on 9 October. The earlier billing lock no longer prevented this run.
The contract hash job, Swift 6.4 Linux jobs and macOS job passed. Three jobs failed:

1. Both Swift 6.2 Linux jobs trapped when the existing re-entrant ownership test
   tried `Mutex.withLockIfAvailable` from the thread already holding the mutex.
   An atomic admission flag now rejects competing and re-entrant calls before
   touching the non-recursive mutex. The flag is released after the state lock,
   on both return and throw. Storage remains checked `Sendable`; no pointer owner
   or unchecked concurrency annotation is introduced.
2. The independent consumer requested dependency identity `SwiftJLS`, although
   its dependency checkout is named `package`. Its product still names
   `SwiftJLS`; its package identity now matches the checkout directory.

Existing re-entrant, lifetime, sealed-reader and overlapping-writer tests remain
active. The concurrent-borrow test now checks abort/reserve rejection too. A new
throwing-borrow regression proves that admission is released and failure cleanup
can invalidate the lease without publishing storage.

The candidate must pass the full CI workflow before any codec source moves,
as required by suite policy revisions 0.8.0 and 0.9.0. A local pass alone does
not satisfy this gate. Candidate CI evidence is attached to the pull request.

## Migration selection and reconciliation

| Source at the selected predecessor | Planned treatment |
| --- | --- |
| `JPEGLSEncoder.swift`, `JPEGLSDecoder.swift` | Adapt the scalar single-component lossless kernels to the successor API |
| `Core/` bitstream, marker, header, preset and context types | Audit and migrate only dependencies required by that scalar profile |
| `Encoder/` regular/run mode and `Decoder/` parser/regular/run mode | Retain predictor and entropy invariants; add checked limits and bounded cancellation |
| `Contract/ContractCodec.swift` | Use as source evidence for the stride-aware access points; do not import its parallel public facade |
| Other `Contract/` types | Keep SwiftJLS's existing API/storage implementation and deliberately omit the duplicate types |
| `Encoder/JPEGLSPixelBuffer.swift` | Keep legacy nested arrays out of the successor hand-off path |
| `PNGSupport.swift`, `TIFFSupport.swift` | Deferred under the existing POL-05 dispositions |
| `Sources/jpeglscli/` | Payload CLI migration is deferred; keep argument-parser outside the core dependency graph |
| `Tests/JPEGLSTests/` | Audit scalar, robustness, marker-fill, precision and shared-layout cases before adaptation |

The first codec profile remains native scalar lossless unsigned greyscale in
16-bit storage, explicitly testing 12 and 16 meaningful bits, odd geometry and
padded rows. Unsupported modes remain explicit failures. Shared-storage
qualification and cross-codec proof are Milestone 3 work.

The selected predecessor contains a synchronous contract facade, not a complete
implementation of the successor contract. Its cancellation checks occur before
the kernel calls; its workspace reports and resource admission need further
review. Its parse helper normalises `Data` indices, so decode slicing must be
reconciled with that normalisation and tested. A wholesale directory copy would
duplicate public types and carry those limitations into the successor.

The predecessor root licence is Apache-2.0 and its NOTICE credits Raster Images
Private Limited. Preserve per-file copyright notices. The pinned manifest still
resolves `swift-argument-parser` for CLI/tests, despite the core target having no
package dependency. The local resolution selected 1.8.2 at
`6a52f3251125d74daf04fcbd5e6f08a75d074382`; do not add it to SwiftJLS's core.
Synthetic fixtures generated by the predecessor are regression material, not an
independent interoperability oracle. Fixture redistribution and oracle versions
must be recorded before importing fixtures; neither is waived by this inventory.

## Executed local evidence and limits

[local-results.json](local-results.json) records commands, exit codes, timing,
toolchain identity and hashes of the changed implementation/test/workflow files.
Workspace paths are normalised to `<workspace>`; no command is claimed to have
run with that literal placeholder. The initial build used `work/caches/`; later
checks used repository-specific cache directories under it. Swift's default
Swift Build engine was used unless the recorded command explicitly says otherwise.

- Baseline `swift build`: exit 0.
- Candidate Debug and Release `swift test`: exit 0; 33 tests in each, zero failures.
- Separate local AddressSanitizer and ThreadSanitizer builds: exit 1 before tests,
  because the selected Command Line Tools environment could not load
  `TestingMacros` in those builds. These are unexecuted sanitizer gates locally.
- The selected predecessor's filtered scalar/robustness test build encountered
  the same macro-plugin problem. An explicitly recorded native-engine retry also
  failed before execution with `no such module Testing`. Neither attempt is a
  passing predecessor baseline.
- All seven shared-document checksums and `git diff --check`: pass.

The change adds one atomic flag per writable owner and an atomic admission/release
pair per storage lifecycle operation. It adds no pixel allocation or hand-off
copy; existing sample/lifetime tests exercise the storage behaviour. No allocator
telemetry, codec throughput or controlled performance measurement was made.

Remaining work includes a passing predecessor regression baseline, independent
JPEG-LS interoperability, explicit resource/cancellation implementation, provenance
review, fuzzing and the later platform/performance gates. The CLI rename required
by 0.10.0 and stale active guidance remain separate recorded cleanup items. This
preparation does not merge a PR, change consumers, archive a predecessor or tag a
release.
