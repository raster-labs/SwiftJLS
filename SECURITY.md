# Security policy and implementation requirements

Status: stable release `2.0.1` (`v2.0.1`) of the native codec with bounded parsing, resource admission and sanitizer/mutation evidence. [Current validation](Documentation/Engineering/CodecMigration/Validation.md), [RELEASE-v2.0.1.md](Documentation/RELEASE-v2.0.1.md) and [RELEASE-v2.0.0.md](Documentation/RELEASE-v2.0.0.md) distinguish tested revisions from open physical-device gates. No fixed vulnerability response-time deadline is promised.

## Reporting

Use [GitHub private vulnerability reporting](https://github.com/raster-labs/SwiftJLS/security/advisories/new), the channel selected by the owner on 4 November 2026 and verified enabled (`enabled: true`; see [the verification record](Documentation/Engineering/ReleasePreparation/results/private-reporting-enabled.json)). The earlier disabled state remains in the dated evidence. Do not post exploitable payloads, credentials or patient information in a public issue. The earlier 12 October failed enable attempt remains recorded in the historical qualification evidence.

Include affected version/commit, platform, a minimal safe reproducer, expected/actual behaviour and impact. Use synthetic data where possible. Keep the report private while maintainers reproduce the issue and prepare a correction.

## Supported versions

| Version | Current status |
| --- | --- |
| `2.0.x` (latest: `2.0.1`) | Supported for security fixes; reporters on earlier `2.0.x` patches should reproduce against the latest patch when safe. |
| Current development `main` and snapshots | Investigated case by case; corrections target `main` and the active line without a separate backport guarantee. |
| JLSwift predecessor | Separate project and security policy; no change to its support or maintenance follows from this work. |

## Threat model

Treat every compressed image, metadata field, interchange header and caller-supplied descriptor as untrusted. Attackers may attempt out-of-bounds access, integer overflow, decompression bombs, pathological entropy work, deeply nested containers, unbounded tasks/caches, malformed colour profiles, unsafe external references or leakage of previous frame memory. Core codecs do not access the network, spawn reference codecs or interpret embedded code.

Enforce the resource, deadline and ownership rules in the common contracts before allocating and while processing. Check slice indices and offset bases. Bound metadata, frame/component/tile counts and parse depth. Reject unsupported essential features. Do not use assertions/preconditions to validate hostile input. Do not emit success after partial decode or cancellation.

Use synthetic fixtures and sanitised diagnostics. Do not log raw images, patient fields, full filesystem paths or memory addresses by default. Initialise exported padding and prevent pool reuse while readers remain. Use scoped filesystem operations only in the CLI; reject detached input references/URLs in the initial stream profile. Atomic final-output publication and overwrite checks must not become path traversal or symlink vulnerabilities.

## Required verification

Run parser/descriptor mutation tests, bounded fuzzing, address/race checks on supported environments and allocation/cancellation stress. Record and fix crash/hang seeds. Review unsafe bridges and native kernels. Check third-party development tools/dependencies and pin reproducible versions. No unresolved severe memory-safety, data-corruption or input-triggered denial-of-service finding is acceptable at stable release.

Correctness and security gates cannot be waived by a benchmark improvement. See `Documentation/TESTING.md` and `Documentation/PERFORMANCE.md` for evidence requirements.
