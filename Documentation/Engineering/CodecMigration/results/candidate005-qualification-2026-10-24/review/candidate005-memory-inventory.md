# Candidate005 memory inventory and acceptance boundary

Status: source frozen and host tests passed in four configurations; fresh Linux workspace/copy collection and RSS comparison are pending. This is a source-bound design inventory, not a measurement result or final acceptance. `candidate005-memory-inventory.json` binds its source references to the final candidate005 receipt and source pins.

## What the contract requires

`MEMORY_CONTRACT.md` MEM-10 permits algorithm workspace, requires its per-operation/sample/row bound to be stated, and forbids a hidden second final decoded image for hand-off. MEM-12 requires peak owned-pixel and workspace reporting **where measurable** and requires unknown measurements to remain unknown. COMMON_API API-07 likewise describes operation statistics **where available**. TEST-06 adds independent finite ceilings and aggregate preallocation admission; concurrency in an application must be accounted for by the caller, since a per-operation limit is not a process-wide concurrency coordinator.

These requirements support a source-level bounded-storage proof plus scoped empirical checks. They do not require or justify a universal exact maximum for Swift runtime heaps, all compiler stack layouts, allocator usable sizes, VM residency, or concurrently running calls. Historical records that say an exact universal total is unknown remain true. That uncertainty must not be relabelled as a newly measured peak or silently erased from history.

PERF-03 is separate: an unexplained confirmed representative peak-memory regression blocks stable release. Requested-heap attribution cannot replace the original whole-process RSS comparison. The shared-host condition must stay explicit; do not subtract runtime baselines or label the host idle.

## Units and enforced reservations

Let `F = 65,536`, `I = MemoryLayout<Int>.stride`, `C <= 4`, `W` be the active component width, `N = 2*T3+1 <= 131,071`, `GInt = N*I`, `G8 = N`, `E` be retained encoded input bytes, `L` the checked compressed-output limit, `M` admitted retained/constructed metadata bytes, and `D = 2*sum(rangeCount)*MemoryLayout<Range<Int>>.stride`. All arithmetic entering admission uses checked integer helpers; the profile limits are caller-selected finite ceilings.

| Operation | Logical reservation passed to `maximumWorkspaceBytes` | Separate bytes admitted into aggregate memory |
| --- | --- | --- |
| Initial parser | `F` | `E` |
| Metadata/directory parser stages | `F + 32*M + D` | `E`; interpreted destination extent additionally at final admission |
| Scalar encode | `F + 2*GInt + 2*L + (NEAR > 0 ? 4*W : 0) + 32*M + discardedICCBytes` | Full retained source capacity and `L` |
| Component encode, noninterleaved | Same, with `4*W` only for NEAR | Full retained source capacity and `L` |
| Component encode, interleaved | `F + 2*GInt + 2*L + 4*W*C + 32*M + discardedICCBytes` (row reservation remains conservative for lossless) | Full retained source capacity and `L` |
| Scalar/component decode | `F + 2*max(GInt of admitted scans) + 2*E + D + 32*M` | Full supplied destination capacity or owned output extent, plus `E` |

The encode/decode numeric reservations are unchanged. Narrower Int8 tables reduce actual payload; they do not reduce the enforced conservative `2*GInt` reservation. The fixed parser floor is newly enforced before its first containers and retained in all parser admissions. These allowances are not reported as measured `peakWorkspaceBytes`.

The output writer bounds each appended byte by `L`. Its array growth and final `Data` construction remain included in the existing compressed reservation (two `L` workspace allowances plus the separately admitted `L`). On decode, the retained `Data` and active range's byte-array materialisation remain separately charged (`E` compressed plus two `E` workspace allowances). These are source-level conservative payload allowances, not a promise of exact Swift capacity rounding or allocator usable size.

## Actual algorithm storage and lifetime

