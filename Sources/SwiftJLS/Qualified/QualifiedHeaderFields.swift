// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Core/JPEGLSHeaderFields.swift; Core/JPEGLSFrameHeader.swift; Core/JPEGLSScanHeader.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal enum QualifiedInterleaveMode: UInt8, Sendable, Equatable {
    case none = 0

    case line = 1

    case sample = 2

    internal func isValid(forComponentCount componentCount: Int) -> Bool {
        switch self {
        case .none:
            // No interleaving is always valid
            return true
        case .line, .sample:
            // Interleaving requires multiple components
            return componentCount > 1
        }
    }
}
internal enum QualifiedFrameHeader {
    internal struct ComponentSpec: Sendable, Equatable {
        internal let id: UInt8

        internal let horizontalSamplingFactor: UInt8

        internal let verticalSamplingFactor: UInt8

        internal init(
            id: UInt8,
            horizontalSamplingFactor: UInt8 = 1,
            verticalSamplingFactor: UInt8 = 1
        ) {
            self.id = id
            self.horizontalSamplingFactor = horizontalSamplingFactor
            self.verticalSamplingFactor = verticalSamplingFactor
        }
    }
}
internal enum QualifiedScanHeader {
    internal struct ComponentSelector: Sendable, Equatable {
        internal let id: UInt8

        internal let mappingTableID: UInt8

        internal init(id: UInt8, mappingTableID: UInt8 = 0) {
            self.id = id
            self.mappingTableID = mappingTableID
        }
    }
}
internal enum QualifiedColorTransformation: UInt8, Sendable, Equatable { case none = 0, hp1 = 1, hp2 = 2, hp3 = 3 }
// Fixed scalar header facts shared by both parser storage policies.
internal struct QualifiedInline4<Element> {
    private var a: Element, b: Element, c: Element, d: Element
    private(set) var count = 0
    init(repeating value: Element) { a = value; b = value; c = value; d = value }
    mutating func append(_ value: Element) {
        precondition(count < 4)
        switch count { case 0: a = value; case 1: b = value; case 2: c = value; default: d = value }
        count += 1
    }
    subscript(index: Int) -> Element {
        precondition(index >= 0 && index < count)
        switch index { case 0: return a; case 1: return b; case 2: return c; default: return d }
    }

}
extension QualifiedInline4 where Element == QualifiedFrameHeader.ComponentSpec {
    func containsID(_ id: UInt8) -> Bool {
        for index in 0..<count where self[index].id == id { return true }; return false
    }
}
internal struct QualifiedFrameFields {
    let bitsPerSample: Int, height: Int, width: Int, componentCount: Int
    let components: QualifiedInline4<QualifiedFrameHeader.ComponentSpec>
    init(bitsPerSample: Int, height: Int, width: Int, componentCount: Int,
         components: QualifiedInline4<QualifiedFrameHeader.ComponentSpec>) {
        self.bitsPerSample = bitsPerSample; self.height = height; self.width = width
        self.componentCount = componentCount; self.components = components
    }

    static func validate(bitsPerSample: Int, height: Int, width: Int, componentCount: Int,
                         actualComponentCount: Int) -> QualifiedFailure? {

        // Validate bits per sample
        guard bitsPerSample >= 2 && bitsPerSample <= 16 else {
            return QualifiedFailure(.invalidBitsPerSample, bitsPerSample)
        }

        // Validate dimensions.
        // Standard JPEG-LS SOF supports up to 65535 per dimension; dimensions
        // greater than 65535 use LSE type 4 (extended dimensions) per ITU-T.87 §5.1.1.4.
        // Maximum supported dimension is 2^32 – 1 (32-bit LSE type 4 encoding).
        guard width > 0 && height > 0 else {
            return QualifiedFailure(.invalidDimensions, width, height)
        }

        guard UInt64(width) <= UInt64(UInt32.max) && UInt64(height) <= UInt64(UInt32.max) else {
            return QualifiedFailure(.invalidDimensions, width, height)
        }

        // Validate component count
        guard componentCount >= 1 && componentCount <= 4 else {
            return QualifiedFailure(.invalidComponentCount, componentCount)
        }

        // Validate components array matches count
        guard actualComponentCount == componentCount else {
            return QualifiedFailure(.frameComponentMismatch, componentCount, actualComponentCount)
        }

        return nil
    }
}
internal struct QualifiedScanFields {
    let componentCount: Int, near: Int, pointTransform: Int
    let interleaveMode: QualifiedInterleaveMode
    let components: QualifiedInline4<QualifiedScanHeader.ComponentSelector>
    init(componentCount: Int, components: QualifiedInline4<QualifiedScanHeader.ComponentSelector>,
         near: Int, interleaveMode: QualifiedInterleaveMode, pointTransform: Int) {
        self.componentCount = componentCount; self.components = components
        self.near = near; self.interleaveMode = interleaveMode; self.pointTransform = pointTransform
    }

    static func validate(componentCount: Int, actualComponentCount: Int, near: Int,
                         interleaveMode: QualifiedInterleaveMode, pointTransform: Int) -> QualifiedFailure? {

        // Validate component count
        guard componentCount >= 1 && componentCount <= 4 else {
            return QualifiedFailure(.invalidComponentCount, componentCount)
        }

        // Validate components array matches count
        guard actualComponentCount == componentCount else {
            return QualifiedFailure(.scanComponentMismatch, componentCount, actualComponentCount)
        }

        // Validate NEAR parameter
        guard near >= 0 && near <= 255 else {
            return QualifiedFailure(.invalidNearParameter, near)
        }

        // Validate interleave mode for component count
        guard interleaveMode.isValid(forComponentCount: componentCount) else {
            return QualifiedFailure(.scanInterleave, Int(interleaveMode.rawValue), componentCount)
        }

        // Validate point transform
        guard pointTransform >= 0 && pointTransform <= 15 else {
            return QualifiedFailure(.pointTransform, pointTransform)
        }

        return nil
    }
    func validate(against frameHeader: QualifiedFrameFields) -> QualifiedFailure? {

        // Check that all component IDs exist in frame
        for index in 0..<componentCount {
            let component = components[index]
            guard frameHeader.components.containsID(component.id) else {
                return QualifiedFailure(.unknownScanComponent, Int(component.id))
            }
        }

        // For non-interleaved mode, scan must have exactly 1 component
        if interleaveMode == .none && componentCount != 1 {
            return QualifiedFailure(.noninterleavedCount, componentCount)
        }

        // For interleaved modes, all frame components should be in scan
        if interleaveMode != .none && componentCount != frameHeader.componentCount {
            return QualifiedFailure(.interleavedCount, frameHeader.componentCount, componentCount)
        }
        return nil
    }
}
