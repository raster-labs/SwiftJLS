# Development-only cross-codec consumer

This separate package pins SwiftJ2K to `be4e7a3ad352759e7a78a90f6a2e2c3b7aa0f748`; neither codec library gains a dependency on the other.

Run `swift run --package-path Examples/CrossCodecConsumer` from SwiftJLS. Optionally run the built executable with one output-directory argument to export final compressed validation streams after both in-memory routes finish. Input and intermediate pixels never use files.

The harness checks 37×23 12/16-bit deterministic samples in both directions, direct destination identities and writes, adapter reads, sentinel padding, different row strides, byte-identical concurrent and packed-input encodes, cancellation invalidation and sealed-write rejection. It does not claim allocator telemetry or operating-system file-I/O tracing from report fields alone. Those remain distinct qualification gates.
