# Predecessor profile coverage and qualification — 12 October 2026

Baseline: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; suite policy 0.10.0. This record supersedes the older profile limitations in the chronological checkpoint log. No release or consumer cutover is authorised by this record.

[The completion audit](Completion.md) records the merged PR 15 baseline and remaining qualification. The inactive-DRI compatibility gap is closed in runtime checkpoint `4008f21`; this profile inventory does not imply that all release qualification gates have passed.

## Migrated behaviour

| Predecessor capability | SwiftJLS owning API behaviour | Evidence |
| --- | --- | --- |
| Unsigned 2–16-bit, 1–4 components, all scan interleaves | Scoped source reads and final-destination writes; lossless/near-lossless, presets and non-interleaved row restarts | Existing scalar/component/reference manifests |
| LSE mapping tables, 1/2-byte unsigned entries | Bounded tables and contiguous continuations; complete MAXVAL+1 entries required; explicit unsigned output precision | 60 new independent CharLS inputs, including full 65,536-entry tables; actual predecessor continuation files |
| Mapping indices as encoder input | Attach `JPEGLSMappingTables.metadata` to the index image; selectors follow logical components | Public API consumer and independent decoding of successor output |
| Parser APP0–APP15 and COM data | Ordered binary payloads through `JPEGLSMetadata`; opaque bytes retain no inferred text/ICC interpretation | Empty, duplicate, binary and unknown APP8 payload tests; preserve/discard/required policies |
| SPIFF application data | Header, density/aspect and directory preservation; RGB/grey interpretation; other colour codes retained as required metadata with uninterpreted components | Directory/density and unknown-colour tests |
| LSE extended dimensions | Standard Ye/Xe ordering, checked dimension and memory admission | Four independent tall/wide CharLS fixtures; actual predecessor extended streams |
| Legacy HP transformations | Explicit predecessor inverse; all three interleaves and 2–16-bit coding; no marker-based autodetection | 36 actual predecessor fixtures at 2/8/12/16 bits, 36 combined mapping/HP lossless/near profiles, plus the earlier six 8/16-bit fixtures |
| Subsampled line decoding | Explicit per-plane horizontal/vertical factors; ceiling dimensions; final caller planes with no upsampling | Odd-sized 17×19 zero-run streams plus 12 nonzero block/noise 8/12/16-bit streams at NEAR 0/3, verified with the unchanged pinned decoder; padded planes in both byte orders |
| Parser per-scan DRI/presets | Parameters captured per scan; 16/24/32-bit DRI fields; mixed scan NEAR reports the maximum bound | Inactive DRI at/above frame height accepted for line/sample and subsampled line input; 16/24/32-bit fields, inspection, both decode destinations and malformed-marker rejection tested |
| Bounded complete codestreams | Resource admission, EOI and trailing-data checks; merged PR 15 accepts one zero after an odd-length stream | 18 bounded-decoding comparisons plus all four previously failing DRI comparisons agree; 84 declarations and 73 payload CLI checks pass at `8389b29` |

The successor additionally preserves opaque mapping entries of widths 1–255 as required table metadata. Unsigned scalar interpretation is restricted to widths 1/2. T.87 C.2.4.1.2 explicitly leaves entry-byte interpretation to the application. The default decoder therefore returns indices and required tables, rather than guessing output precision from observed values or byte width.

## Mapping and metadata API

`JPEGLSMappingTable(id:entryWidth:entries:)` accepts unsigned scalar values; `init(id:entryWidth:data:)` accepts raw entries in wire byte order. `JPEGLSMappingTables(tables:componentTableIDs:)` supplies an `ImageMetadata` value with a required `jpeg-ls.mapping-tables` key. Merge it with other metadata when constructing an index `Image`. Encoding does not perform inverse palette lookup: this matches the predecessor's index-input API.

To obtain mapped samples, configure the decoder explicitly:

```swift
let decoder = try Decoder(configuration: .init(codecOptions: .init(
    restartIntervalLines: 0, mappingOutputPrecision: 16)))
let mapped = try await decoder.decode(data)
```

