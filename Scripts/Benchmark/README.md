# Release benchmark harness

Compile `Consumer.swift` in two separate executable packages: one linked to pinned JLSwift `15aa75164145414f3d5ffb801401c52d40cc5bcc` with the `PREDECESSOR` compilation condition, and one linked only to SwiftJLS without that condition. Use tools 6.2 or newer, Swift 6 language mode, and `swift build -c release`. These development consumers are outside the shipped library graph.

Run `compare.py --predecessor /path/to/old/Benchmark --successor /path/to/new/Benchmark --output /path/to/results` from SwiftJLS. It uses four alternating process blocks per case, each with five warm-ups and five measured iterations, and retains all raw timings. Full sample validation precedes timing. This compares supported public APIs with owned decode, including required admission/validation work. Fixture sizes include odd non-square, 512², 2048² and 4096×3073, at 12 and 16 meaningful bits with flat/ramp/seeded-noise samples.

RSS is the whole-process high-water mark and includes caller input storage and runtime overhead. It is not pixel-allocation or copy instrumentation; unavailable counters are explicitly null. Developer-workstation runs are advisory unless power, thermal state and competing load have actually been controlled. Investigate latency/memory regressions and encoded-size changes under PERF-03; do not silently convert a benchmark failure into a pass.
