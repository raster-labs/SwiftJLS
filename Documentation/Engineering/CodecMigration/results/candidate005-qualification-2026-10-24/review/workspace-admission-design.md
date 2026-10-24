# Bounded parser admission repair — 24 October 2026

The repair closes a concrete admission omission and a restart-array growth risk. It does not establish a universal allocator, stack, runtime, or RSS peak.

- All four parser `CodecBudget.admit` sites now include the existing 64 KiB control allowance. The initial check precedes parser containers; metadata and restart directories retain checked variable charges. The scalar context and two-Int-table formula are aliases of the same unchanged numeric reservations.
- At SOS, checked accumulated directory admission happens first. Each accepted range is nonempty (`scanEnd > scanStart`) and ends at at least two marker bytes; subsequent ranges begin after the restart marker. Therefore `expected <= (bytes.count - end) / 3` is necessary for a valid stream. `end` is already proven within the input by the segment-length guard. The division cannot overflow. Fill/stuffing/extra headers increase the required input, so do not invalidate the lower bound.
- Only after both conditions pass does `ranges.reserveCapacity(expected)` execute. Accepted append count never exceeds expected. This removes geometric old/new directory buffer overlap at power-of-two boundaries without claiming allocator rounding is exact.
- Error precedence stays admission-before-malformed for the directory: the new input-size guard follows the previous budget check. An impossible truncated directory rejects before destination acquisition or writes.

Four new tests cover metadata-free workspace/total exact boundaries, immediate metadata-charge failure, valid restarts around powers of two with sample comparison, and a tiny stream falsely declaring 65,535 restart ranges while preserving destination reuse. No builds/tests were run by this agent.

## Scope of the remaining memory proof

MEM-10 requires bounded algorithm work, row/sample state, and direct final destinations. MEM-12/API-07 allow unknown optional measured peak fields. TEST-06 requires independent preallocation limits including aggregate memory. A documented/tested algorithm reservation plus scoped observed heap peaks can establish that scope; it cannot justify a universal allocator/runtime/stack maximum. Keep `peakWorkspaceBytes` nil until a real per-operation measurement exists.

The source inventory still distinguishes fixed managed contexts (365*4 Int), bounded control containers, one active gradient table, NEAR row state (4*width bytes per active component), scan directories, metadata construction, and compressed-buffer growth. Encode/decode retain their conservative Int-based two-table and existing input/output growth reservations. Swift Array payload/capacity accounting is not a portable exact allocator-byte bound. Compiler/platform stack evidence is scoped and separate.

RSS remains a separate PERF-03 metric: preserve the original whole-process peak and same-binary controls. Shared services remain running. Do not substitute a heap ledger, subtract runtime baselines, or infer that a small table reduction closes a multi-megabyte RSS effect.