| Storage | Source-level extent/lifetime |
| --- | --- |
| Prediction context | One active `ManagedBuffer` holding 365 records of four `Int` values: `1,460*I` payload bytes (11,680 on 64-bit; 5,840 with 32-bit Int). Four two-element run-state arrays are inline, `8*I` bytes. |
| Gradient quantisation | One active `[Int8]` with `N` entries. Values remain in -4...4; lookup widens to Int before context arithmetic. Both directions use `G8`, not `GInt`. Maximum payload is 131,071 bytes instead of 1,048,568 on a 64-bit host. |
| Scalar/noninterleaved lossless encode | Reads causal source samples directly. No predictor-row allocation. |
| NEAR encode | Two reconstructed UInt16 rows for the active component, `4*W`; interleaved NEAR retains `4*W*C`. Buffers are swapped without publication or a third row. |
| Decode | Causal reconstruction reads the final supplied/owned output directly. No reconstructed-row arrays or second full decoded image. Active reader has a byte array plus fixed counters/window; byte payload is charged as compressed storage. |
| Interleaved scheduling | Inline arrays with at most four component indices/edges and four neighbour records. Vertical-sampling schedule has at most `C` Int elements. |
| Borrowed sample/HP/native descriptors | At most four component/native descriptors, or three HP descriptors, retaining synchronous borrowed views. Logical payload is count times the relevant type stride, within `F`; these contain no image samples. Prior 64-bit observed strides (72-byte component, 48-byte native) are ABI-specific, not universal constants. |
| Parser | At most four frame components/scans; validated selectors and descriptor containers. The covered-component mask is UInt8. Metadata-backed containers scale with admitted metadata and are charged separately, not hidden in a fixed per-pixel formula. |
| Scan directory | Range count is bounded by the admitted restart schedule. The parser reserves once after checked `D` admission and `expected <= remainingEncodedBytes/3`: each accepted nonempty entropy range needs a following marker of at least two bytes. This prevents huge reservations from tiny truncated inputs and removes geometric old/new directory-buffer coexistence. |
| Mapping/HP application | Admitted mapping tables/metadata plus scalar temporaries; writes into the final destination. No mapped/transformed sample frame. |
| Owned output | Exactly one final owner; pixel storage, not algorithm workspace. Supplied decode must allocate no additional owned pixel buffer and preserve the supplied owner. |
| Fixed control | Budget/cancellation scalars, reader/writer counters, leases, closures, descriptor and owner objects are bounded per operation. `F` is conservative logical control allowance; instrumentation must report observed requested allocations separately. |

Scans and restart chunks execute sequentially. One active context/table is not multiplied by total scan/chunk count. Distinct concurrent calls retain distinct state, and process-wide aggregate concurrency remains the application's responsibility.

For the existing maximum-table `W=257` scalar NEAR profile, context/table/row payload becomes `11,680 + 131,071 + 1,028 = 143,779` bytes on 64-bit Int. Its 257x129 UInt16 sample frame is 66,306 bytes, so the algorithm payload still exceeds that frame (~2.17x); this must be stated under MEM-10. These are payload calculations, not predicted measured peaks. The retained `2*GInt` table admission alone is 2,097,136 bytes at that threshold.

## Evidence still needed before a disposition

1. Fresh ordinary-release Linux ARM64 89-case collection: all raw allocations/free events retained, original classifier controls pass, zero unexplained codec allocation or live-baseline bytes, per-category and simultaneous totals reconcile, 23 owned pixel allocations and none in the other 66 operations. Compare actual table/context/directory/control changes against candidate004; reject new unrecognised stacks rather than broadening classification without proof.
2. Fresh CopyProbe20: ten normal zero-source-copy rows and ten exact-capacity positive controls, correct samples. It does not observe inlined copies and therefore supplements the source/allocator proof.
3. Final current-source host/platform checks and independent interoperability, including the four new parser boundary/restart tests. Host validation is bound by the final receipt, not by previously measured004 results.
4. The separately predeclared current-source RSS experiment and its same-binary controls, with all outcomes and shared-service conditions retained. RSS findings require their own PERF-03 disposition.

After those checks, a defensible completion statement can cover **the bounded source-level algorithm storage and fully attributed requested heap for the measured profiles**, while explicitly retaining runtime/allocator/stack scope limits. It cannot say the observed maximum is a universal bound. `peakWorkspaceBytes` remains `nil`; `pure_algorithm_workspace_complete` in the existing empirical ledger remains false because it denotes a combined pure stack/heap total that the tool does not measure. Physical-device testing and milestone5 stay pending.
