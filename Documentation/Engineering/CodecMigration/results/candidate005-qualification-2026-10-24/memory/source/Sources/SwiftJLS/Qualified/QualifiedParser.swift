// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Decoder/JPEGLSParser.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal struct QualifiedParseState {
    let frameHeader: QualifiedFrameFields
    let firstScan: QualifiedScanFields
    let scanCount: Int
    let presetParameters: QualifiedPresetParameters?
    let restartInterval: Int?
    let scanRestartInterval: Int
    let colorTransformation: QualifiedColorTransformation
}

internal struct QualifiedParserCore {
    var reader: QualifiedBitstreamCursor
    mutating func parse<Storage: QualifiedStorageEvents>(storage: inout Storage) -> QualifiedOutcome<QualifiedParseState> {
        // Parse SOI marker
        if let failure = expectMarker(.startOfImage) { return .failure(failure) }

        var frameHeader: QualifiedFrameFields?
        var scanCount = 0
        var firstScan: QualifiedScanFields?
        var firstScanRestartInterval = 0
        var presetParameters: QualifiedPresetParameters?
        var restartInterval: Int?
        var extendedWidth: Int?
        var extendedHeight: Int?
        var colorTransformation: QualifiedColorTransformation = .none

        // Parse marker segments until EOI
        while !reader.isAtEnd {
            if let failure = reader.cancellation.checkpoint() { return .failure(failure) }
            // Read marker bytes manually to handle unknown markers
            let byte1: UInt8
            switch reader.readByte() {
            case .success(let value): byte1 = value
            case .failure(let failure): return .failure(failure)
            }
            guard byte1 == QualifiedMarker.markerPrefix else {
                return .failure(QualifiedFailure(.expectedPrefix, Int(byte1)))
            }

            var byte2: UInt8
            switch reader.readByte() {
            case .success(let value): byte2 = value
            case .failure(let failure): return .failure(failure)
            }

            // ITU-T T.81 B.1.1.2 (inherited by T.87): any marker may be preceded
            // by any number of 0xFF fill bytes. Encoders such as CharLS emit one
            // before EOI when the entropy coder's last byte is 0xFF, so skip fill
            // bytes before interpreting the marker code.
            while byte2 == QualifiedMarker.markerPrefix {
                switch reader.readByte() {
                case .success(let value): byte2 = value
                case .failure(let failure): return .failure(failure)
                }
            }

            // Try to parse as known marker
            guard let marker = QualifiedMarker(rawValue: byte2) else {
                return .failure(QualifiedFailure(.unsupportedProfile, Int(byte2)))
            }

            switch marker {
            case .endOfImage:
                // A decoder consumes one complete codestream. Permit only the single
                // zero byte needed to even-pad an odd stream in DICOM PS3.5 A.4.
                if reader.bytesRemaining > 0 {
                    guard reader.currentPosition % 2 == 1, reader.bytesRemaining == 1 else {
                        return .failure(QualifiedFailure(.trailingBytes))
                    }
                    let padding: UInt8
                    switch reader.readByte() {
                    case .success(let value): padding = value
                    case .failure(let failure): return .failure(failure)
                    }
                    guard padding == 0 else { return .failure(QualifiedFailure(.trailingBytes)) }
                }
                guard let frame = frameHeader else {
                    return .failure(QualifiedFailure(.missingFrame))
                }
                guard scanCount > 0, let firstScan else {
                    return .failure(QualifiedFailure(.missingScan))
                }
                return .success(QualifiedParseState(frameHeader: frame, firstScan: firstScan, scanCount: scanCount,
                    presetParameters: presetParameters, restartInterval: restartInterval,
                    scanRestartInterval: firstScanRestartInterval, colorTransformation: colorTransformation))

            case .startOfFrameQualified:
                // Parse frame header
                guard frameHeader == nil else {
                    return .failure(QualifiedFailure(.multipleFrames))
                }
                switch parseFrameHeader(monochrome: Storage.monochrome,
                    extendedWidth: extendedWidth, extendedHeight: extendedHeight) {
                case .success(let value): frameHeader = value
                case .failure(let failure): return .failure(failure)
                }

            case .startOfScan:
                // Parse scan header
                guard let frame = frameHeader else {
                    return .failure(QualifiedFailure(.scanBeforeFrame))
                }
                if Storage.monochrome, scanCount > 0 {
                    return .failure(QualifiedFailure(.monochromeScanCount))
                }
                let scanHeader: QualifiedScanFields
                switch parseScanHeader(frameHeader: frame, monochrome: Storage.monochrome) {
                case .success(let value): scanHeader = value
                case .failure(let failure): return .failure(failure)
                }
                scanCount += 1
                if firstScan == nil { firstScan = scanHeader; firstScanRestartInterval = restartInterval ?? 0 }
                storage.scan(scanHeader, interval: restartInterval ?? 0)
                // Record the restart interval in effect at this SOS (a DRI
                // between scans applies to following scans only, T.81 B.2.4.4).

                // Skip scan data until we hit a marker, recording the body's
                // byte range so the decoder can slice it without a second
                // full-file walk.
                // Per ISO 14495-1 §9.1, a byte following 0xFF with MSB = 0 (value < 0x80)
                // is a stuffed byte; with MSB = 1 (value ≥ 0x80) it is a real marker.
                let scanStart = reader.currentPosition
                var regionStart = scanStart
                var scanEnd: Int? = nil
                while !reader.isAtEnd {
                    let byte: UInt8
                    switch reader.readByte() {
                    case .success(let value): byte = value
                    case .failure(let failure): return .failure(failure)
                    }
                    if byte == QualifiedMarker.markerPrefix {
                        let prefix = reader.currentPosition - 1
                        // Fill FF bytes belong to the following marker, never to
                        // entropy or a restart region. Keep the first prefix.
                        var hadFill = false
                        while reader.peekByte() == 0xFF {
                            hadFill = true
                            if case .failure(let failure) = reader.readByte() { return .failure(failure) }
                        }
                        guard let code = reader.peekByte() else {
                            return .failure(QualifiedFailure(.prematureEndOfStream))
                        }
                        if code >= 0xD0 && code <= 0xD7 {
                            if case .failure(let failure) = reader.readByte() { return .failure(failure) }
                            if let failure = storage.region(regionStart..<prefix, marker: code) { return .failure(failure) }
                            regionStart = reader.currentPosition
                            continue
                        }
                        if code >= 0x80 {
                            if let failure = reader.seek(to: prefix) { return .failure(failure) }
                            scanEnd = prefix
                            break
                        }
                        guard !hadFill else { return .failure(QualifiedFailure(.invalidMarker, 255, Int(code))) }
                        if case .failure(let failure) = reader.readByte() { return .failure(failure) }
                    }
                }
                let end = scanEnd ?? reader.currentPosition
                storage.scanRange(scanStart..<end)
                if let failure = storage.region(regionStart..<end, marker: nil) { return .failure(failure) }

            case .jpegLSExtension:
                // Parse JPEG-LS extension
                if let failure = parseQualifiedExtension(
                    storage: &storage,
                    frameHeader: frameHeader,
                    presetParameters: &presetParameters,
                    extendedWidth: &extendedWidth,
                    extendedHeight: &extendedHeight
                ) { return .failure(failure) }

            case .applicationMarker0, .applicationMarker1, .applicationMarker2,
                 .applicationMarker3, .applicationMarker4, .applicationMarker5,
                 .applicationMarker6, .applicationMarker7, .applicationMarker8,
                 .applicationMarker9, .applicationMarker10, .applicationMarker11,
                 .applicationMarker12, .applicationMarker13, .applicationMarker14,
                 .applicationMarker15:
                let range: Range<Int>
                switch parseMarkerRange() {
                case .success(let value): range = value
                case .failure(let failure): return .failure(failure)
                }
                storage.application(marker, range: range, reader: reader)
                // Inspect the existing APP8 signal in place; no payload copy.
                if marker == .applicationMarker8, range.count >= 5 {
                    let i = range.lowerBound
                    if reader.byte(at: i) == 0x6D && reader.byte(at: i + 1) == 0x72 &&
                       reader.byte(at: i + 2) == 0x66 && reader.byte(at: i + 3) == 0x78 {
                        guard reader.byte(at: i + 4) == 0 else { return .failure(QualifiedFailure(.unsupportedProfile)) }
                        colorTransformation = .none
                    }
                }

            case .comment:
                let range: Range<Int>
                switch parseMarkerRange() {
                case .success(let value): range = value
                case .failure(let failure): return .failure(failure)
                }
                storage.comment(range, reader: reader)

            case .restart0, .restart1, .restart2, .restart3,
                 .restart4, .restart5, .restart6, .restart7:
                return .failure(QualifiedFailure(.restartMarker))

            case .defineRestartInterval:
                // Parse Define Restart Interval (DRI) marker per ITU-T.87 §5.1
                switch parseRestartInterval() {
                case .success(let value): restartInterval = value
                case .failure(let failure): return .failure(failure)
                }

            case .defineNumberOfLines:
                return .failure(QualifiedFailure(.unsupportedProfile, Int(marker.rawValue)))

            case .startOfImage:
                return .failure(QualifiedFailure(.unexpectedSOI))
            }
        }

        return .failure(QualifiedFailure(.missingEOI))
    }

