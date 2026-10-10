// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

/// Operation-local, monotonic admission and cancellation budget. No shared state.
struct CodecBudget {
    let limits: ResourceLimits
    let started = ProcessInfo.processInfo.systemUptime
    func check() throws {
        try Task.checkCancellation()
        guard ProcessInfo.processInfo.systemUptime - started < limits.deadlineSeconds else {
            throw CodecError(.resourceLimitExceeded, "Codec operation deadline exceeded.")
        }
    }
    func admit(pixelBytes: Int, workspaceBytes: Int, compressedBytes: Int) throws {
        guard pixelBytes <= limits.maximumDecodedBytes,
              workspaceBytes <= limits.maximumWorkspaceBytes,
              compressedBytes <= limits.maximumCompressedBytes,
              try checkedAdd(checkedAdd(pixelBytes, workspaceBytes), compressedBytes) <= limits.maximumMemoryBytes else {
            throw CodecError(.resourceLimitExceeded, "Codec operation exceeds its memory budget.")
        }
        try check()
    }
}

/// Bounded JPEG-LS frame/scan directory. Sample interpretation is only inferred
/// for a single grey component; RGB requires an explicit supported SPIFF header.
struct JPEGLSHeader {
    struct Scan {
        let components: [Int]
        let near: Int
        let interleave: JPEGLSInterleaveMode
        let parameters: JPEGLSPresetParameters
        let ranges: [Range<Int>]
        let restartInterval: Int
    }
    let width: Int, height: Int, bits: Int
    let componentIDs: [UInt8]
    let rgb: Bool
    let records: [Scan]
    var near: Int { records[0].near }
    var parameters: JPEGLSPresetParameters { records[0].parameters }
    var scans: [Range<Int>] { records[0].ranges }
    var restartInterval: Int { records[0].restartInterval }
    var scan: Range<Int> { scans[0] }
    var roles: [ComponentRole] {
        if componentIDs.count == 1 { return [.grey] }
        if rgb { return [.red, .green, .blue] }
        return componentIDs.map { .uninterpreted("JPEG-LS:\($0)") }
    }
    func descriptor(limits: ResourceLimits) throws -> ImageDescriptor {
        if componentIDs.count == 1 {
            return try .greyscale16(width: width, height: height, meaningfulBits: bits, limits: limits)
        }
        let rowBytes = try checkedMultiply(width, 2)
        let planeBytes = try checkedMultiply(rowBytes, height)
        let total = try checkedMultiply(planeBytes, componentIDs.count)
        guard total <= limits.maximumDecodedBytes, total <= limits.maximumMemoryBytes else {
            throw CodecError(.resourceLimitExceeded, "Component storage exceeds the memory budget.")
        }
        let planes = try componentIDs.indices.map { i in
            try PlaneDescriptor(width: width, height: height, components: [i],
                offset: i * planeBytes, rowBytes: rowBytes, byteCount: (i + 1) * planeBytes)
        }
        return try ImageDescriptor(width: width, height: height, meaningfulBits: bits,
            components: roles, colour: rgb ? .rgb : .unknown, planes: planes, limits: limits)
    }

