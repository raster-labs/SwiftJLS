// SPDX-License-Identifier: Apache-2.0
import Darwin
import Foundation
import SwiftJLS

struct ProbeError: Error, CustomStringConvertible {
    let description: String
    init(_ description: String) { self.description = description }
}

/// Sequential per-phase memory and thread telemetry snapshot.
/// Note: getrusage, task_info, malloc_zone_statistics, and proc_pidinfo are captured sequentially,
/// not as an atomic simultaneous kernel measurement.
struct PhaseSnapshot: Codable, Sendable {
    let phase: String
    /// Current resident memory size in bytes from mach_task_basic_info
    let current_resident_bytes: UInt64
    /// Process lifetime high-water mark of resident_size from mach_task_basic_info
    let peak_resident_bytes_mach: UInt64
    /// Process lifetime high-water mark of ru_maxrss from getrusage(RUSAGE_SELF) (bytes on Darwin)
    let peak_ru_maxrss_bytes: Int
    /// Current physical footprint in bytes from task_vm_info
    let current_phys_footprint_bytes: UInt64
    /// Current allocated bytes in use across all malloc zones (malloc_zone_statistics(nil, ...).size_in_use)
    let malloc_current_size_in_use_bytes: UInt64
    /// High-water mark of touched/in-use bytes across malloc zones; when observed as 0 under the active allocator, treat as unavailable rather than zero workspace
    let malloc_high_water_max_size_in_use_bytes: UInt64
    /// Total VM bytes reserved by malloc zones (size_allocated)
    let malloc_reserved_size_allocated_bytes: UInt64
    /// Current blocks in use across malloc zones
    let malloc_blocks_in_use: UInt32
    /// Current process thread count from proc_pidinfo(PROC_PIDTASKINFO).pti_threadnum
    let current_thread_count: Int32
}

@inline(never)
func captureSnapshot(_ phase: String) throws -> PhaseSnapshot {
    var usage = rusage()
    let ruStatus = getrusage(RUSAGE_SELF, &usage)
    guard ruStatus == 0, usage.ru_maxrss > 0 else {
        throw ProbeError("getrusage(RUSAGE_SELF) failed at \(phase): status=\(ruStatus), ru_maxrss=\(usage.ru_maxrss)")
    }

    var basicInfo = mach_task_basic_info()
    var basicCount = mach_msg_type_number_t(MemoryLayout<mach_task_basic_info>.size / MemoryLayout<natural_t>.size)
    let basicKr = withUnsafeMutablePointer(to: &basicInfo) {
        $0.withMemoryRebound(to: integer_t.self, capacity: Int(basicCount)) {
            task_info(mach_task_self_, task_flavor_t(MACH_TASK_BASIC_INFO), $0, &basicCount)
        }
    }
    guard basicKr == KERN_SUCCESS, basicInfo.resident_size > 0, basicInfo.resident_size_max > 0 else {
        throw ProbeError("task_info(MACH_TASK_BASIC_INFO) failed at \(phase): kr=\(basicKr)")
    }

    var vmInfo = task_vm_info_data_t()
    var vmCount = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<natural_t>.size)
    let vmKr = withUnsafeMutablePointer(to: &vmInfo) {
        $0.withMemoryRebound(to: integer_t.self, capacity: Int(vmCount)) {
            task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &vmCount)
        }
    }
    guard vmKr == KERN_SUCCESS, vmInfo.phys_footprint > 0 else {
        throw ProbeError("task_info(TASK_VM_INFO) failed at \(phase): kr=\(vmKr)")
    }

    var mstats = malloc_statistics_t()
    malloc_zone_statistics(nil, &mstats)
    guard mstats.blocks_in_use > 0, mstats.size_in_use > 0, mstats.size_allocated > 0 else {
        throw ProbeError("malloc_zone_statistics returned zero at \(phase): blocks=\(mstats.blocks_in_use), in_use=\(mstats.size_in_use), allocated=\(mstats.size_allocated)")
    }

    var pti = proc_taskinfo()
    let expectedPtiSize = Int32(MemoryLayout<proc_taskinfo>.size)
    let ptiRet = proc_pidinfo(getpid(), PROC_PIDTASKINFO, 0, &pti, expectedPtiSize)
    guard ptiRet == expectedPtiSize, pti.pti_threadnum > 0 else {
        throw ProbeError("proc_pidinfo(PROC_PIDTASKINFO) failed at \(phase): ret=\(ptiRet), expected=\(expectedPtiSize), threads=\(pti.pti_threadnum)")
    }

    return PhaseSnapshot(
        phase: phase,
        current_resident_bytes: UInt64(basicInfo.resident_size),
        peak_resident_bytes_mach: UInt64(basicInfo.resident_size_max),
        peak_ru_maxrss_bytes: Int(usage.ru_maxrss),
        current_phys_footprint_bytes: UInt64(vmInfo.phys_footprint),
        malloc_current_size_in_use_bytes: UInt64(mstats.size_in_use),
        malloc_high_water_max_size_in_use_bytes: UInt64(mstats.max_size_in_use),
        malloc_reserved_size_allocated_bytes: UInt64(mstats.size_allocated),
        malloc_blocks_in_use: mstats.blocks_in_use,
        current_thread_count: pti.pti_threadnum
    )
}

