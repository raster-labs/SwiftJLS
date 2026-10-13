# Bounded concurrent resource workload

Run `swift run -c release --package-path Examples/ResourceStress ResourceStress`. This standalone development consumer has four fixed workers: 512×512, 12-bit greyscale/RGB, each at NEAR 0 and 3. Each worker runs eight serial frame transactions with one encode, owned decode and caller-destination decode. Every output sample is checked, the supplied owner must be preserved, and reports must contain exactly one owned pixel allocation, no supplied pixel allocation and no pixel copies per frame.

Each operation uses explicit ceilings: 8 MiB compressed, 4 MiB decoded, 32 MiB workspace, one codec worker and 64 MiB total admission. These are per-operation limits. The harness bounds its queue to four workers; the library does not provide a global process admission scheduler. The sum of configured limits is not a measured memory peak or a device guarantee.

The contract workflow profiles this ordinary release executable with Heaptrack, then replays allocation/free events using `Scripts/StorageEvidence/measure-peaks.py`. The JSON consumer results are correctness/report evidence; allocator peaks are separate observations. Keep runtime/unattributed bytes and nonpixel heap attribution visible. This is neither a latency benchmark nor physical-device admission evidence.
