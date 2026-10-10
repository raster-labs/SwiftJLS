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
    let sampling: [UInt8]
    let rgb: Bool
    let grey: Bool
    let colourTransform: CodecOptions.ColourTransform
    let records: [Scan]
    let metadata: ImageMetadata
    let mapping: JPEGLSMappingTables?
    let outputBits: Int
    let mapsSamples: Bool
    let metadataBytes: Int
    var near: Int { records.reduce(0) { max($0, $1.near) } }
    var parameters: JPEGLSPresetParameters { records[0].parameters }
    var scans: [Range<Int>] { records[0].ranges }
    var restartInterval: Int { records[0].restartInterval }
    var scan: Range<Int> { scans[0] }
    var roles: [ComponentRole] {
        if grey { return [.grey] }
        if rgb { return [.red, .green, .blue] }
        return componentIDs.map { .uninterpreted("JPEG-LS:\($0)") }
    }
    func descriptor(limits: ResourceLimits) throws -> ImageDescriptor {
        if grey {
            return try .greyscale16(width: width, height: height, meaningfulBits: outputBits, limits: limits)
        }
        let hMax = sampling.map { Int($0 >> 4) }.max() ?? 1
        let vMax = sampling.map { Int($0 & 15) }.max() ?? 1
        var end = 0
        let planes = try componentIDs.indices.map { i in
            let h = Int(sampling[i] >> 4), v = Int(sampling[i] & 15)
            let w = try checkedAdd(checkedMultiply(width, h), hMax - 1) / hMax
            let rows = try checkedAdd(checkedMultiply(height, v), vMax - 1) / vMax
            let rowBytes = try checkedMultiply(w, 2)
            let start = end; end = try checkedAdd(end, checkedMultiply(rowBytes, rows))
            return try PlaneDescriptor(width: w, height: rows, components: [i], offset: start,
                rowBytes: rowBytes, byteCount: end, horizontalSamplingFactor: h, verticalSamplingFactor: v)
        }
        return try ImageDescriptor(width: width, height: height, meaningfulBits: outputBits,
            components: roles, colour: rgb ? .rgb : .unknown, planes: planes, limits: limits)
    }

    func retainedMetadata(_ policy: MetadataPolicy) -> ImageMetadata {
        if policy == .preserve { return metadata }
        return ImageMetadata(entries: metadata.entries.filter { metadata.requiredKeys.contains($0.key) }, requiredKeys: metadata.requiredKeys)
    }
    func mapSamples(in bytes: UnsafeMutableRawBufferPointer, descriptor: ImageDescriptor, budget: CodecBudget) throws {
        guard mapsSamples, let mapping else { return }
        for (component, id) in mapping.componentTableIDs.enumerated() where id != 0 {
            guard let table = mapping.tables.first(where: { $0.id == id }),
                  let plane = descriptor.planes.first(where: { $0.components.contains(component) }),
                  let position = plane.components.firstIndex(of: component) else {
                throw CodecError(.internalFailure, "Mapping component unavailable.")
            }
            let view = ComponentSampleWriter(bytes: bytes, width: plane.width, height: plane.height,
                offset: plane.offset + position * plane.sampleStride, rowBytes: plane.rowBytes,
                pixelStride: plane.pixelStride, sampleBytes: descriptor.storageBits / 8,
                littleEndian: descriptor.byteOrder == .littleEndian)
            for index in 0..<view.count {
                if index & 255 == 0 { try budget.check() }
                let sample = Int(view[index])
                guard sample < table.count else { throw CodecError(.malformedInput, "Mapping index is out of range.") }
                view[index] = table.sample(sample)
            }
        }
    }
    func fidelity(budget: CodecBudget) throws -> Fidelity {
        if near > 0 && colourTransform != .none { return .boundedError((1 << outputBits) - 1) }
        guard near > 0 else { return .exactSamples }
        guard mapsSamples, let mapping else { return .boundedError(near) }
        // NEAR bounds index error. A nonlinear lookup requires a separately
        // derived output bound; never report the index bound for mapped samples.
        var bound = mapping.componentTableIDs.contains(0) ? near : 0
        for table in mapping.tables where mapping.componentTableIDs.contains(table.id) {
            for i in 0..<table.count {
                if i & 63 == 0 { try budget.check() }
                for j in i..<min(table.count, i + near + 1) {
                    bound = max(bound, abs(Int(table.sample(i)) - Int(table.sample(j))))
                }
            }
        }
        return bound == 0 ? .exactSamples : .boundedError(bound)
    }

    static func parse(_ data: Data, budget: CodecBudget, codecOptions: CodecOptions = .init()) throws -> Self {
        try budget.admit(pixelBytes: 0, workspaceBytes: 0, compressedBytes: data.count)
        return try data.withUnsafeBytes { (bytes: UnsafeRawBufferPointer) in
            func malformed() -> CodecError { .init(.malformedInput, "Invalid or truncated JPEG-LS header.") }
            func unsupported(_ message: String) -> CodecError { .init(.unsupportedFeature, message) }
            func word(_ offset: Int) -> Int { Int(bytes[offset]) << 8 | Int(bytes[offset + 1]) }
            func longWord(_ offset: Int) -> UInt32 { UInt32(word(offset)) << 16 | UInt32(word(offset + 2)) }
            guard bytes.count >= 2, bytes[0] == 255, bytes[1] == 216 else {
                throw CodecError(.unsupportedFormat, "Input is not a JPEG-LS codestream.")
            }
            var cursor = 2
            var frame: (width: Int, height: Int, bits: Int, ids: [UInt8], sampling: [UInt8])?
            var preset: [Int]?
            var extendedSize: (width: Int, height: Int)?
            var restartInterval = 0
            var records: [Scan] = []
            var covered = Set<Int>()
            var spiff: (width: Int, height: Int, bits: Int, components: Int, rgb: Bool, grey: Bool)?
            var needsDirectoryEnd = false
            var spiffData = Data()
            var transform: CodecOptions.ColourTransform?
            var metadataBytes = 0, directoryBytes = 0
            var ancillary: [JPEGLSMetadata.Segment] = []
            var tables: [UInt8: JPEGLSMappingTable] = [:]
            var selectors: [UInt8] = []
            var continuationID: UInt8?
            func charge(_ count: Int) throws {
                metadataBytes = try checkedAdd(metadataBytes, count)
                guard metadataBytes <= budget.limits.maximumMetadataBytes else {
                    throw CodecError(.resourceLimitExceeded, "JPEG-LS metadata limit exceeded.")
                }
                try budget.admit(pixelBytes: 0, workspaceBytes: checkedAdd(checkedMultiply(metadataBytes, 32), directoryBytes), compressedBytes: data.count)
            }
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
                    let mapping = try tables.isEmpty ? nil : JPEGLSMappingTables(tables: Array(tables.values), componentTableIDs: selectors)
                    let outputBits = codecOptions.mappingOutputPrecision ?? f.bits
                    let legacyMappedHP = codecOptions.hpInterpretation == .legacyJLSwift && transform != nil && transform != CodecOptions.ColourTransform.none
                    let mapsSamples = (codecOptions.mappingOutputPrecision != nil || legacyMappedHP) && selectors.contains(where: { $0 != 0 })
                    if mapsSamples {
                        guard !legacyMappedHP || outputBits >= f.bits else { throw unsupported("Legacy HP output precision must hold the inverse transform range.") }
                        for id in selectors {
                            if id == 0 {
                                guard outputBits >= f.bits else { throw unsupported("Unmapped components do not fit the requested precision.") }
                            } else if let table = tables[id] {
                                guard table.entryWidth <= 2 else { throw unsupported("Unsigned interpretation requires one- or two-byte table entries.") }
                                for index in 0..<table.count {
                                    if index & 255 == 0 { try budget.check() }
                                    guard Int(table.sample(index)) < (1 << outputBits) else {
                                        throw unsupported("Mapping table values exceed requested output precision.")
                                    }
                                }
                            }
                        }
                    }
                    var metadata = JPEGLSMetadata(segments: ancillary).metadata
                    if !spiffData.isEmpty {
                        if mapsSamples { spiffData[23] = UInt8(outputBits) }
                        metadata = ImageMetadata(entries: metadata.entries.merging([JPEGLSMetadata.spiffKey: spiffData]) { _, new in new },
                            requiredKeys: spiff?.rgb == false && spiff?.grey == false ? [JPEGLSMetadata.spiffKey] : [])
                    }
                    if let mapping, !mapsSamples {
                        metadata = ImageMetadata(entries: metadata.entries.merging(mapping.metadata.entries) { _, new in new }, requiredKeys: metadata.requiredKeys.union([JPEGLSMappingTables.key]))
                    }
                    let retainedBytes = try metadata.validate(limits: budget.limits)
                    let header = Self(width: f.width, height: f.height, bits: f.bits,
                        componentIDs: f.ids, sampling: f.sampling, rgb: spiff?.rgb ?? (transform.map { $0 != .none } ?? false),
                        grey: spiff?.grey ?? (f.ids.count == 1),
                        colourTransform: transform ?? .none, records: records, metadata: metadata, mapping: mapping,
                        outputBits: mapsSamples ? outputBits : f.bits, mapsSamples: mapsSamples, metadataBytes: max(metadataBytes, retainedBytes))
                    let descriptor = try header.descriptor(limits: budget.limits)
                    try budget.admit(pixelBytes: descriptor.requiredByteCount, workspaceBytes: checkedAdd(checkedMultiply(header.metadataBytes, 32), directoryBytes), compressedBytes: data.count)
                    return header
                }
                guard bytes.count - cursor >= 2 else { throw malformed() }
                let length = word(cursor)
                guard length >= 2, length <= bytes.count - cursor else { throw malformed() }
                let payload = cursor + 2, end = cursor + length
                if needsDirectoryEnd {
                    guard marker == 0xe8, length >= 6 else { throw malformed() }
                    try charge(length + 2)
                    spiffData.append(contentsOf: [255, 232]); spiffData.append(contentsOf: bytes[cursor..<end])
                    if longWord(payload) == 1 {
                        guard length == 8, bytes[payload + 4] == 255, bytes[payload + 5] == 216 else { throw malformed() }
                        needsDirectoryEnd = false
                    }
                    cursor = end
                    continue
                }
                if marker != 0xf8 || length < 3 || bytes[payload] != 3 { continuationID = nil }
                switch marker {
                case 0xe8:
                    if length == 7, Array(bytes[payload..<(payload + 4)]) == [109, 114, 102, 120] {
                        guard transform == nil, records.isEmpty else { throw malformed() }
                        guard let value = CodecOptions.ColourTransform(rawValue: bytes[payload + 4]) else {
                            throw unsupported("Unknown HP colour transform.")
                        }
                        metadataBytes = try checkedAdd(metadataBytes, 5)
                        guard metadataBytes <= budget.limits.maximumMetadataBytes else {
                            throw CodecError(.resourceLimitExceeded, "Application headers exceed metadata budget.")
                        }
                        transform = value
                        break
                    }
                    if length < 8 || Array(bytes[payload..<(payload + 6)]) != [83, 80, 73, 70, 70, 0] {
                        // An APP8 payload that starts with mrfx is a malformed
                        // interpretation marker, never opaque ancillary data.
                        guard length < 6 || Array(bytes[payload..<(payload + 4)]) != [109, 114, 102, 120] else { throw malformed() }
                        try charge(length + 1)
                        ancillary.append(try .init(marker: marker, payload: Data(bytes[payload..<end])))
                        break
                    }
                    guard frame == nil, spiff == nil, length == 32,
                          Array(bytes[payload..<(payload + 6)]) == [83, 80, 73, 70, 70, 0],
                          bytes[payload + 6] == 2, bytes[payload + 7] == 0,
                          bytes[payload + 20] == 6,
                          bytes[payload + 21] <= 2, longWord(payload + 22) > 0,
                          longWord(payload + 26) > 0 else {
                        throw unsupported("Unsupported JPEG-LS application metadata or SPIFF profile.")
                    }
                    metadataBytes = try checkedAdd(metadataBytes, 30)
                    guard budget.limits.maximumMetadataBytes >= metadataBytes else {
                        throw CodecError(.resourceLimitExceeded, "SPIFF header exceeds the metadata budget.")
                    }
                    let count = Int(bytes[payload + 9]), colour = bytes[payload + 18]
                    guard (1...4).contains(count), (colour != 10 || count == 3), (colour != 8 || count == 1) else { throw malformed() }
                    guard let spiffWidth = Int(exactly: longWord(payload + 14)),
                          let spiffHeight = Int(exactly: longWord(payload + 10)) else {
                        throw CodecError(.resourceLimitExceeded, "SPIFF dimensions exceed native addressable limits.")
                    }
                    spiff = (spiffWidth, spiffHeight, Int(bytes[payload + 19]), count, colour == 10, colour == 8)
                    spiffData.append(contentsOf: [255, 232]); spiffData.append(contentsOf: bytes[cursor..<end])
                    needsDirectoryEnd = true
                case 0xf7:
                    guard frame == nil, length >= 8 else { throw malformed() }
                    let count = Int(bytes[payload + 5])
                    guard (1...4).contains(count) else { throw unsupported("Only one to four components are implemented.") }
                    guard length == 8 + count * 3 else { throw malformed() }
                    let bits = Int(bytes[payload])
                    let codedHeight = word(payload + 1), codedWidth = word(payload + 3)
                    let height = codedHeight == 0 ? extendedSize?.height ?? 0 : codedHeight
                    let width = codedWidth == 0 ? extendedSize?.width ?? 0 : codedWidth
                    if let size = extendedSize {
                        guard size.width == width, size.height == height else { throw malformed() }
                    }
                    guard (2...16).contains(bits) else { throw malformed() }
                    if width > 0 && height > 0 {
                        _ = try ImageDescriptor.greyscale16(width: width, height: height, meaningfulBits: bits, limits: budget.limits)
                    }
                    let imageBytes = try checkedMultiply(checkedMultiply(width, height), count * 2)
                    guard imageBytes <= budget.limits.maximumDecodedBytes, imageBytes <= budget.limits.maximumMemoryBytes else {
                        throw CodecError(.resourceLimitExceeded, "Component storage exceeds the memory budget.")
                    }
                    var ids: [UInt8] = [], sampling: [UInt8] = []
                    for i in 0..<count {
                        let at = payload + 6 + 3 * i
                        guard (1...4).contains(bytes[at + 1] >> 4), (1...4).contains(bytes[at + 1] & 15), bytes[at + 2] == 0 else { throw malformed() }
                        sampling.append(bytes[at + 1])
                        guard !ids.contains(bytes[at]) else { throw malformed() }
                        ids.append(bytes[at])
                    }
                    if let s = spiff, width > 0, height > 0 {
                        guard s.width == width, s.height == height, s.bits == bits, s.components == count else { throw malformed() }
                    }
                    frame = (width, height, bits, ids, sampling)
                    selectors = Array(repeating: 0, count: count)
                case 0xf8:
                    guard length >= 3 else { throw malformed() }
                    if bytes[payload] == 1 {
                        guard length == 13 else { throw malformed() }
                        preset = stride(from: payload + 1, to: end, by: 2).map { word($0) }
                    } else if bytes[payload] == 2 || bytes[payload] == 3 {
                        let continuation = bytes[payload] == 3
                        let legacy = continuation && codecOptions.legacyMappingContinuations
                        guard length >= (legacy ? 5 : 6) else { throw malformed() }
                        let id = bytes[payload + 1]
                        let width = legacy ? tables[id]?.entryWidth ?? 0 : Int(bytes[payload + 2])
                        guard id != 0, width > 0 else { throw malformed() }
                        let start = payload + (legacy ? 2 : 3)
                        guard (end - start) % width == 0 else { throw malformed() }
                        if continuation {
                            guard continuationID == id, tables[id]?.entryWidth == width else { throw malformed() }
                        } else {
                            // A referenced table cannot be replaced after its scan:
                            // retaining a single final table would change its meaning.
                            guard tables[id] == nil else { throw unsupported("Mapping table redefinition is not implemented.") }
                        }
                        let previous = continuation ? tables[id]?.data.count ?? 0 : 0
                        guard (previous + end - start) / width <= 65536 else { throw malformed() }
                        try charge(end - start + (continuation ? 0 : 6))
                        var tableData = continuation ? tables[id]?.data ?? Data() : Data()
                        tableData.append(contentsOf: bytes[start..<end])
                        tables[id] = try JPEGLSMappingTable(id: id, entryWidth: width, data: tableData)
                        continuationID = id
                    } else if bytes[payload] == 4 {
                        guard length >= 8, records.isEmpty, extendedSize == nil else { throw malformed() }
                        let size = Int(bytes[payload + 1])
                        guard (2...4).contains(size), length == 4 + 2 * size else { throw malformed() }
                        func dimension(_ start: Int) throws -> Int {
                            var value: UInt32 = 0
                            for offset in 0..<size { value = (value << 8) | UInt32(bytes[start + offset]) }
                            guard let result = Int(exactly: value) else {
                                throw CodecError(.resourceLimitExceeded, "Extended dimensions exceed native addressable limits.")
                            }
                            return result
                        }
                        let first = try dimension(payload + 2), second = try dimension(payload + 2 + size)
                        let width = codecOptions.legacyExtendedDimensions ? first : second
                        let height = codecOptions.legacyExtendedDimensions ? second : first
                        _ = try ImageDescriptor.greyscale16(width: width, height: height, limits: budget.limits)
                        extendedSize = (width, height)
                        if var f = frame {
                            guard (f.width == 0 || f.width == width), (f.height == 0 || f.height == height) else { throw malformed() }
                            f.width = width; f.height = height; frame = f
                        }
                    } else { throw unsupported("JPEG-LS extension is not implemented.") }
                case 0xdd:
                    guard (4...6).contains(length) else { throw malformed() }
                    var wireInterval: UInt32 = 0
                    for i in payload..<end { wireInterval = (wireInterval << 8) | UInt32(bytes[i]) }
                    // An interval beyond native Int.max is also beyond every
                    // representable frame height, so it still describes one scan.
                    restartInterval = Int(clamping: wireInterval)
                case 0xda:
                    guard let f = frame, length >= 6, f.width > 0, f.height > 0 else { throw malformed() }
                    _ = try ImageDescriptor.greyscale16(width: f.width, height: f.height, meaningfulBits: f.bits, limits: budget.limits)
                    if let s = spiff {
                        guard s.width == f.width, s.height == f.height, s.bits == f.bits, s.components == f.ids.count else { throw malformed() }
                    }
                    let count = Int(bytes[payload])
                    guard count > 0, count <= f.ids.count, length == 6 + 2 * count else { throw malformed() }
                    var indices: [Int] = []
                    for i in 0..<count {
                        guard let component = f.ids.firstIndex(of: bytes[payload + 1 + 2 * i]),
                              !covered.contains(component), !indices.contains(component) else { throw malformed() }
                        selectors[component] = bytes[payload + 2 + 2 * i]
                        indices.append(component)
                    }
                    let near = Int(bytes[payload + 1 + 2 * count])
                    guard let interleave = JPEGLSInterleaveMode(rawValue: bytes[payload + 2 + 2 * count]),
                          bytes[payload + 3 + 2 * count] == 0 else {
                        throw unsupported("Unsupported scan interleave or point transform.")
                    }
                    guard (interleave == .none && count == 1) || (interleave != .none && count > 1) else { throw malformed() }
                    if Set(f.sampling).count > 1 {
                        guard interleave == .line, count == f.ids.count, restartInterval == 0,
                              transform == nil || transform == CodecOptions.ColourTransform.none else {
                            throw unsupported("Subsampled decoding requires one line-interleaved scan without HP or restarts.")
                        }
                    }
                    guard restartInterval == 0 || interleave == .none else {
                        throw unsupported("Restart markers require non-interleaved scans.")
                    }
                    if let transform, transform != .none {
                        let legacy = codecOptions.hpInterpretation == .legacyJLSwift
                        guard f.ids.count == 3,
                              legacy || ([8, 16].contains(f.bits) && near == 0 && interleave != .none),
                              (interleave == .none && legacy) || indices == [0, 1, 2],
                              spiff == nil || spiff?.rgb == true else {
                            throw unsupported("HP transforms require lossless full-range 8/16-bit interleaved RGB.")
                        }
                    }
                    let maximum = (1 << f.bits) - 1
                    let declared = preset.map { $0[0] == 0 ? maximum : $0[0] } ?? maximum
                    guard declared <= maximum else { throw malformed() }
                    var defaults = try JPEGLSPresetParameters.defaultParameters(maxValue: declared, near: near)
                    if declared < 128 && (codecOptions.legacyPresetDefaults || codecOptions.hpInterpretation == .legacyJLSwift) {
                        // Pinned predecessor's nonstandard low-range default formula.
                        let factor = (256 + declared / 2) / (declared + 1)
                        let t1 = min(max(factor + 2 + 3 * near, near + 1), declared)
                        let t2 = min(max(factor * 4 + 3 + 5 * near, t1), declared)
                        let t3 = min(max(factor * 17 + 4 + 7 * near, t2), declared)
                        defaults = try .init(maxValue: declared, threshold1: t1, threshold2: t2, threshold3: t3, reset: 64)
                    }
                    let params: JPEGLSPresetParameters
                    if let p = preset {
                        params = try JPEGLSPresetParameters(maxValue: p[0] == 0 ? defaults.maxValue : p[0],
                            threshold1: p[1] == 0 ? defaults.threshold1 : p[1], threshold2: p[2] == 0 ? defaults.threshold2 : p[2],
                            threshold3: p[3] == 0 ? defaults.threshold3 : p[3], reset: p[4] == 0 ? defaults.reset : p[4])
                        guard params.threshold1 > near else { throw malformed() }
                    } else { params = defaults }
                    if let transform, transform != .none, params.maxValue != maximum {
                        throw unsupported("HP transforms require the full sample range.")
                    }
                    for component in indices where selectors[component] != 0 {
                        guard let table = tables[selectors[component]], table.count == params.maxValue + 1 else { throw malformed() }
                        guard transform == nil || transform == CodecOptions.ColourTransform.none || codecOptions.hpInterpretation == .legacyJLSwift else { throw unsupported("Mapping tables with HP require explicit predecessor interpretation.") }
                    }
                    let expected = restartInterval > 0 ? 1 + (f.height - 1) / restartInterval : 1
                    directoryBytes = try checkedAdd(directoryBytes, checkedMultiply(expected, MemoryLayout<Range<Int>>.stride * 2))
                    try budget.admit(pixelBytes: 0, workspaceBytes: checkedAdd(directoryBytes, checkedMultiply(metadataBytes, 32)), compressedBytes: data.count)
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
                case 0xe0...0xe7, 0xe9...0xef, 0xfe:
                    try charge(length + 1)
                    ancillary.append(try .init(marker: marker, payload: Data(bytes[payload..<end])))
                default:
                    throw unsupported("JPEG-LS marker or metadata is not implemented.")
                }
                cursor = end
            }
            throw malformed()
        }
    }
}
