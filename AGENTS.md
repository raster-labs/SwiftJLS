# Coding-agent instructions

Applies to Claude, Codex and other coding agents working in this repository.

## Start here

Current owner-approved baseline: suite policy 0.10.0, Swift tools 6.2 minimum, primary Swift 6.4, Apple OS 26.0 and the native codec/CLI. Contract 0.5.0 reversed the 0.4.0 raise to OS 27; the OS 27 records under Documentation/Engineering/OS27CLI are superseded history, not the current baseline.

For the compiler upgrade, read the [Swift 6.4 manifesto](Documentation/Engineering/Swift64/Swift_6.4_Upgrade_Manifesto_v1.0.0.md), [suite supplement](Documentation/Engineering/Swift64/Swift_Image_Compression_Suite_Swift_6.4_Supplement_v1.0.0.md), then the [historical upgrade record and feature register](Documentation/Engineering/Swift64/README.md). Preserve the supplied files byte-for-byte. The current suite policy governs platform/toolchain requirements; each shared document retains its own recorded revision. Historical evidence is not rewritten.

Read `README.md`, `HISTORY.md`, this file and `IMPLEMENTATION.md`, then all seven common contract documents in `Documentation/`. Read the repository-specific `TRANSCODING.md` when present before work affecting transcoding. `CLAUDE.md` points here and is not a separate policy. Follow the precedence in `Documentation/SUITE_POLICY.md`.

For application dependency/API migration from JLSwift, read [MIGRATION.md](MIGRATION.md). Distinguish application integration from implementing this library's codec algorithms: a consumer migration does not authorise later codec milestones. Preserve the guide's implemented/planned distinction and update its mappings and acceptance gates when public behaviour changes.

This repository began with documentation only. Reading its instructions does not by itself authorise codec migration. When the owner assigns an implementation task, execute only that milestone. The original foundation contained no package or source. Milestones 1–3 have implementation and scoped validation evidence; feature/release qualification remains incomplete. Read [the current completion audit](Documentation/Engineering/CodecMigration/Completion.md) before claiming parity or completion. Documentation/MILESTONE1.md is historical feasibility evidence. Do not report a plan or an older-revision result as current implementation proof.

## Required working method

1. Confirm the task, target repository, pinned predecessor revision and contract version. Inspect existing working changes before editing. Work on an isolated feature branch; preserve unrelated work.
2. Inventory the relevant predecessor paths, tests, capability coverage, external material and failure cases. Source at the pinned SHA is evidence; stale README claims are not implementation proof. Read scoped predecessor guidance for migrated files and reconcile it with the new contract.
3. Establish the relevant predecessor baseline and record failures/skips. Add meaningful tests for the new contract before claiming migration success. For contract feasibility, compile an isolated ownership/adapter experiment before moving large codec subsystems.
4. Implement the smallest complete assigned milestone. Maintain the common API, memory lifecycle, platform boundaries and explicit fidelity/copy policies. No dependency on another suite codec or shared-foundation package.
5. Run the affected unit and regression groups, independent oracle checks and memory/security tests required for the change. Use controlled release benchmarks for changed hot paths. Expand testing to resolve a concrete risk or required gate, not to inflate a test count.
6. Review the diff, public API, unsafe operations, licence/provenance and emitted resource/copy reports. Update documentation to distinguish implemented, tested, unexecuted and deferred capabilities. Submit a reviewable PR with exact commands and outcomes. Do not tag a stable release merely because compilation passes.

## Non-negotiable engineering rules

- Swift tools 6.2 minimum, Swift 6.4 primary qualification, Swift 6 language mode and complete concurrency checking. Expensive codec work must have a defined executor policy and bounded cancellation points.
- Validate untrusted sizes, offsets, strides, entropy counts and lengths with checked arithmetic. Throw defined errors. No input-dependent force unwrap/cast, assertion trap, uncontrolled allocation or process exit.
- No raw pointer may outlive its scoped borrow; no array/Data buffer pointer becomes an async storage owner. Retain owners and join CPU/GPU work before release. Raw unsafe borrow APIs document caller obligations; closure syntax alone does not prove pointer non-escape.
- An unchecked concurrency annotation needs a local written proof and relevant lifetime/race tests. Do not weaken language mode or globally suppress diagnostics to pass CI.
- Do not reduce bit depth, change signedness, apply display transformations, change compression fidelity or spill decoded images to disk implicitly.
- Prefer common scalar correctness and small measured acceleration boundaries. No runtime fallback to an external reference codec or shell executable.
- Keep codec-specific options explicit. Test declared capabilities; reject unsupported combinations. Use British English in prose.
- Do not relicense third-party code/fixtures, add secrets/patient data, rewrite predecessor history, delete existing repositories, or change organisation permissions as part of implementation.

## Change report required from the agent

State what behaviour changed and why, exact source/baseline/contract revisions, commands and exit results, skipped/unavailable gates, sample/copy/lifetime evidence, performance/memory impact and remaining limitations. Separate measured facts from expectations. Include links to tests and fixture provenance. No invented test counts, benchmark numbers, platform verification or medical/regulatory claims.

## Historical Milestone 1 task prompt

"Read AGENTS.md, IMPLEMENTATION.md, HISTORY.md and the common contract. Carry out Milestone 1 only: validate the local public API and owning-memory contract in Swift 6.4, with meaningful descriptor, lifetime, concurrency and independent-consumer tests. Use synthetic buffers for the adapter experiment and preserve repository independence. Do not migrate codec algorithms or implement the real transcoder in this milestone. Return a reviewable PR, exact test evidence and any concrete contract issue requiring a coordinated revision."

Later task prompts must name the next milestone explicitly. Repository creation and documentation publication are separate from authorising codec implementation.

## Current platform and CLI direction

Contract 0.5.0 restored Apple OS 26.0; suite policy 0.10.0 and the current manifest govern. The [OS 27/CLI record](Documentation/Engineering/OS27CLI/README.md) is historical. Read [CLI.md](CLI.md) and [current validation](Documentation/Engineering/CodecMigration/Validation.md) for implemented payload operations and evidence. Preserve archived inputs and records. Keep help, verbosity, VERSION, man pages and installer behaviour aligned. Library code must not terminate a process; the executable alone maps documented CLI exit statuses. Codec implementations still require their assigned milestone.