struct HarnessContext {
    let width: Int
    let height: Int
    let bits: Int
    let pattern: String
    let components: Int
    let near: Int
    let interleave: Int
    let endToEnd: Bool
    let maximum: Int
    let benchmarkLimits: ResourceLimits
    let mode: CodecOptions.InterleaveMode

    init(width: Int, height: Int, bits: Int, pattern: String, components: Int = 1, near: Int = 0, interleave: Int = 0, endToEnd: Bool = true) throws {
        self.width = width
        self.height = height
        self.bits = bits
        self.pattern = pattern
        self.components = components
        self.near = near
        self.interleave = interleave
        self.endToEnd = endToEnd
        self.maximum = (1 << bits) - 1
        self.benchmarkLimits = try ResourceLimits(
            maximumWorkspaceBytes: 1024 * 1024 * 1024,
            maximumMemoryBytes: 2 * 1024 * 1024 * 1024
        )
        guard let m = CodecOptions.InterleaveMode(rawValue: UInt8(interleave)) else {
            throw ProbeError("Invalid interleave mode")
        }
        self.mode = m
    }

    func sample(_ x: Int, _ y: Int, _ component: Int = 0) -> Int {
        switch pattern {
        case "flat": return (maximum / 2 + component * 17) & maximum
        case "ramp": return (x * 13 + y * 17 + component * 31) & maximum
        default:
            let index = UInt64((component * height + y) * width + x)
            var z = index &+ 0x9e3779b97f4a7c15
            z = (z ^ (z >> 30)) &* 0xbf58476d1ce4e5b9
            z = (z ^ (z >> 27)) &* 0x94d049bb133111eb
            return Int((z ^ (z >> 31)) & UInt64(maximum))
        }
    }

    func makeCanonical() -> [UInt16] {
        endToEnd ? (0..<(components * height * width)).map { i in
            UInt16(sample(i % width, (i / width) % height, i / (width * height)))
        } : []
    }

    func inputSample(_ x: Int, _ y: Int, _ c: Int, canonical: [UInt16]) -> Int {
        endToEnd ? Int(canonical[(c * height + y) * width + x]) : sample(x, y, c)
    }

