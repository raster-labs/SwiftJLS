# Independent coverage of native sample decode

The final `bee49a2` host and native macOS 26.0 debug/release/ASan/TSan XMLs each confirm all four named declarations in the sibling JSON, without failure, error or skip. This is a coverage review of existing runs, not another test execution.

`MappingMetadataTests.independentMappingTablesPreserveIndicesAndMapExplicitly` supplies 15 independent sample-interleaved native cases at 2/8/12/16 bits and NEAR 0/1. It owns packed UInt16 output and checks every sample against stored values from an independent CharLS decode (mapping revision `04e44bb760632104ab1209593eea3f8c20ac11e5`). The packed native path follows from `JPEGLSHeader.makeDescriptor` and the `InterleavedKernel` admission condition; this review does not add runtime instrumentation.

`ComponentCodecTests.independentPlanarAndPixelLayouts` additionally checks 66 CharLS 2.4.2 sample-interleaved fixtures and 18 HP sample-interleaved fixtures against their independent reconstructed samples. Its padded/sparse layouts exercise the general view, in both endian orders. These are distinct from the packed native cases.

The two new `SampleNativeDecodeTests` declarations use synthetic expected values and streams from the current encoder. They cover NEAR 0/3, odd base addresses, native/fallback equality, guards and bounded cancellation; they are not counted as independent oracle evidence.

The JSON records exact source/fixture provenance, manifest hashes, test names and matching XML hashes. No oracle tool was built or rerun. Independent native NEAR 0/1 coverage is not a claim of exhaustive external coverage at every supported NEAR value.
