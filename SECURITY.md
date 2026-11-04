# Security policy and implementation requirements

Status: unreleased native codec with bounded parsing, resource admission and sanitizer/mutation evidence. [Current validation](Documentation/Engineering/CodecMigration/Validation.md) distinguishes tested revisions from open release gates. No stable successor release or vulnerability response-time commitment is claimed.

## Reporting

Use [GitHub private vulnerability reporting](https://github.com/raster-labs/SwiftJLS/security/advisories/new), the channel selected by the owner on 4 November 2026. A later same-day read-only API check confirms `enabled: true`; [the verification record](Documentation/Engineering/ReleasePreparation/results/private-reporting-enabled.json) preserves that result. The earlier disabled state remains in the dated evidence. This task did not change the repository setting or submit a test advisory. Do not post exploitable payloads, credentials or patient information in a public issue. The earlier 12 October failed enable attempt remains recorded in the historical qualification evidence.

Include affected version/commit, platform, a minimal safe reproducer, expected/actual behaviour and impact. Use synthetic data where possible. The current `1.1.0-dev.2` candidate is unreleased; there is no published stable successor version with a support window. The reporting channel is configured; a maintainer must accept and publish the supported-version policy before the first stable release.

## Supported versions

| Version | Current status |
| --- | --- |
| `1.1.0-dev.2` and other development commits | Unreleased; reports investigated case by case, without a supported-release or response-time guarantee. |
| `1.1.0` / `1.1.x` stable | Not published or supported yet. The [prepared support policy](RELEASE.md#prepared-first-stable-support-policy) requires maintainer acceptance before publication. |
| JLSwift predecessor | Separate project and security policy; no change to its support or maintenance follows from this work. |

## Threat model

Treat every compressed image, metadata field, interchange header and caller-supplied descriptor as untrusted. Attackers may attempt out-of-bounds access, integer overflow, decompression bombs, pathological entropy work, deeply nested containers, unbounded tasks/caches, malformed colour profiles, unsafe external references or leakage of previous frame memory. Core codecs do not access the network, spawn reference codecs or interpret embedded code.

Enforce the resource, deadline and ownership rules in the common contracts before allocating and while processing. Check slice indices and offset bases. Bound metadata, frame/component/tile counts and parse depth. Reject unsupported essential features. Do not use assertions/preconditions to validate hostile input. Do not emit success after partial decode or cancellation.

Use synthetic fixtures and sanitised diagnostics. Do not log raw images, patient fields, full filesystem paths or memory addresses by default. Initialise exported padding and prevent pool reuse while readers remain. Use scoped filesystem operations only in the CLI; reject detached input references/URLs in the initial stream profile. Atomic final-output publication and overwrite checks must not become path traversal or symlink vulnerabilities.

## Required verification

Run parser/descriptor mutation tests, bounded fuzzing, address/race checks on supported environments and allocation/cancellation stress. Record and fix crash/hang seeds. Review unsafe bridges and native kernels. Check third-party development tools/dependencies and pin reproducible versions. No unresolved severe memory-safety, data-corruption or input-triggered denial-of-service finding is acceptable at stable release.

Correctness and security gates cannot be waived by a benchmark improvement. See `Documentation/TESTING.md` and `Documentation/PERFORMANCE.md` for evidence requirements.
