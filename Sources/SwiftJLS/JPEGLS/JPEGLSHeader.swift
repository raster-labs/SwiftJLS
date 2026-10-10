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

/// Bounded single-component header reader. The format extensions are admitted
/// explicitly as their migrated paths become independently qualified.
struct JPEGLSHeader {
    let width: Int, height: Int, bits: Int, near: Int
    let parameters: JPEGLSPresetParameters
    let scans: [Range<Int>]
    let restartInterval: Int
    var scan: Range<Int> { scans[0] }

    static func parse(_ data: Data, budget: CodecBudget) throws -> Self {
        try budget.admit(pixelBytes: 0, workspaceBytes: 0, compressedBytes: data.count)
        return try data.withUnsafeBytes { (bytes: UnsafeRawBufferPointer) in
            guard bytes.count >= 2, bytes[0] == 255, bytes[1] == 216 else {
                throw CodecError(.unsupportedFormat, "Input is not a JPEG-LS codestream.")
            }
            var cursor = 2
            var frame: (width: Int, height: Int, bits: Int, id: UInt8)?
            var preset: [Int]?
            var restartInterval = 0
            var hasRestartDefinition = false
            func malformed() -> CodecError { CodecError(.malformedInput, "Invalid or truncated JPEG-LS header.") }
            func word(_ offset: Int) -> Int { Int(bytes[offset]) << 8 | Int(bytes[offset + 1]) }
            while cursor < bytes.count {
                try budget.check()
                guard bytes[cursor] == 255 else { throw malformed() }
                repeat { cursor += 1; if cursor & 4095 == 0 { try budget.check() } }
                while cursor < bytes.count && bytes[cursor] == 255
                guard cursor < bytes.count else { throw malformed() }
                let marker = bytes[cursor]; cursor += 1
                guard bytes.count - cursor >= 2 else { throw malformed() }
                let length = word(cursor)
                guard length >= 2, length <= bytes.count - cursor else { throw malformed() }
                let payload = cursor + 2, end = cursor + length
                switch marker {
                case 0xf7:
                    guard frame == nil, length == 11, bytes[payload + 5] == 1,
                          bytes[payload + 7] == 0x11, bytes[payload + 8] == 0 else {
                        throw CodecError(.unsupportedFeature, "Only a single unsubsampled JPEG-LS component is currently implemented.")
                    }
                    let bits = Int(bytes[payload]), height = word(payload + 1), width = word(payload + 3)
                    guard (2...16).contains(bits), width > 0, height > 0 else { throw malformed() }
                    _ = try ImageDescriptor.greyscale16(width: width, height: height, meaningfulBits: bits, limits: budget.limits)
                    frame = (width, height, bits, bytes[payload + 6])
                case 0xf8:
                    guard length == 13, bytes[payload] == 1, preset == nil else {
                        throw CodecError(.unsupportedFeature, "JPEG-LS extension is not implemented.")
                    }
                    preset = stride(from: payload + 1, to: end, by: 2).map { word($0) }
                case 0xdd:
                    guard length == 4, !hasRestartDefinition else { throw malformed() }
                    restartInterval = word(payload)
                    hasRestartDefinition = true
                case 0xda:
                    guard let frame, length == 8, bytes[payload] == 1,
                          bytes[payload + 1] == frame.id else { throw malformed() }
                    let near = Int(bytes[payload + 3])
                    guard bytes[payload + 2] == 0, bytes[payload + 4] == 0,
                          bytes[payload + 5] == 0 else {
                        throw CodecError(.unsupportedFeature, "This migrated path requires non-interleaved samples without mapping or point transform.")
                    }
                    let maximum = (1 << frame.bits) - 1
                    let declaredMaximum = preset.map { $0[0] == 0 ? maximum : $0[0] } ?? maximum
                    guard declaredMaximum <= maximum else { throw malformed() }
                    let defaults = try JPEGLSPresetParameters.defaultParameters(maxValue: declaredMaximum, near: near)
                    let params: JPEGLSPresetParameters
                    if let p = preset {
                        params = try JPEGLSPresetParameters(maxValue: p[0] == 0 ? defaults.maxValue : p[0],
                            threshold1: p[1] == 0 ? defaults.threshold1 : p[1], threshold2: p[2] == 0 ? defaults.threshold2 : p[2],
                            threshold3: p[3] == 0 ? defaults.threshold3 : p[3], reset: p[4] == 0 ? defaults.reset : p[4])
                        guard params.maxValue <= defaults.maxValue, params.threshold1 > near else { throw malformed() }
                    } else { params = defaults }
                    var scanStart = end
                    var scans: [Range<Int>] = []
                    let expected = restartInterval > 0 ? (frame.height + restartInterval - 1) / restartInterval : 1
                    try budget.admit(pixelBytes: 0,
                        workspaceBytes: checkedMultiply(expected, MemoryLayout<Range<Int>>.stride * 2), compressedBytes: data.count)
                    while true {
                        var scanEnd = scanStart
                        while scanEnd + 1 < bytes.count {
                            if scanEnd & 4095 == 0 { try budget.check() }
                            if bytes[scanEnd] == 255 && bytes[scanEnd + 1] >= 128 { break }
                            scanEnd += 1
                        }
                        var terminal = scanEnd
                        while terminal < bytes.count && bytes[terminal] == 255 {
                            terminal += 1
                            if terminal & 4095 == 0 { try budget.check() }
                        }
                        guard terminal < bytes.count, scanEnd > scanStart, scans.count < expected else { throw malformed() }
                        scans.append(scanStart..<scanEnd)
                        if scans.count == expected {
                            guard bytes[terminal] == 0xd9, terminal + 1 == bytes.count else { throw malformed() }
                            return Self(width: frame.width, height: frame.height, bits: frame.bits, near: near,
                                parameters: params, scans: scans, restartInterval: restartInterval)
                        }
                        guard bytes[terminal] == 0xd0 + UInt8((scans.count - 1) % 8) else { throw malformed() }
                        scanStart = terminal + 1
                    }
                default:
                    throw CodecError(.unsupportedFeature, "JPEG-LS marker or metadata is not yet implemented by this migrated path.")
                }
                cursor = end
            }
            throw malformed()
        }
    }
}
