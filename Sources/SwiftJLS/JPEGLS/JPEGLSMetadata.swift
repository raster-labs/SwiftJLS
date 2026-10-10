// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
import Foundation

/// Opaque JPEG application and comment payloads, in their original order.
/// No character encoding or application-specific interpretation is inferred.
public struct JPEGLSMetadata: Sendable, Equatable {
    public struct Segment: Sendable, Equatable {
        public let marker: UInt8
        public let payload: Data
        public init(marker: UInt8, payload: Data) throws {
            guard marker == 0xfe || (0xe0...0xef).contains(marker), payload.count <= 65533 else {
                throw CodecError(.invalidArgument, "Expected a bounded JPEG APP or COM segment.")
            }
            guard marker != 0xe8 || (!payload.starts(with: [109, 114, 102, 120]) && !payload.starts(with: [83, 80, 73, 70, 70, 0])) else {
                throw CodecError(.invalidArgument, "SPIFF and HP interpretation markers cannot be opaque metadata.")
            }
            self.marker = marker; self.payload = payload
        }
    }
    public static let key = "jpeg-ls.ancillary-markers"
    /// Raw SPIFF APP8 header and directory segments, including the directory terminator.
    public static let spiffKey = "jpeg-ls.spiff"
    public let segments: [Segment]
    public init(segments: [Segment]) { self.segments = segments }
    public init(metadata: ImageMetadata) throws {
        var segments: [Segment] = []
        let data = metadata.entries[Self.key] ?? Data()
        try data.withUnsafeBytes { (bytes: UnsafeRawBufferPointer) in
            var i = 0
            while i < bytes.count {
                guard bytes.count - i >= 3 else { throw CodecError(.invalidArgument, "Truncated metadata segment.") }
                let count = Int(bytes[i + 1]) << 8 | Int(bytes[i + 2])
                guard count <= bytes.count - i - 3 else { throw CodecError(.invalidArgument, "Truncated metadata payload.") }
                segments.append(try Segment(marker: bytes[i], payload: Data(bytes[(i + 3)..<(i + 3 + count)])))
                i += 3 + count
            }
        }
        self.segments = segments
    }
    public var metadata: ImageMetadata { .init(entries: segments.isEmpty ? [:] : [Self.key: archive]) }
    var archive: Data {
        var data = Data()
        for s in segments {
            data.append(s.marker); data.append(UInt8(s.payload.count >> 8)); data.append(UInt8(s.payload.count & 255))
            data.append(s.payload)
        }
        return data
    }
    func write(to writer: JPEGLSBitstreamWriter) throws {
        for s in segments {
            writer.writeByte(255); writer.writeByte(s.marker); writer.writeUInt16(UInt16(s.payload.count + 2))
            for byte in s.payload { writer.writeByte(byte) }
            try writer.checkLimit()
        }
    }
}

/// T.87 table entries are opaque bytes. Scalar output interpretation is an
/// explicit decoder option; the default returns indices with required tables.
public struct JPEGLSMappingTable: Sendable, Equatable {
    public let id: UInt8
    public let entryWidth: Int
    public let data: Data
    public var count: Int { data.count / entryWidth }
    public init(id: UInt8, entryWidth: Int, data: Data) throws {
        guard id != 0, (1...255).contains(entryWidth), !data.isEmpty,
              data.count % entryWidth == 0, data.count / entryWidth <= 65536 else {
            throw CodecError(.invalidArgument, "Invalid mapping table ID, width or entry count.")
        }
        self.id = id; self.entryWidth = entryWidth; self.data = Data(data)
    }
    public init(id: UInt8, entryWidth: Int, entries: [UInt16]) throws {
        guard entryWidth == 1 || entryWidth == 2,
              entryWidth == 2 || entries.allSatisfy({ $0 <= 255 }) else {
            throw CodecError(.invalidArgument, "Scalar table entries must fit one or two bytes.")
        }
        var data = Data()
        for entry in entries {
            if entryWidth == 2 { data.append(UInt8(entry >> 8)) }
            data.append(UInt8(entry & 255))
        }
        try self.init(id: id, entryWidth: entryWidth, data: data)
    }
    func sample(_ index: Int) -> UInt16 {
        let at = data.startIndex + index * entryWidth
        return entryWidth == 1 ? UInt16(data[at]) : UInt16(data[at]) << 8 | UInt16(data[at + 1])
    }
}