    static func parse(_ data: Data, budget: CodecBudget) throws -> Self {
        try budget.admit(pixelBytes: 0, workspaceBytes: 0, compressedBytes: data.count)
        return try data.withUnsafeBytes { (bytes: UnsafeRawBufferPointer) in
            func malformed() -> CodecError { .init(.malformedInput, "Invalid or truncated JPEG-LS header.") }
            func unsupported(_ message: String) -> CodecError { .init(.unsupportedFeature, message) }
            func word(_ offset: Int) -> Int { Int(bytes[offset]) << 8 | Int(bytes[offset + 1]) }
            func longWord(_ offset: Int) -> Int { word(offset) << 16 | word(offset + 2) }
            guard bytes.count >= 2, bytes[0] == 255, bytes[1] == 216 else {
                throw CodecError(.unsupportedFormat, "Input is not a JPEG-LS codestream.")
            }
            var cursor = 2
            var frame: (width: Int, height: Int, bits: Int, ids: [UInt8])?
            var preset: [Int]?
            var restartInterval = 0, hasRestartDefinition = false
            var records: [Scan] = []
            var covered = Set<Int>()
            var spiff: (width: Int, height: Int, bits: Int, components: Int, rgb: Bool)?
            var needsDirectoryEnd = false
            while cursor < bytes.count {
                try budget.check()
                guard bytes[cursor] == 255 else { throw malformed() }
                repeat { cursor += 1; if cursor & 4095 == 0 { try budget.check() } }
                while cursor < bytes.count && bytes[cursor] == 255
                guard cursor < bytes.count else { throw malformed() }
                let marker = bytes[cursor]; cursor += 1
                if marker == 0xd9 {
                    guard let f = frame, !records.isEmpty, covered.count == f.ids.count,
                          cursor == bytes.count, !needsDirectoryEnd else { throw malformed() }
                    let header = Self(width: f.width, height: f.height, bits: f.bits,
                        componentIDs: f.ids, rgb: spiff?.rgb ?? false, records: records)
                    _ = try header.descriptor(limits: budget.limits)
                    return header
                }
                guard bytes.count - cursor >= 2 else { throw malformed() }
                let length = word(cursor)
                guard length >= 2, length <= bytes.count - cursor else { throw malformed() }
                let payload = cursor + 2, end = cursor + length
                if needsDirectoryEnd {
                    guard marker == 0xe8, length == 8,
                          longWord(payload) == 1, bytes[payload + 4] == 255, bytes[payload + 5] == 216 else {
                        throw unsupported("Only the empty SPIFF directory is implemented.")
                    }
                    needsDirectoryEnd = false
                    cursor = end
                    continue
                }
                switch marker {
                case 0xe8:
                    guard frame == nil, spiff == nil, length == 32,
                          Array(bytes[payload..<(payload + 6)]) == [83, 80, 73, 70, 70, 0],
                          bytes[payload + 6] == 2, bytes[payload + 7] == 0,
                          bytes[payload + 8] == 0, bytes[payload + 20] == 6,
                          bytes[payload + 21] == 0, longWord(payload + 22) == 1,
                          longWord(payload + 26) == 1 else {
                        throw unsupported("Unsupported JPEG-LS application metadata or SPIFF profile.")
                    }
                    guard budget.limits.maximumMetadataBytes >= 30 else {
                        throw CodecError(.resourceLimitExceeded, "SPIFF header exceeds the metadata budget.")
                    }
                    let count = Int(bytes[payload + 9]), colour = bytes[payload + 18]
                    guard (count == 3 && colour == 10) || (count == 1 && colour == 8) else {
                        throw unsupported("Only grey and RGB SPIFF interpretation is implemented.")
                    }
                    spiff = (longWord(payload + 14), longWord(payload + 10), Int(bytes[payload + 19]), count, colour == 10)
                    needsDirectoryEnd = true
                case 0xf7:
                    guard frame == nil, length >= 8 else { throw malformed() }
                    let count = Int(bytes[payload + 5])
                    guard (1...4).contains(count) else { throw unsupported("Only one to four unsubsampled components are implemented.") }
                    guard length == 8 + count * 3 else { throw malformed() }
                    let bits = Int(bytes[payload]), height = word(payload + 1), width = word(payload + 3)
                    guard (2...16).contains(bits), width > 0, height > 0 else { throw malformed() }
                    _ = try ImageDescriptor.greyscale16(width: width, height: height, meaningfulBits: bits, limits: budget.limits)
                    let imageBytes = try checkedMultiply(checkedMultiply(width, height), count * 2)
                    guard imageBytes <= budget.limits.maximumDecodedBytes, imageBytes <= budget.limits.maximumMemoryBytes else {
                        throw CodecError(.resourceLimitExceeded, "Component storage exceeds the memory budget.")
                    }
                    var ids: [UInt8] = []
                    for i in 0..<count {
                        let at = payload + 6 + 3 * i
                        guard bytes[at + 1] == 0x11, bytes[at + 2] == 0 else {
                            throw unsupported("Subsampled JPEG-LS components are not implemented.")
                        }
                        guard !ids.contains(bytes[at]) else { throw malformed() }
                        ids.append(bytes[at])
                    }
                    if let s = spiff {
                        guard s.width == width, s.height == height, s.bits == bits, s.components == count else { throw malformed() }
                    }
                    frame = (width, height, bits, ids)
                case 0xf8:
                    guard length == 13, bytes[payload] == 1, preset == nil else {
                        throw unsupported("JPEG-LS extension is not implemented.")
                    }
                    preset = stride(from: payload + 1, to: end, by: 2).map { word($0) }
                case 0xdd:
                    guard length == 4, !hasRestartDefinition else { throw malformed() }
                    restartInterval = word(payload); hasRestartDefinition = true
                case 0xda:
                    guard let f = frame, length >= 6 else { throw malformed() }
                    let count = Int(bytes[payload])
                    guard count > 0, count <= f.ids.count, length == 6 + 2 * count else { throw malformed() }
                    var indices: [Int] = []
                    for i in 0..<count {
                        guard let component = f.ids.firstIndex(of: bytes[payload + 1 + 2 * i]),
                              !covered.contains(component), !indices.contains(component) else { throw malformed() }
                        guard bytes[payload + 2 + 2 * i] == 0 else { throw unsupported("Mapping tables are not implemented.") }
                        indices.append(component)
                    }
                    let near = Int(bytes[payload + 1 + 2 * count])
                    guard let interleave = JPEGLSInterleaveMode(rawValue: bytes[payload + 2 + 2 * count]),
                          bytes[payload + 3 + 2 * count] == 0 else {
                        throw unsupported("Unsupported scan interleave or point transform.")
                    }
                    guard (interleave == .none && count == 1) || (interleave != .none && count > 1) else { throw malformed() }
                    guard restartInterval == 0 || interleave == .none else {
                        throw unsupported("Restart markers require non-interleaved scans.")
                    }
                    guard records.isEmpty || near == records[0].near else {
                        throw unsupported("Different NEAR values across component scans are not implemented.")
                    }
                    let maximum = (1 << f.bits) - 1
                    let declared = preset.map { $0[0] == 0 ? maximum : $0[0] } ?? maximum
                    guard declared <= maximum else { throw malformed() }
                    let defaults = try JPEGLSPresetParameters.defaultParameters(maxValue: declared, near: near)
                    let params: JPEGLSPresetParameters
                    if let p = preset {
                        params = try JPEGLSPresetParameters(maxValue: p[0] == 0 ? defaults.maxValue : p[0],
                            threshold1: p[1] == 0 ? defaults.threshold1 : p[1], threshold2: p[2] == 0 ? defaults.threshold2 : p[2],
                            threshold3: p[3] == 0 ? defaults.threshold3 : p[3], reset: p[4] == 0 ? defaults.reset : p[4])
                        guard params.threshold1 > near else { throw malformed() }
                    } else { params = defaults }
                    let expected = restartInterval > 0 ? (f.height + restartInterval - 1) / restartInterval : 1
                    try budget.admit(pixelBytes: 0, workspaceBytes: checkedMultiply(checkedMultiply(expected, f.ids.count), MemoryLayout<Range<Int>>.stride * 2), compressedBytes: data.count)
                    var ranges: [Range<Int>] = [], scanStart = end
                    while true {
                        var scanEnd = scanStart
                        while scanEnd + 1 < bytes.count {
                            if scanEnd & 4095 == 0 { try budget.check() }
                            if bytes[scanEnd] == 255 && bytes[scanEnd + 1] >= 128 { break }
                            scanEnd += 1
                        }
                        var terminal = scanEnd
                        while terminal < bytes.count && bytes[terminal] == 255 {
                            terminal += 1; if terminal & 4095 == 0 { try budget.check() }
                        }
                        guard terminal < bytes.count, scanEnd > scanStart, ranges.count < expected else { throw malformed() }
                        ranges.append(scanStart..<scanEnd)
                        if ranges.count == expected {
                            guard !(0xd0...0xd7).contains(bytes[terminal]) else { throw malformed() }
                            cursor = scanEnd
                            break
                        }
                        guard bytes[terminal] == 0xd0 + UInt8((ranges.count - 1) % 8) else { throw malformed() }
                        scanStart = terminal + 1
                    }
                    records.append(Scan(components: indices, near: near, interleave: interleave,
                        parameters: params, ranges: ranges, restartInterval: restartInterval))
                    covered.formUnion(indices)
                    continue
                default:
                    throw unsupported("JPEG-LS marker or metadata is not implemented.")
                }
                cursor = end
            }
            throw malformed()
        }
    }
}