    // MARK: - Private Parsing Methods

    private mutating func expectMarker(_ expected: QualifiedMarker) -> QualifiedFailure? {
        let marker: QualifiedMarker
        switch reader.readMarker() {
        case .success(let value): marker = value
        case .failure(let failure): return failure
        }
        guard marker == expected else {
            return QualifiedFailure(.expectedMarker, Int(expected.rawValue), Int(marker.rawValue))
        }
        return nil
    }

    private mutating func parseMarkerRange() -> QualifiedOutcome<Range<Int>> {
        let length: UInt16
        switch reader.readUInt16() {
        case .success(let value): length = value
        case .failure(let failure): return .failure(failure)
        }
        guard length >= 2 else {
            return .failure(QualifiedFailure(.markerLength, Int(length)))
        }
        // Length includes the 2 bytes of the length field itself
        let dataLength = Int(length) - 2
        return reader.readRange(dataLength)
    }

    private mutating func parseFrameHeader(monochrome: Bool,
        extendedWidth: Int? = nil, extendedHeight: Int? = nil) -> QualifiedOutcome<QualifiedFrameFields> {
        let length: UInt16
        switch reader.readUInt16() {
        case .success(let value): length = value
        case .failure(let failure): return .failure(failure)
        }

        // Read precision (bits per sample)
        let bitsPerSample: Int
        switch reader.readByte() {
        case .success(let value): bitsPerSample = Int(value)
        case .failure(let failure): return .failure(failure)
        }

        // Read dimensions from SOF.  When a dimension is 0, the actual value comes
        // from a preceding LSE type 4 (extended dimensions) segment per ITU-T.87 §5.1.1.4.
        let sofHeight: Int
        switch reader.readUInt16() {
        case .success(let value): sofHeight = Int(value)
        case .failure(let failure): return .failure(failure)
        }
        let sofWidth: Int
        switch reader.readUInt16() {
        case .success(let value): sofWidth = Int(value)
        case .failure(let failure): return .failure(failure)
        }
        let height = (sofHeight == 0) ? (extendedHeight ?? sofHeight) : sofHeight
        let width  = (sofWidth  == 0) ? (extendedWidth  ?? sofWidth)  : sofWidth

        // Read component count
        let componentCount: Int
        switch reader.readByte() {
        case .success(let value): componentCount = Int(value)
        case .failure(let failure): return .failure(failure)
        }
        if monochrome, componentCount != 1 {
            return .failure(QualifiedFailure(.monochromeComponentCount))
        }

        // Validate expected length
        let expectedLength = 2 + 1 + 2 + 2 + 1 + (componentCount * 3)
        guard length == expectedLength else {
            return .failure(QualifiedFailure(.sofLength, expectedLength, Int(length)))
        }

        // Read component specifications
        var components = QualifiedInline4(repeating: QualifiedFrameHeader.ComponentSpec(id: 0))

        for _ in 0..<componentCount {
            let id: UInt8
            switch reader.readByte() {
            case .success(let value): id = value
            case .failure(let failure): return .failure(failure)
            }
            let samplingFactors: UInt8
            switch reader.readByte() {
            case .success(let value): samplingFactors = value
            case .failure(let failure): return .failure(failure)
            }
            let horizontalSampling = samplingFactors >> 4
            let verticalSampling = samplingFactors & 0x0F
            // Quantization table selector (not used in JPEG-LS).
            if case .failure(let failure) = reader.readByte() { return .failure(failure) }

            if components.count < 4 { components.append(QualifiedFrameHeader.ComponentSpec(
                id: id, horizontalSamplingFactor: horizontalSampling, verticalSamplingFactor: verticalSampling)) }
        }

        if let failure = QualifiedFrameFields.validate(bitsPerSample: bitsPerSample, height: height,
            width: width, componentCount: componentCount, actualComponentCount: components.count) {
            return .failure(failure)
        }
        return .success(QualifiedFrameFields(
            bitsPerSample: bitsPerSample,
            height: height,
            width: width,
            componentCount: componentCount,
            components: components
        ))
    }

