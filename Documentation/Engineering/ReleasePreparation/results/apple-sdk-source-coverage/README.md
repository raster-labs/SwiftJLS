# Complete Apple SDK source selection — 4 November 2026

The direct compiler commands in three workflows selected 28 Swift files from the
root and JPEG-LS directories, omitting all 11 files under `Sources/SwiftJLS/Qualified`.
They now recursively select all 39 current production Swift sources and typecheck
an imported `QualifiedMonochromeDecoder` client after compiling the library.

Changed workflows: `contract.yml` visionOS SDK fallback, `apple-runtime.yml`
visionOS simulator fallback, and `watch-device.yml` arm64_32 device-SDK compilation.
No production source, public API, package manifest or fixture changed. Source SHA-256
identities at base HEAD `53cea07be57fb030451a87bead9a3c3c0e863f04` are in `source.json`;
`report.json` confirms those source bytes remain unchanged after verification.

## Executed checks

The host compiler is Apple Swift 6.4.2 / Xcode 27.2. The installed visionOS and
watchOS SDKs are 27.2; both commands explicitly target the 26.0 deployment floor.

- Old 28-file visionOS compile/link: exit 0.
- Imported qualified client against that old module: expected exit 1, with
  `module 'SwiftJLS' has no member named 'QualifiedMonochromeDecoder'`.
- Complete 39-file visionOS compile/link and qualified client typecheck: exit 0.
- Complete 39-file arm64_32 Watch device-SDK compile/link and client typecheck: exit 0.
- The exact stdin client form used by CI also passes for both target modules.
- Recursive shell source discovery matches the complete source inventory.
- All three workflows parse with Ruby Psych, their affected shell blocks pass
  `bash -n`, and `git diff --check` passes.

`report.json` records all 14 argument lists, exit codes and durations (13 exit 0,
one expected negative-control exit 1). Each command has separate stdout/stderr logs.
`before/`, `after/`, `workflow-diff.patch`, `workflow-validation.json` and
`shell-blocks.json` retain the workflow inputs and structural checks. `verify.py`
is the explicit reproducer; it needs a fresh evidence directory for its build outputs.

This evidence proves SDK compilation/linking and client API visibility only. It
does not execute a simulator or a physical Watch/Vision device, qualify runtime
resource limits, or close physical-device release gates. The next hosted workflow
runs remain separately required after the CI change.