/// Attach this required metadata to an index image before encoding. Table IDs
/// correspond to logical descriptor components, independently of plane layout.
public struct JPEGLSMappingTables: Sendable, Equatable {
    public static let key = "jpeg-ls.mapping-tables"
    public let tables: [JPEGLSMappingTable]
    public let componentTableIDs: [UInt8]
    public init(tables: [JPEGLSMappingTable], componentTableIDs: [UInt8]) throws {
        guard (1...4).contains(componentTableIDs.count), tables.count <= 255,
              Set(tables.map(\.id)).count == tables.count else {
            throw CodecError(.invalidArgument, "Invalid mapping table assignments.")
        }
        let ids = Set(tables.map(\.id))
        guard componentTableIDs.allSatisfy({ $0 == 0 || ids.contains($0) }) else {
            throw CodecError(.invalidArgument, "Referenced mapping table is absent.")
        }
        self.tables = tables; self.componentTableIDs = componentTableIDs
    }
    public init(metadata: ImageMetadata) throws {
        guard let data = metadata.entries[Self.key] else {
            throw CodecError(.invalidArgument, "Mapping table metadata is absent.")
        }
        self = try data.withUnsafeBytes { (bytes: UnsafeRawBufferPointer) in
            guard bytes.count >= 2, bytes[0] == 1, (1...4).contains(bytes[1]), bytes.count >= 2 + Int(bytes[1]) else {
                throw CodecError(.invalidArgument, "Invalid mapping table archive.")
            }
            let ids = Array(bytes[2..<(2 + Int(bytes[1]))]); var i = 2 + ids.count
            var tables: [JPEGLSMappingTable] = []
            while i < bytes.count {
                guard bytes.count - i >= 6 else { throw CodecError(.invalidArgument, "Truncated mapping table archive.") }
                let wireCount = (UInt32(bytes[i + 2]) << 24) | (UInt32(bytes[i + 3]) << 16) | (UInt32(bytes[i + 4]) << 8) | UInt32(bytes[i + 5])
                guard let count = Int(exactly: wireCount), count <= bytes.count - i - 6 else { throw CodecError(.invalidArgument, "Truncated mapping table data.") }
                tables.append(try .init(id: bytes[i], entryWidth: Int(bytes[i + 1]), data: Data(bytes[(i + 6)..<(i + 6 + count)])))
                i += 6 + count
            }
            return try Self(tables: tables, componentTableIDs: ids)
        }
    }
    public var metadata: ImageMetadata {
        var data = Data([1, UInt8(componentTableIDs.count)]); data.append(contentsOf: componentTableIDs)
        for table in tables.sorted(by: { $0.id < $1.id }) {
            data.append(table.id); data.append(UInt8(table.entryWidth))
            for shift in [24, 16, 8, 0] { data.append(UInt8((table.data.count >> shift) & 255)) }
            data.append(table.data)
        }
        return .init(entries: [Self.key: data], requiredKeys: [Self.key])
    }
    func validate(components: Int, maximum: Int) throws {
        guard componentTableIDs.count == components,
              tables.allSatisfy({ $0.count == maximum + 1 }) else {
            throw CodecError(.invalidArgument, "Mapping tables must contain MAXVAL + 1 entries and match the component count.")
        }
    }
    func write(to writer: JPEGLSBitstreamWriter, budget: CodecBudget) throws {
        for table in tables {
            let maximumBytes = (65530 / table.entryWidth) * table.entryWidth
            var start = 0
            while start < table.data.count {
                try budget.check()
                let end = min(start + maximumBytes, table.data.count)
                writer.writeByte(255); writer.writeByte(0xf8); writer.writeUInt16(UInt16(end - start + 5))
                writer.writeByte(start == 0 ? 2 : 3); writer.writeByte(table.id); writer.writeByte(UInt8(table.entryWidth))
                for byte in table.data[start..<end] { writer.writeByte(byte) }
                try writer.checkLimit(); start = end
            }
        }
    }
}