    private mutating func parseScanHeader(frameHeader: QualifiedFrameFields,
        monochrome: Bool) -> QualifiedOutcome<QualifiedScanFields> {
        let length: UInt16
        switch reader.readUInt16() {
        case .success(let value): length = value
        case .failure(let failure): return .failure(failure)
        }

        // Read component count in this scan
        let componentCount: Int
        switch reader.readByte() {
        case .success(let value): componentCount = Int(value)
        case .failure(let failure): return .failure(failure)
        }
        if monochrome, componentCount != 1 {
            return .failure(QualifiedFailure(.monochromeComponentCount))
        }

        // Validate expected length
        let expectedLength = 2 + 1 + (componentCount * 2) + 3
        guard length == expectedLength else {
            return .failure(QualifiedFailure(.sosLength, expectedLength, Int(length)))
        }

        // Read component selectors
        var components = QualifiedInline4(repeating: QualifiedScanHeader.ComponentSelector(id: 0))

        for _ in 0..<componentCount {
            let id: UInt8
            switch reader.readByte() {
            case .success(let value): id = value
            case .failure(let failure): return .failure(failure)
            }
            // Tdi field: mapping table ID per ITU-T.87 §5.1.2.
            // 0 means no mapping table; 1–255 references a mapping table from an LSE type 2/3 marker.
            let mappingTableID: UInt8
            switch reader.readByte() {
            case .success(let value): mappingTableID = value
            case .failure(let failure): return .failure(failure)
            }
            if components.count < 4 { components.append(QualifiedScanHeader.ComponentSelector(id: id, mappingTableID: mappingTableID)) }
        }

        // Read NEAR parameter
        let near: Int
        switch reader.readByte() {
        case .success(let value): near = Int(value)
        case .failure(let failure): return .failure(failure)
        }

        // Read interleave mode
        let interleaveModeValue: UInt8
        switch reader.readByte() {
        case .success(let value): interleaveModeValue = value
        case .failure(let failure): return .failure(failure)
        }
        guard let interleaveMode = QualifiedInterleaveMode(rawValue: interleaveModeValue) else {
            return .failure(QualifiedFailure(.interleaveMode, Int(interleaveModeValue)))
        }

        // Read point transform
        let pointTransform: Int
        switch reader.readByte() {
        case .success(let value): pointTransform = Int(value)
        case .failure(let failure): return .failure(failure)
        }

        if let failure = QualifiedScanFields.validate(componentCount: componentCount,
            actualComponentCount: components.count, near: near, interleaveMode: interleaveMode,
            pointTransform: pointTransform) { return .failure(failure) }
        let scanHeader = QualifiedScanFields(
            componentCount: componentCount,
            components: components,
            near: near,
            interleaveMode: interleaveMode,
            pointTransform: pointTransform
        )

        // Validate scan header against frame header
        if let failure = scanHeader.validate(against: frameHeader) { return .failure(failure) }

        return .success(scanHeader)
    }

