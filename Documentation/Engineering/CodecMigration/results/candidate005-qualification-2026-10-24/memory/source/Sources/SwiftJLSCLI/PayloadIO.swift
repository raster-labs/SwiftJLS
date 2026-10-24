// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS
#if canImport(Darwin)
import Darwin
#else
import Glibc
#endif

struct StreamBudget {
    let limits: ResourceLimits
    let started = ProcessInfo.processInfo.systemUptime
    func check() throws {
        try Task.checkCancellation()
        if ProcessInfo.processInfo.systemUptime - started >= limits.deadlineSeconds {
            throw CodecError(.resourceLimitExceeded, "Stream deadline exceeded.")
        }
    }
    func remainingLimits() throws -> ResourceLimits {
        try check()
        return try ResourceLimits(maximumCompressedBytes: limits.maximumCompressedBytes,
            maximumDecodedBytes: limits.maximumDecodedBytes, maximumWorkspaceBytes: limits.maximumWorkspaceBytes,
            maximumPixels: limits.maximumPixels, maximumDimension: limits.maximumDimension,
            maximumFrames: limits.maximumFrames, maximumMetadataBytes: limits.maximumMetadataBytes,
            maximumICCBytes: limits.maximumICCBytes, maximumNestingDepth: limits.maximumNestingDepth,
            maximumWorkers: limits.maximumWorkers,
            deadlineSeconds: max(Double.leastNonzeroMagnitude, limits.deadlineSeconds - (ProcessInfo.processInfo.systemUptime - started)),
            maximumMemoryBytes: limits.maximumMemoryBytes)
    }
    func ready(_ fd: Int32, events: Int16) throws {
        while true {
            try check()
            var item = pollfd(fd: fd, events: events, revents: 0)
            let result = poll(&item, 1, 100)
            if result > 0 { return }
            if result < 0 && errno != EINTR { throw CodecError(.storageUnavailable, "Stream polling failed.") }
        }
    }
}

/// Bounded nonblocking reads ensure slow pipes respect cancellation/deadlines.
final class InputStreamReader {
    let fd: Int32
    private let owned: Bool
    private let originalFlags: Int32
    let budget: StreamBudget
    private var buffer = Data()
    private var cursor = 0
    init(path: String, budget: StreamBudget) throws {
        owned = path != "-"
        fd = owned ? open(path, O_RDONLY | O_NONBLOCK) : STDIN_FILENO
        guard fd >= 0 else { throw CodecError(.storageUnavailable, "Cannot open input.") }
        self.budget = budget
        originalFlags = fcntl(fd, F_GETFL)
        if originalFlags >= 0 { _ = fcntl(fd, F_SETFL, originalFlags | O_NONBLOCK) }
    }
    deinit {
        if owned { _ = close(fd) }
        else if originalFlags >= 0 { _ = fcntl(fd, F_SETFL, originalFlags) }
    }
    private func refill() throws -> Bool {
        while true {
            try budget.ready(fd, events: Int16(POLLIN))
            var chunk = [UInt8](repeating: 0, count: 65536)
            let count = read(fd, &chunk, chunk.count)
            if count < 0 {
                if errno == EINTR || errno == EAGAIN { continue }
                throw CodecError(.storageUnavailable, "Cannot read input.")
            }
            buffer = Data(chunk.prefix(count)); cursor = 0
            return count > 0
        }
    }
    func byte() throws -> UInt8? {
        if cursor == buffer.count { if try !refill() { return nil } }
        let value = buffer[cursor]; cursor += 1; return value
    }
    func compressed() throws -> Data {
        var result = Data()
        while try refill() {
            guard buffer.count <= budget.limits.maximumCompressedBytes - result.count,
                  buffer.count <= budget.limits.maximumMemoryBytes - result.count else {
                throw CodecError(.resourceLimitExceeded, "Compressed input exceeds stream limits.")
            }
            result.append(buffer)
        }
        return result
    }
    func nrrdImage() throws -> Image {
        var lines: [String] = [], line: [UInt8] = [], bytes = 0
        var terminated = false
        while let next = try byte() {
            bytes += 1
            guard bytes <= 16384, line.count <= 1024, lines.count < 32 else {
                throw CodecError(.resourceLimitExceeded, "NRRD header exceeds profile limits.")
            }
            if next == 10 {
                if line.last == 13 { line.removeLast() }
                if line.isEmpty { terminated = true; break }
                guard let text = String(bytes: line, encoding: .ascii) else {
                    throw CodecError(.malformedInput, "NRRD header is not ASCII.")
                }
                lines.append(text); line.removeAll(keepingCapacity: true)
            } else { line.append(next) }
        }
        guard terminated, line.isEmpty, let magic = lines.first, ["NRRD0001", "NRRD0002", "NRRD0003", "NRRD0004", "NRRD0005"].contains(magic) else {
            throw CodecError(.malformedInput, "Invalid attached NRRD header.")
        }
        var fields: [String: String] = [:]
        let accepted: Set<String> = ["type", "dimension", "sizes", "encoding", "endian", "kinds"]
        for entry in lines.dropFirst() where !entry.hasPrefix("#") {
            guard let separator = entry.range(of: ": ") else {
                throw CodecError(.unsupportedFeature, "Unsupported NRRD field syntax.")
            }
            let key = String(entry[..<separator.lowerBound]).lowercased()
            guard accepted.contains(key), fields[key] == nil else {
                throw CodecError(.unsupportedFeature, "Unsupported or duplicate NRRD field.")
            }
            fields[key] = entry[separator.upperBound...].trimmingCharacters(in: .whitespaces).lowercased()
        }
        guard fields["dimension"] == "2", fields["encoding"] == "raw",
              ["ushort", "unsigned short", "unsigned short int", "uint16", "uint16_t"].contains(fields["type"] ?? ""),
              ["little", "big"].contains(fields["endian"] ?? ""),
              fields["kinds"] == nil || fields["kinds"] == "domain domain" else {
            throw CodecError(.unsupportedFeature, "NRRD profile requires 2D raw uint16 greyscale and explicit endian.")
        }
        let tokens = fields["sizes", default: ""].split(whereSeparator: { $0.isWhitespace })
        let sizes = tokens.compactMap { Int($0) }
        guard tokens.count == 2, sizes.count == 2 else { throw CodecError(.malformedInput, "Invalid NRRD sizes.") }
        let shape = try ImageDescriptor.greyscale16(width: sizes[0], height: sizes[1], limits: budget.limits)
        guard shape.requiredByteCount <= budget.limits.maximumMemoryBytes - 131072 else {
            throw CodecError(.resourceLimitExceeded, "NRRD samples exceed stream memory admission.")
        }
        let little = fields["endian"] == "little"
        let image = try ImageDestination.allocate(descriptor: shape, limits: budget.limits).writeUInt16 { x, _ in
            if x & 255 == 0 { try self.budget.check() }
            guard let first = try self.byte(), let second = try self.byte() else {
                throw CodecError(.malformedInput, "Truncated NRRD sample payload.")
            }
            return little ? UInt16(first) | UInt16(second) << 8 : UInt16(first) << 8 | UInt16(second)
        }
        guard try byte() == nil else { throw CodecError(.malformedInput, "Unexpected NRRD payload suffix.") }
        return image
    }
}