struct JPEGMetadataEncoding {
    let ancillary: JPEGLSMetadata
    let mapping: JPEGLSMappingTables?
    let spiff: Data?
    let byteCount: Int
    init(_ image: Image, options: EncodeOptions, additionalBytes: Int = 0) throws {
        let metadataBytes = try image.metadata.validate(limits: options.resourceLimits, additionalBytes: additionalBytes)
        let supported: Set<String> = [JPEGLSMetadata.key, JPEGLSMetadata.spiffKey, JPEGLSMappingTables.key]
        guard image.metadata.requiredKeys.isSubset(of: supported),
              options.metadataPolicy == .discardAncillary || Set(image.metadata.entries.keys).isSubset(of: supported) else {
            throw CodecError(.unsupportedFeature, "Unrepresentable image metadata cannot be preserved in JPEG-LS.")
        }
        ancillary = try JPEGLSMetadata(metadata: options.metadataPolicy == .preserve || image.metadata.requiredKeys.contains(JPEGLSMetadata.key) ? image.metadata : .empty)
        spiff = options.metadataPolicy == .preserve || image.metadata.requiredKeys.contains(JPEGLSMetadata.spiffKey)
            ? image.metadata.entries[JPEGLSMetadata.spiffKey] : nil
        if let spiff { try Self.validateSPIFF(spiff, descriptor: image.descriptor) }
        mapping = try image.metadata.entries[JPEGLSMappingTables.key].map { _ in try JPEGLSMappingTables(metadata: image.metadata) }
        // Archive bytes plus segment overhead; a conservative allowance for all
        // live metadata copies is separately charged to the workspace budget.
        byteCount = try checkedAdd(metadataBytes, checkedMultiply(ancillary.segments.count + (mapping?.tables.count ?? 0) * 260, 4))
    }
    static func validateSPIFF(_ data: Data, descriptor: ImageDescriptor) throws {
        try data.withUnsafeBytes { (b: UnsafeRawBufferPointer) in
            func invalid() -> CodecError { .init(.invalidArgument, "SPIFF metadata disagrees with the image or is malformed.") }
            func word(_ i: Int) -> Int { Int(b[i]) << 8 | Int(b[i + 1]) }
            func long(_ i: Int) -> UInt32 { UInt32(word(i)) << 16 | UInt32(word(i + 2)) }
            guard b.count >= 44, Array(b[0..<12]) == [255, 232, 0, 32, 83, 80, 73, 70, 70, 0, 2, 0],
                  Int(b[13]) == descriptor.components.count,
                  UInt64(long(14)) == UInt64(descriptor.height), UInt64(long(18)) == UInt64(descriptor.width),
                  Int(b[23]) == descriptor.meaningfulBits, b[24] == 6, b[25] <= 2,
                  long(26) > 0, long(30) > 0,
                  (b[22] == 8 && descriptor.colour == .greyscale) || (b[22] == 10 && descriptor.colour == .rgb) || (b[22] != 8 && b[22] != 10 && descriptor.colour == .unknown) else { throw invalid() }
            var i = 34
            while i < b.count {
                guard b.count - i >= 8, b[i] == 255, b[i + 1] == 232 else { throw invalid() }
                let length = word(i + 2)
                guard length >= 6, length <= b.count - i - 2 else { throw invalid() }
                if long(i + 4) == 1 {
                    guard length == 8, b[i + 8] == 255, b[i + 9] == 216, i + 10 == b.count else { throw invalid() }
                    return
                }
                i += length + 2
            }
            throw invalid()
        }
    }
    func writeSPIFF(to writer: JPEGLSBitstreamWriter) throws {
        if let spiff {
            for byte in spiff { writer.writeByte(byte) }
            try writer.checkLimit()
        }
    }

}