Both inspection and decoding report the requested meaningful precision. All table values must fit it. Mapping happens in the final caller allocation after entropy prediction; a caller's storage width must also hold the intermediate indices. Applied mapping metadata is consumed, so re-encoding the resulting image encodes the final samples. For near-lossless indices, the reported mapped error bound is computed from the table rather than incorrectly reusing NEAR.

`JPEGLSMetadata.Segment(marker:payload:)` represents APP/COM data. `JPEGLSMetadata(metadata:)` reads the ordered archive. HP control markers cannot masquerade as opaque metadata. `jpeg-ls.spiff` contains the raw SPIFF APP8 header/directory sequence; encoding validates it against the descriptor. `discardAncillary` retains required mapping tables and uninterpreted SPIFF meaning. Unknown unrepresentable required keys fail; the NRRD CLI continues to reject output metadata it cannot preserve.

## Explicit legacy compatibility

The pinned predecessor differs from standard wire semantics in four places. None can be safely inferred from the stream alone:

- `hpInterpretation: .legacyJLSwift`: predecessor HP inverse formulae; also selects its low-range defaults for those known-producer assets.
- `legacyPresetDefaults: true`: the predecessor's nonstandard default thresholds below MAXVAL 128, including streams without HP.
- `legacyMappingContinuations: true`: LSE type 3 omits Wt in the predecessor. Standard output always includes Wt.
- `legacyExtendedDimensions: true`: the predecessor writes Xe before Ye; standard output writes Ye before Xe.

Use only the options matching the known producer. These options are decoder-only. Migrated output uses standard syntax/formulae. Combined predecessor mapping/HP assets apply the table before the legacy inverse; only explicit predecessor interpretation accepts that combination. For legacy transformed NEAR streams, modular inverse transforms can magnify error across wrap boundaries; the report conservatively bounds RGB error by the full declared range, never the transformed-channel NEAR.

Malformed/incomplete tables fail before a destination write. The predecessor's fallback of returning an unmapped value for an out-of-range index is deliberately not retained. External-table abbreviated streams and table redefinition are rejected explicitly. Subsampled encode, DNL-driven unknown-height decode and alpha/ICC colour interpretation were not functional predecessor codec paths and are not claimed. The existing owner-approved PNG/TIFF and extended CLI deferrals remain in force.

## Qualification status

The 10 October codec checkpoint passes 74 test declarations in local debug, release, ASan and TSan, and the 32-bit Watch device SDK build passes. All 14 hosted contract jobs and four Apple simulator runtime jobs also pass on this final source. A separate CharLS development checkout pinned to `04e44bb760632104ab1209593eea3f8c20ac11e5` independently verifies 136 additional successor outputs: 60 mapping, four extended, 36 legacy HP and 36 combined mapping/HP migrations. CharLS remains test-only, outside the package dependency graph. Exact revisions, commands, duration status and remaining release gates are maintained in [Validation.md](Validation.md).

That oracle splits 3-byte entries across 65,530-byte continuation chunks for 16-bit tables. T.87 requires integral entries per segment. Those four cases are excluded explicitly; they are not accepted conformance vectors. One/two-byte predecessor widths and smaller opaque 3-byte tables are independently covered.

The merged PR 15 runtime passes 80 declarations in ten suites in local debug/release/ASan/TSan runs. The corrected runtime also passes all four Apple simulator jobs and the Watch device-architecture build; see [current validation](Validation.md) for exact hosted revisions and versions. Physical Watch execution is excluded from this task.

Current scoped workspace accounting includes source bounds and 89 fully attributed observed operations; universal heap-plus-stack-plus-allocator totals remain unknown. The metadata allowance conservatively admits 32 times retained metadata bytes for archives, table copies and container overhead; this is an admission ceiling, not a measured allocation claim. Earlier mutation campaigns retain their source revisions; current-source duration evidence is linked from [Validation.md](Validation.md).

The current Milestone 4 checkpoint `e6a6436` passes 120 declarations in 24 suites under debug/release/ASan/TSan on both the host and native arm64 macOS 26.0 (25A354) guest. Five exact OS 26.0 simulator consumers, CLI/resource consumers and SDK builds pass. The native guest uses hardware virtualisation. [Current qualification](Milestone4Performance.md) records native sample-interleaved decode improvements, powered representative measurements, the performance disposition and refreshed workspace evidence. All physical-device tests remain pending; Milestone 5 is deferred.
