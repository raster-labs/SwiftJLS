# Predecessor parity and qualification — 10 October 2026

Baseline: JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc`; suite policy 0.10.0. This record supersedes the older profile limitations in the chronological checkpoint log. No release or consumer cutover is authorised by this record.

## Migrated behaviour

| Predecessor capability | SwiftJLS owning API behaviour | Evidence |
| --- | --- | --- |
| Unsigned 2–16-bit, 1–4 components, all scan interleaves | Scoped source reads and final-destination writes; lossless/near-lossless, presets and non-interleaved row restarts | Existing scalar/component/reference manifests |
| LSE mapping tables, 1/2-byte unsigned entries | Bounded tables and contiguous continuations; complete MAXVAL+1 entries required; explicit unsigned output precision | 60 new independent CharLS inputs, including full 65,536-entry tables; actual predecessor continuation files |
| Mapping indices as encoder input | Attach `JPEGLSMappingTables.metadata` to the index image; selectors follow logical components | Public API consumer and independent decoding of successor output |
| Parser APP0–APP15 and COM data | Ordered binary payloads through `JPEGLSMetadata`; opaque bytes retain no inferred text/ICC interpretation | Empty, duplicate, binary and unknown APP8 payload tests; preserve/discard/required policies |
| SPIFF application data | Header, density/aspect and directory preservation; RGB/grey interpretation; other colour codes retained as required metadata with uninterpreted components | Directory/density and unknown-colour tests |
| LSE extended dimensions | Standard Ye/Xe ordering, checked dimension and memory admission | Four independent tall/wide CharLS fixtures; actual predecessor extended streams |
| Legacy HP transformations | Explicit predecessor inverse; all three interleaves and 2–16-bit coding; no marker-based autodetection | 36 actual predecessor fixtures at 2/8/12/16 bits plus the earlier six 8/16-bit fixtures |
| Subsampled line decoding | Explicit per-plane horizontal/vertical factors; ceiling dimensions; final caller planes with no upsampling | Odd-sized 17×19 zero-run streams, NEAR 0/3, verified with the pinned predecessor; padded big-endian destination tests |
| Parser per-scan DRI/presets | Parameters captured per scan; 16/24/32-bit DRI fields; mixed scan NEAR reports the maximum bound | Existing scan regression suite; additional combinations remain subject to fixture qualification |

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

Use only the options matching the known producer. These options are decoder-only. Migrated output uses standard syntax/formulae. For legacy transformed NEAR streams, modular inverse transforms can magnify error across wrap boundaries; the report conservatively bounds RGB error by the full declared range, never the transformed-channel NEAR.

Malformed/incomplete tables fail before a destination write. The predecessor's fallback of returning an unmapped value for an out-of-range index is deliberately not retained. External-table abbreviated streams and table redefinition are rejected explicitly. Subsampled encode, DNL-driven unknown-height decode and alpha/ICC colour interpretation were not functional predecessor codec paths and are not claimed. The existing owner-approved PNG/TIFF and extended CLI deferrals remain in force.

## Qualification status

The added code has passed local debug, release, ASan and TSan runs with 70 test declarations; exact command evidence is recorded with the final validation checkpoint. A separate CharLS development checkout pinned to `04e44bb760632104ab1209593eea3f8c20ac11e5` independently verified 100 additional successor outputs: 60 mapping, four extended and 36 legacy HP migrations. CharLS remains test-only, outside the package dependency graph.

That oracle splits 3-byte entries across 65,530-byte continuation chunks for 16-bit tables. T.87 requires integral entries per segment. Those four cases are excluded explicitly; they are not accepted conformance vectors. One/two-byte predecessor widths and smaller opaque 3-byte tables are independently covered.

Latest-source hosted CI, expanded duration fuzzing, complete production allocation/copy classification, controlled performance and Apple device/simulator runtime qualification remain separate gates. Earlier successful campaigns apply to their recorded source revisions; do not promote them to evidence for new parsing paths. The metadata allowance conservatively admits 32 times retained metadata bytes for archives, table copies and container overhead; this is an admission ceiling, not a measured allocation claim.