    private mutating func parseQualifiedExtension<Storage: QualifiedStorageEvents>(
        storage: inout Storage,
        frameHeader: QualifiedFrameFields?,
        presetParameters: inout QualifiedPresetParameters?,
        extendedWidth: inout Int?,
        extendedHeight: inout Int?
    ) -> QualifiedFailure? {
        let length: UInt16
        switch reader.readUInt16() {
        case .success(let value): length = value
        case .failure(let failure): return failure
        }
        // Length includes the 2-byte length field and the 1-byte type that
        // follows; anything shorter is structurally invalid (and would make
        // the skip count below negative).
        guard length >= 3 else {
            return QualifiedFailure(.lseLength, Int(length))
        }

        // Read extension type
        let extensionTypeByte: UInt8
        switch reader.readByte() {
        case .success(let value): extensionTypeByte = value
        case .failure(let failure): return failure
        }
        guard let extensionType = QualifiedExtensionType(rawValue: extensionTypeByte) else {
            return QualifiedFailure(.unsupportedProfile, Int(extensionTypeByte))
        }

        switch extensionType {
        case .presetCodingParameters:
            // Parse preset parameters
            // Length should be 13: 2 (length field) + 1 (type) + 10 (5 x 2-byte params)
            guard length == 13 else {
                return QualifiedFailure(.presetLength, Int(length))
            }

            let maxValue: Int
            switch reader.readUInt16() {
            case .success(let value): maxValue = Int(value)
            case .failure(let failure): return failure
            }
            let threshold1: Int
            switch reader.readUInt16() {
            case .success(let value): threshold1 = Int(value)
            case .failure(let failure): return failure
            }
            let threshold2: Int
            switch reader.readUInt16() {
            case .success(let value): threshold2 = Int(value)
            case .failure(let failure): return failure
            }
            let threshold3: Int
            switch reader.readUInt16() {
            case .success(let value): threshold3 = Int(value)
            case .failure(let failure): return failure
            }
            let reset: Int
            switch reader.readUInt16() {
            case .success(let value): reset = Int(value)
            case .failure(let failure): return failure
            }

            switch QualifiedPresetParameters.qualified(maxValue: maxValue, threshold1: threshold1,
                threshold2: threshold2, threshold3: threshold3, reset: reset) {
            case .success(let value): presetParameters = value
            case .failure(let failure): return failure
            }

        case .mappingTable:
            // Parse mapping table specification per ITU-T.87 §5.1.1.3.
            // Format: Length(2) + Type(1) + TID(1) + Wt(1) + Entries((Length-5)*1 or (Length-5)/2)
            // Minimum length = 5 (no entries)
            guard length >= 5 else {
                return QualifiedFailure(.mappingLength, Int(length))
            }
            let tableID: UInt8
            switch reader.readByte() {
            case .success(let value): tableID = value
            case .failure(let failure): return failure
            }
            let entryWidth: Int
            switch reader.readByte() {
            case .success(let value): entryWidth = Int(value)
            case .failure(let failure): return failure
            }
            guard entryWidth == 1 || entryWidth == 2 else {
                return QualifiedFailure(.mappingWidth, entryWidth)
            }
            // Data bytes = length - 5 (subtract: 2 for Ll, 1 for Id, 1 for TID, 1 for Wt)
            let dataBytes = Int(length) - 5
            guard dataBytes >= 0 && dataBytes % entryWidth == 0 else {
                return QualifiedFailure(.mappingRemainder, dataBytes, entryWidth)
            }
            let range: Range<Int>
            switch reader.readRange(dataBytes) {
            case .success(let value): range = value
            case .failure(let failure): return failure
            }
            if let failure = storage.replaceMapping(id: tableID, width: entryWidth, range: range, reader: reader) { return failure }

        case .mappingTableContinuation:
            // Append additional entries to an existing mapping table per ITU-T.87 §5.1.1.3.
            // Format: Length(2) + Type(1) + TID(1) + Entries((Length-4) bytes or /2)
            guard length >= 4 else {
                return QualifiedFailure(.continuationLength, Int(length))
            }
            let tableID: UInt8
            switch reader.readByte() {
            case .success(let value): tableID = value
            case .failure(let failure): return failure
            }
            // data bytes = length - 4 (subtract: 2 for Ll, 1 for Id, 1 for TID)
            let dataBytes = Int(length) - 4
            if let failure = storage.preflightContinuation(id: tableID, byteCount: dataBytes) { return failure }
            let range: Range<Int>
            switch reader.readRange(dataBytes) {
            case .success(let value): range = value
            case .failure(let failure): return failure
            }
            if let failure = storage.continueMapping(id: tableID, range: range, reader: reader) { return failure }

        case .extendedDimensions:
            // Parse extended X/Y dimensions per ITU-T.87 §5.1.1.4.
            // Format: Ll(2) + Id(1) + Wxy(1) + XSIZE(Wxy bytes) + YSIZE(Wxy bytes)
            // remainingBytes = everything after Ll (2) and Id (1) that has already been read.
            let remainingBytes = Int(length) - 3
            guard remainingBytes >= 1 else {
                return QualifiedFailure(.extendedLength, Int(length))
            }
            let wxy: Int
            switch reader.readByte() {
            case .success(let value): wxy = Int(value)
            case .failure(let failure): return failure
            }
            // Wxy must be 1, 2, or 4 and the remaining bytes must be exactly 1 + 2*Wxy.
            guard (wxy == 1 || wxy == 2 || wxy == 4) && remainingBytes == 1 + 2 * wxy else {
                return QualifiedFailure(.extendedLength, Int(length))
            }
            // Read XSIZE (image width) as Wxy bytes, big-endian.
            var xSize: UInt32 = 0
            for _ in 0..<wxy {
                let byte: UInt8
                switch reader.readByte() {
                case .success(let value): byte = value
                case .failure(let failure): return failure
                }
                xSize = (xSize << 8) | UInt32(byte)
            }
            // Read YSIZE (image height) as Wxy bytes, big-endian.
            var ySize: UInt32 = 0
            for _ in 0..<wxy {
                let byte: UInt8
                switch reader.readByte() {
                case .success(let value): byte = value
                case .failure(let failure): return failure
                }
                ySize = (ySize << 8) | UInt32(byte)
            }
            guard let width = Int(exactly: xSize), let height = Int(exactly: ySize) else {
                return QualifiedFailure(.decodedLimit)
            }
            extendedWidth = width
            extendedHeight = height
        }
        return nil
    }

    private mutating func parseRestartInterval() -> QualifiedOutcome<Int> {
        let length: UInt16
        switch reader.readUInt16() {
        case .success(let value): length = value
        case .failure(let failure): return .failure(failure)
        }
        guard length == 4 else {
            return .failure(QualifiedFailure(.driLength, Int(length)))
        }
        let interval: UInt16
        switch reader.readUInt16() {
        case .success(let value): interval = value
        case .failure(let failure): return .failure(failure)
        }
        return .success(Int(interval))
    }
}
