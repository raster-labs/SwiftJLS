// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Core/JPEGLSBitstreamReader.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal struct QualifiedBitstreamCursor {
    let cancellation: QualifiedCancellation
    private let bytes: UnsafeRawBufferPointer
    private var position: Int
    private var nextCancellationCheckpoint = 65_536
    private var bitBuffer: UInt64
    private var bitsInBuffer: Int
    private var bitRegionStart: Int
    private var bitsConsumedInRegion: Int

    init(borrowing bytes: UnsafeRawBufferPointer, cancellation: QualifiedCancellation = .init()) {
        self.cancellation = cancellation
        self.bytes = bytes
        position = 0; bitBuffer = 0; bitsInBuffer = 0
        bitRegionStart = 0; bitsConsumedInRegion = 0
    }

    internal mutating func readRange(_ count: Int) -> QualifiedOutcome<Range<Int>> {
        if let failure = cancellation.checkpoint() { return .failure(failure) }
        guard count >= 0, count <= bytes.count - position else {
            return .failure(QualifiedFailure(.prematureEndOfStream))
        }
        let start = position
        position += count
        return .success(start..<position)
    }

    internal func byte(at position: Int) -> UInt8 { bytes[position] }

    internal var currentPosition: Int {
        return position
    }

    internal var bytesRemaining: Int {
        return bytes.count - position
    }

    internal var isAtEnd: Bool {
        return position >= bytes.count && bitsInBuffer == 0
    }

    internal mutating func readByte() -> QualifiedOutcome<UInt8> {
        if position >= nextCancellationCheckpoint {
            if let failure = cancellation.checkpoint() { return .failure(failure) }
            nextCancellationCheckpoint = position > Int.max - 65_536 ? Int.max : position + 65_536
        }
        guard position < bytes.count else {
            return .failure(QualifiedFailure(.prematureEndOfStream))
        }
        let byte = bytes[position]
        position += 1
        return .success(byte)
    }

    internal mutating func readUInt16() -> QualifiedOutcome<UInt16> {
        let byte1: UInt8
        switch readByte() {
        case .success(let value): byte1 = value
        case .failure(let failure): return .failure(failure)
        }
        let byte2: UInt8
        switch readByte() {
        case .success(let value): byte2 = value
        case .failure(let failure): return .failure(failure)
        }
        return .success((UInt16(byte1) << 8) | UInt16(byte2))
    }

    internal func peekByte() -> UInt8? {
        guard position < bytes.count else {
            return nil
        }
        return bytes[position]
    }

    internal mutating func readMarker() -> QualifiedOutcome<QualifiedMarker> {
        let byte1: UInt8
        switch readByte() {
        case .success(let value): byte1 = value
        case .failure(let failure): return .failure(failure)
        }
        guard byte1 == QualifiedMarker.markerPrefix else {
            return .failure(QualifiedFailure(.invalidMarker, Int(byte1), 0))
        }

        var byte2: UInt8
        switch readByte() {
        case .success(let value): byte2 = value
        case .failure(let failure): return .failure(failure)
        }
        while byte2 == QualifiedMarker.markerPrefix {
            switch readByte() {
            case .success(let value): byte2 = value
            case .failure(let failure): return .failure(failure)
            }
        }
        guard let marker = QualifiedMarker(rawValue: byte2) else {
            return .failure(QualifiedFailure(.invalidMarker, Int(byte1), Int(byte2)))
        }

        return .success(marker)
    }

    internal mutating func findNextMarker() -> QualifiedOutcome<QualifiedMarker> {
        while !isAtEnd {
            let byte: UInt8
            switch readByte() {
            case .success(let value): byte = value
            case .failure(let failure): return .failure(failure)
            }
            if byte == QualifiedMarker.markerPrefix {
                if let nextByte = peekByte(), nextByte >= 0x80 {
                    // MSB = 1: real marker
                    position -= 1  // Back up to re-read the 0xFF
                    return readMarker()
                }
                // MSB = 0: stuffed byte, skip and continue
            }
        }
        return .failure(QualifiedFailure(.prematureEndOfStream))
    }

    // MARK: - Bit-level reading

    @inline(__always)
    private mutating func refill() {
        if bitsInBuffer == 0 && bitsConsumedInRegion == 0 {
            bitRegionStart = position
        }
        let count = bytes.count
        while bitsInBuffer <= 48 && position < count {
            let byte = bytes[position]
            if byte == 0xFF && position + 1 < count {
                let next = bytes[position + 1]
                if next < 0x80 {
                    // Stuffed pair: 0xFF (8 bits) + stuff bit dropped + 7 data bits.
                    position += 2
                    bitBuffer = (bitBuffer << 15) | (0xFF << 7) | UInt64(next & 0x7F)
                    bitsInBuffer += 15
                    continue
                }
                // next >= 0x80: marker follows. The FF is added below; decoding
                // should finish before any marker bytes are consumed.
            }
            position += 1
            bitBuffer = (bitBuffer << 8) | UInt64(byte)
            bitsInBuffer += 8
        }
    }

    @inline(__always)
    private func alignedWindow() -> UInt64 {
        let mask: UInt64 = (1 << UInt64(bitsInBuffer)) &- 1
        return (bitBuffer & mask) << UInt64(64 - bitsInBuffer)
    }

    internal mutating func readBits(_ count: Int) -> QualifiedOutcome<UInt32> {
        if position >= nextCancellationCheckpoint {
            if let failure = cancellation.checkpoint() { return .failure(failure) }
            nextCancellationCheckpoint = position > Int.max - 65_536 ? Int.max : position + 65_536
        }
        guard count > 0 && count <= 32 else {
            return .failure(QualifiedFailure(.bitCount, count))
        }

        if bitsInBuffer < count {
            refill()
            guard bitsInBuffer >= count else {
                return .failure(QualifiedFailure(.prematureEndOfStream))
            }
        }

        // Extract bits from the most-significant valid position.
        let shift = bitsInBuffer - count
        let mask: UInt32 = count < 32 ? ((1 << count) - 1) : UInt32.max
        let bits = UInt32(truncatingIfNeeded: bitBuffer >> UInt64(shift)) & mask

        bitsInBuffer -= count
        bitsConsumedInRegion += count

        return .success(bits)
    }

    internal mutating func readUnaryCount(maximum: Int) -> QualifiedOutcome<Int> {
        var count = 0
        while true {
            if position >= nextCancellationCheckpoint {
                if let failure = cancellation.checkpoint() { return .failure(failure) }
                nextCancellationCheckpoint = position > Int.max - 65_536 ? Int.max : position + 65_536
            }
            if bitsInBuffer == 0 {
                refill()
                guard bitsInBuffer > 0 else {
                    return .failure(QualifiedFailure(.prematureEndOfStream))
                }
            }
            let window = alignedWindow()
            let zeros = min(window.leadingZeroBitCount, bitsInBuffer)
            guard zeros <= maximum - count else { return .failure(QualifiedFailure(.invalidEntropy)) }
            if zeros < bitsInBuffer {
                // Found the terminating '1': consume the zeros and the 1.
                bitsInBuffer -= zeros + 1
                bitsConsumedInRegion += zeros + 1
                return .success(count + zeros)
            }
            // Every buffered bit is 0 — consume them all and keep scanning.
            count += bitsInBuffer
            bitsConsumedInRegion += bitsInBuffer
            bitsInBuffer = 0
        }
    }

    // The final region can contain at most seven zero fill bits, including the
    // seven data bits in a stuffed zero following FF. Surplus entropy is invalid.
    mutating func validateEndOfScan() -> QualifiedFailure? {
        refill()
        guard position == bytes.count, bitsInBuffer <= 7 else { return QualifiedFailure(.invalidEntropy) }
        let mask: UInt64 = (1 << bitsInBuffer) - 1
        guard bitBuffer & mask == 0 else { return QualifiedFailure(.invalidEntropy) }
        return nil
    }

    internal mutating func resetBitBuffer() {
        if bitsConsumedInRegion > 0 {
            var pos = bitRegionStart
            var remaining = bitsConsumedInRegion
            let count = bytes.count
            while remaining > 0 && pos < count {
                let byte = bytes[pos]
                if byte == 0xFF && pos + 1 < count && bytes[pos + 1] < 0x80 {
                    pos += 2
                    remaining -= 15
                } else {
                    pos += 1
                    remaining -= 8
                }
            }
            position = pos
        }
        bitBuffer = 0
        bitsInBuffer = 0
        bitRegionStart = position
        bitsConsumedInRegion = 0
    }

    internal mutating func seek(to position: Int) -> QualifiedFailure? {
        guard position >= 0 && position <= bytes.count else {
            return QualifiedFailure(.seekPosition, position)
        }
        bitBuffer = 0
        bitsInBuffer = 0
        bitsConsumedInRegion = 0
        self.position = position
        bitRegionStart = position
        return nil
    }
}