    @inline(never)
    func makeImage(canonical: [UInt16]) throws -> Image {
        let capacity = width * height * 2
        let planes = try (0..<components).map { c in
            try PlaneDescriptor(
                width: width, height: height, components: [c], offset: c * capacity,
                rowBytes: width * 2, byteCount: (c + 1) * capacity
            )
        }
        let shape = try ImageDescriptor(
            width: width, height: height, meaningfulBits: bits,
            components: components == 1 ? [.grey] : [.red, .green, .blue],
            colour: components == 1 ? .greyscale : .rgb, planes: planes
        )
        return try ImageDestination.allocate(descriptor: shape).write { bytes in
            for c in 0..<components {
                for y in 0..<height {
                    for x in 0..<width {
                        let at = c * capacity + (y * width + x) * 2
                        let value = inputSample(x, y, c, canonical: canonical)
                        bytes[at] = UInt8(truncatingIfNeeded: value)
                        bytes[at + 1] = UInt8(value >> 8)
                    }
                }
            }
        }
    }

    @inline(never)
    func encode(_ image: Image) async throws -> Data {
        try await Encoder(
            configuration: .init(
                mode: near == 0 ? .lossless : .nearLossless(maximumAbsoluteError: near),
                codecOptions: .init(restartIntervalLines: 0, interleaveMode: mode)
            )
        ).encode(
            image,
            options: .init(resourceLimits: benchmarkLimits, executionPolicy: .scalarCPU)
        ).data
    }

    @inline(never)
    func decodeReturningImage(_ data: Data, verify: Bool) async throws -> Image {
        let image = try await Decoder().decode(
            data,
            options: .init(resourceLimits: benchmarkLimits, executionPolicy: .scalarCPU)
        ).image
        guard image.descriptor.meaningfulBits == bits else {
            throw ProbeError("Decoded meaningfulBits mismatch")
        }
        if verify {
            try image.storage.withUnsafeBytes { bytes in
                guard image.descriptor.components.count == components else {
                    throw ProbeError("Decoded components mismatch")
                }
                for p in image.descriptor.planes {
                    for (slot, c) in p.components.enumerated() {
                        for y in 0..<height {
                            for x in 0..<width {
                                let i = p.offset + y * p.rowBytes + x * p.pixelStride + slot * p.sampleStride
                                let actual = Int(bytes[i]) | Int(bytes[i + 1]) << 8
                                guard abs(actual - sample(x, y, c)) <= near else {
                                    throw ProbeError("Decoded sample mismatch at (\(x),\(y),\(c))")
                                }
                            }
                        }
                    }
                }
            }
        }
        return image
    }

    @inline(never)
    func decodeAndRelease(_ data: Data, verify: Bool) async throws {
        _ = try await decodeReturningImage(data, verify: verify)
    }
}

@inline(never)
func runPreflightAndCapture(
    ctx: HarnessContext,
    canonical: [UInt16],
    image: Image,
    reference: Data,
    snaps: inout [PhaseSnapshot]
) async throws {
    let preflight = try await ctx.decodeReturningImage(reference, verify: true)
    try withExtendedLifetime((canonical, image, reference, preflight)) {
        try snaps.append(captureSnapshot("05_during_preflight_decode_alive"))
    }
}

@inline(never)
func runIter0FaithfulEncode(
    ctx: HarnessContext,
    canonical: [UInt16],
    image: Image,
    reference: Data,
    snaps: inout [PhaseSnapshot]
) async throws {
    let encoded = try await ctx.encode(image)
    guard encoded == reference else { throw ProbeError("Iter0 encode mismatch") }
    try withExtendedLifetime((canonical, image, reference, encoded)) {
        try snaps.append(captureSnapshot("08_iter0_encode_output_alive"))
    }
}

@inline(never)
func runIter0FaithfulDecode(
    ctx: HarnessContext,
    canonical: [UInt16],
    image: Image,
    reference: Data,
    snaps: inout [PhaseSnapshot]
) async throws {
    let decoded = try await ctx.decodeReturningImage(reference, verify: false)
    try withExtendedLifetime((canonical, image, reference, decoded)) {
        try snaps.append(captureSnapshot("09_iter0_owned_decode_output_alive"))
    }
}