func writeBytes(_ bytes: UnsafeRawBufferPointer, fd: Int32, budget: StreamBudget) throws {
    var offset = 0
    while offset < bytes.count {
        try budget.ready(fd, events: Int16(POLLOUT))
        let size = min(65536, bytes.count - offset)
        let count = write(fd, bytes.baseAddress?.advanced(by: offset), size)
        if count < 0 {
            if errno == EINTR || errno == EAGAIN { continue }
            throw CodecError(.storageUnavailable, "Cannot write output.")
        }
        guard count > 0 else { throw CodecError(.storageUnavailable, "Output made no progress.") }
        offset += count
    }
}

func publish(path: String, overwrite: Bool, budget: StreamBudget,
             body: (Int32) throws -> Void) throws {
    if path == "-" {
        let flags = fcntl(STDOUT_FILENO, F_GETFL)
        if flags >= 0 { _ = fcntl(STDOUT_FILENO, F_SETFL, flags | O_NONBLOCK) }
        defer { if flags >= 0 { _ = fcntl(STDOUT_FILENO, F_SETFL, flags) } }
        try body(STDOUT_FILENO); return
    }
    let final = URL(fileURLWithPath: path).standardizedFileURL
    let temporary = final.deletingLastPathComponent().appendingPathComponent(".swiftjls-\(UUID().uuidString).tmp").path
    let fd = open(temporary, O_CREAT | O_EXCL | O_WRONLY, mode_t(0o600))
    guard fd >= 0 else { throw CodecError(.storageUnavailable, "Cannot create output transaction.") }
    defer { _ = close(fd); _ = unlink(temporary) }
    try body(fd)
    try budget.check()
    guard fsync(fd) == 0 else { throw CodecError(.storageUnavailable, "Cannot flush output transaction.") }
    // link is an atomic no-replace publication; rename explicitly replaces.
    let result = overwrite ? rename(temporary, final.path) : link(temporary, final.path)
    guard result == 0 else { throw CodecError(.storageUnavailable, "Cannot publish output; destination may already exist.") }
}

func writeNRRD(_ image: Image, fd: Int32, budget: StreamBudget) throws {
    let d = image.descriptor
    guard d.meaningfulBits == 16, d.components == [.grey], image.metadata.entries.isEmpty else {
        throw CodecError(.unsupportedFeature, "The NRRD profile cannot preserve this image's precision or metadata.")
    }
    let header = Data("NRRD0005\ntype: uint16\ndimension: 2\nsizes: \(d.width) \(d.height)\nencoding: raw\nendian: little\n\n".utf8)
    try header.withUnsafeBytes { try writeBytes($0, fd: fd, budget: budget) }
    // Decoded owned storage is packed little-endian; stream the scoped bytes.
    try image.storage.withUnsafeBytes { bytes in
        try writeBytes(bytes, fd: fd, budget: budget)
    }
}
