// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Decoder/JPEGLSParseStorage.swift; Decoder/JPEGLSMonochromeParseStorage.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal protocol QualifiedStorageEvents {
    static var monochrome: Bool { get }
    mutating func scan(_ header: QualifiedScanFields, interval: Int)
    mutating func scanRange(_ range: Range<Int>)
    mutating func region(_ range: Range<Int>, marker: UInt8?) -> QualifiedFailure?
    mutating func application(_ marker: QualifiedMarker, range: Range<Int>, reader: QualifiedBitstreamCursor)
    mutating func comment(_ range: Range<Int>, reader: QualifiedBitstreamCursor)
    mutating func replaceMapping(id: UInt8, width: Int, range: Range<Int>, reader: QualifiedBitstreamCursor) -> QualifiedFailure?
    func preflightContinuation(id: UInt8, byteCount: Int) -> QualifiedFailure?
    mutating func continueMapping(id: UInt8, range: Range<Int>, reader: QualifiedBitstreamCursor) -> QualifiedFailure?
}

internal struct QualifiedParseStorage: QualifiedStorageEvents {
    static let monochrome = true
    private let widths: UnsafeMutableBufferPointer<Int>
    private let values: UnsafeMutableBufferPointer<UInt16>
    private let selectedTable: UInt8?
    private(set) var mappingCount = 0
    private(set) var hasMappingTables = false
    private(set) var restartCount = 0
    private(set) var restartOrderValid = true
    var consumer: QualifiedRegionConsumer?

    init(widths: UnsafeMutableBufferPointer<Int>, values: UnsafeMutableBufferPointer<UInt16>,
         selectedTable: UInt8? = nil, consumer: QualifiedRegionConsumer? = nil) {
        self.consumer = consumer
        self.widths = widths; self.values = values; self.selectedTable = selectedTable
        widths.initialize(repeating: 0)
        values.initialize(repeating: 0)
    }

    mutating func region(_ range: Range<Int>, marker: UInt8?) -> QualifiedFailure? {
        if let marker {
            if marker != QualifiedMarker.restart0.rawValue + UInt8(restartCount % 8) {
                restartOrderValid = false
            }
            restartCount += 1
        }
        return consumer?.consume(range, marker: marker)
    }

    func validateRestarts(_ parsed: QualifiedParseState) -> QualifiedFailure? {
        let interval = parsed.scanRestartInterval
        let height = parsed.frameHeader.height
        let expected = interval > 0 && interval < height ? (height - 1) / interval : 0
        guard restartCount == expected, restartOrderValid else {
            return QualifiedFailure(.restartCycle)
        }
        return nil
    }

    mutating func replaceMapping(id: UInt8, width: Int, range: Range<Int>, reader: QualifiedBitstreamCursor) -> QualifiedFailure? {
        guard id > 0 else {
            return QualifiedFailure(.mappingID)
        }
        hasMappingTables = true
        widths[Int(id)] = width
        if selectedTable == id {
            mappingCount = 0
            copyEntries(range, width: width, reader: reader)
        }
        return nil
    }

    // Borrowed mode historically validates the complete encoded span first.
    func preflightContinuation(id: UInt8, byteCount: Int) -> QualifiedFailure? { nil }

    mutating func continueMapping(id: UInt8, range: Range<Int>, reader: QualifiedBitstreamCursor) -> QualifiedFailure? {
        let width = widths[Int(id)]
        guard width != 0 else { return QualifiedFailure(.missingMappingTable, Int(id)) }
        guard range.count % width == 0 else {
            return QualifiedFailure(.mappingContinuation)
        }
        if selectedTable == id { copyEntries(range, width: width, reader: reader) }
        return nil
    }

    private mutating func copyEntries(_ range: Range<Int>, width: Int, reader: QualifiedBitstreamCursor) {
        // Samples cannot index beyond 65535. Still validate the complete segment
        // range in the parser, but never expand unreachable palette entries.
        let count = min(range.count / width, values.count - mappingCount)
        for index in 0..<count {
            let offset = range.lowerBound + index * width
            let high = UInt16(reader.byte(at: offset))
            values[mappingCount + index] = width == 1 ? high : (high << 8) | UInt16(reader.byte(at: offset + 1))
        }
        mappingCount += count
    }

    mutating func scan(_ header: QualifiedScanFields, interval: Int) {}
    mutating func scanRange(_ range: Range<Int>) {}
    mutating func application(_ marker: QualifiedMarker, range: Range<Int>, reader: QualifiedBitstreamCursor) {}
    mutating func comment(_ range: Range<Int>, reader: QualifiedBitstreamCursor) {}

    func validateMappingSelection(_ parsed: QualifiedParseState) -> QualifiedFailure? {
        let selected = parsed.firstScan.components[0].mappingTableID
        return selected == 0 || widths[Int(selected)] != 0 ? nil : QualifiedFailure(.missingMappingTable, Int(selected))
    }
    func mapped(_ sample: UInt16) -> UInt16? {
        guard let selectedTable, selectedTable != 0 else { return sample }
        guard Int(sample) < mappingCount else { return nil }
        return values[Int(sample)]
    }
}