@inline(never)
func runIter0FaithfulPrepareAndEncode(
    ctx: HarnessContext,
    canonical: [UInt16],
    image: Image,
    reference: Data,
    snaps: inout [PhaseSnapshot]
) async throws {
    let fresh = try ctx.makeImage(canonical: canonical)
    try withExtendedLifetime((canonical, image, reference, fresh)) {
        try snaps.append(captureSnapshot("10_iter0_prepare_fresh_image_alive"))
    }
    let encoded = try await ctx.encode(fresh)
    guard encoded == reference else { throw ProbeError("Iter0 prepare_encode mismatch") }
    try withExtendedLifetime((canonical, image, reference, fresh, encoded)) {
        try snaps.append(captureSnapshot("11_iter0_prepare_encode_outputs_alive"))
    }
}

@inline(never)
func runFaithfulLifecycleWithCallerFixtures(
    ctx: HarnessContext,
    warmups: Int,
    iterations: Int,
    snaps: inout [PhaseSnapshot]
) async throws -> Int {
    let canonical = ctx.makeCanonical()
    try withExtendedLifetime(canonical) {
        try snaps.append(captureSnapshot("02_after_canonical_caller_buffer_alive"))
    }
    let image = try ctx.makeImage(canonical: canonical)
    try withExtendedLifetime((canonical, image)) {
        try snaps.append(captureSnapshot("03_after_initial_image_alive"))
    }
    let reference = try await ctx.encode(image)
    let encodedCount = reference.count
    try withExtendedLifetime((canonical, image, reference)) {
        try snaps.append(captureSnapshot("04_after_reference_encode_alive"))
    }

    try await runPreflightAndCapture(
        ctx: ctx, canonical: canonical, image: image, reference: reference, snaps: &snaps
    )
    try withExtendedLifetime((canonical, image, reference)) {
        try snaps.append(captureSnapshot("06_after_preflight_decode_post_release"))
    }

    for _ in 0..<warmups {
        _ = try await ctx.encode(image)
        try await ctx.decodeAndRelease(reference, verify: false)
        if ctx.endToEnd {
            let fresh = try ctx.makeImage(canonical: canonical)
            _ = try await ctx.encode(fresh)
        }
    }
    try withExtendedLifetime((canonical, image, reference)) {
        try snaps.append(captureSnapshot("07_after_interleaved_warmups_post_release"))
    }

    for iter in 0..<iterations {
        if iter == 0 {
            try await runIter0FaithfulEncode(
                ctx: ctx, canonical: canonical, image: image, reference: reference, snaps: &snaps
            )
            try await runIter0FaithfulDecode(
                ctx: ctx, canonical: canonical, image: image, reference: reference, snaps: &snaps
            )
            if ctx.endToEnd {
                try await runIter0FaithfulPrepareAndEncode(
                    ctx: ctx, canonical: canonical, image: image, reference: reference, snaps: &snaps
                )
            } else {
                try withExtendedLifetime((canonical, image, reference)) {
                    try snaps.append(captureSnapshot("10_iter0_prepare_skipped"))
                    try snaps.append(captureSnapshot("11_iter0_prepare_encode_skipped"))
                }
            }
            try withExtendedLifetime((canonical, image, reference)) {
                try snaps.append(captureSnapshot("12_iter0_interleaved_post_release"))
            }
        } else {
            let encoded = try await ctx.encode(image)
            guard encoded == reference else { throw ProbeError("Encode mismatch at iter \(iter)") }
            try await ctx.decodeAndRelease(reference, verify: false)
            if ctx.endToEnd {
                let fresh = try ctx.makeImage(canonical: canonical)
                let encodedFresh = try await ctx.encode(fresh)
                guard encodedFresh == reference else { throw ProbeError("Prepared encode mismatch at iter \(iter)") }
            }
        }
    }
    try withExtendedLifetime((canonical, image, reference)) {
        try snaps.append(captureSnapshot("13_after_all_interleaved_iterations_at_consumer_rusage_point"))
    }

    return encodedCount
}

struct ReadyHandshake: Codable, Sendable {
    let handshake: String
    let pid: Int32
}

struct VMMapDiagnosticReport: Codable, Sendable {
    let mode: String
    let pid: Int32
    let width: Int
    let height: Int
    let bits: Int
    let pattern: String
    let warmups: Int
    let observations: Int
    let end_to_end: Bool
    let canonical_caller_buffer_bytes: Int
    let encoded_bytes: Int
    let snapshot_count: Int
    let snapshots: [PhaseSnapshot]
}

@main struct MemDiagVMMap {
    static func main() async throws {
        var snaps: [PhaseSnapshot] = []
        snaps.reserveCapacity(16)
        try snaps.append(captureSnapshot("01_process_startup"))

        let args = Array(CommandLine.arguments.dropFirst())
        let mode = args.first ?? "faithful-consumer-vmmap"
        guard mode == "faithful-consumer-vmmap" else {
            throw ProbeError("MemDiagVMMap only supports faithful-consumer-vmmap")
        }
        let width = args.count > 1 ? Int(args[1])! : 512
        let height = args.count > 2 ? Int(args[2])! : 512
        let bits = args.count > 3 ? Int(args[3])! : 12
        let pattern = args.count > 4 ? args[4] : "noise"
        let warmups = args.count > 5 ? Int(args[5])! : 5
        let observations = args.count > 6 ? Int(args[6])! : 5
        let handshakeMode = args.count > 7 ? args[7] : "handshake"
        let endToEnd = ProcessInfo.processInfo.environment["SWIFTJLS_BENCHMARK_END_TO_END"] != "0"

        let ctx = try HarnessContext(
            width: width, height: height, bits: bits, pattern: pattern,
            components: 1, near: 0, interleave: 0, endToEnd: endToEnd
        )
        let encodedCount = try await runFaithfulLifecycleWithCallerFixtures(
            ctx: ctx, warmups: warmups, iterations: observations, snaps: &snaps
        )
        // Phase 14 boundary: caller fixtures released; capture counters immediately before external vmmap
        try snaps.append(captureSnapshot("14_before_vmmap_after_caller_fixtures_released"))

        let pid = getpid()
        if handshakeMode == "handshake" {
            let ready = ReadyHandshake(handshake: "READY_FOR_VMMAP", pid: pid)
            let readyData = try JSONEncoder().encode(ready)
            print(String(decoding: readyData, as: UTF8.self))
            fflush(stdout)

            guard let line = readLine()?.trimmingCharacters(in: .whitespacesAndNewlines),
                  line == "RESUME" else {
                throw ProbeError("Expected RESUME on stdin after vmmap handshake")
            }
        } else if handshakeMode != "smoke-no-handshake" {
            throw ProbeError("Unsupported handshake mode: \(handshakeMode)")
        }

        // Phase 15 boundary: capture counters immediately after resuming from external vmmap
        try snaps.append(captureSnapshot("15_after_vmmap_resumed"))
        guard snaps.count == 15 else {
            throw ProbeError("Expected exactly 15 snapshots, got \(snaps.count)")
        }

        let report = VMMapDiagnosticReport(
            mode: mode,
            pid: pid,
            width: width,
            height: height,
            bits: bits,
            pattern: pattern,
            warmups: warmups,
            observations: observations,
            end_to_end: endToEnd,
            canonical_caller_buffer_bytes: endToEnd ? (width * height * 2) : 0,
            encoded_bytes: encodedCount,
            snapshot_count: snaps.count,
            snapshots: snaps
        )
        let data = try JSONEncoder().encode(report)
        print(String(decoding: data, as: UTF8.self))
        fflush(stdout)
    }
}
