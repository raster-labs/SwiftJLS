// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Upstream Sources/JPEGLS/Core/JPEGLSMarker.swift
// Adapted from raster-labs/JLSwift d17545284a23e93f3d884a18f1046c4e305daa35.
// Qualified synchronous caller-storage subset; no legacy owning/throwing adapters.
internal enum QualifiedMarker: UInt8, Sendable {
    // MARK: - Start and End Markers

    case startOfImage = 0xD8

    case endOfImage = 0xD9

    // MARK: - Frame Markers

    case startOfFrameQualified = 0xF7

    case startOfScan = 0xDA

    // MARK: - JPEG-LS Specific Markers

    case jpegLSExtension = 0xF8

    // MARK: - Application and Comment Markers

    case applicationMarker0 = 0xE0
    case applicationMarker1 = 0xE1
    case applicationMarker2 = 0xE2
    case applicationMarker3 = 0xE3
    case applicationMarker4 = 0xE4
    case applicationMarker5 = 0xE5
    case applicationMarker6 = 0xE6
    case applicationMarker7 = 0xE7
    case applicationMarker8 = 0xE8
    case applicationMarker9 = 0xE9
    case applicationMarker10 = 0xEA
    case applicationMarker11 = 0xEB
    case applicationMarker12 = 0xEC
    case applicationMarker13 = 0xED
    case applicationMarker14 = 0xEE
    case applicationMarker15 = 0xEF

    case comment = 0xFE

    // MARK: - Restart Markers

    case restart0 = 0xD0
    case restart1 = 0xD1
    case restart2 = 0xD2
    case restart3 = 0xD3
    case restart4 = 0xD4
    case restart5 = 0xD5
    case restart6 = 0xD6
    case restart7 = 0xD7

    // MARK: - Interval and Line Markers

    case defineNumberOfLines = 0xDC

    case defineRestartInterval = 0xDD

    internal static let markerPrefix: UInt8 = 0xFF

    internal var bytes: (UInt8, UInt8) {
        return (QualifiedMarker.markerPrefix, self.rawValue)
    }

    internal var hasLength: Bool {
        switch self {
        case .startOfImage, .endOfImage, .restart0, .restart1, .restart2,
             .restart3, .restart4, .restart5, .restart6, .restart7:
            return false
        default:
            return true
        }
    }
}

internal enum QualifiedExtensionType: UInt8, Sendable {
    case presetCodingParameters = 0x01

    case mappingTable = 0x02

    case mappingTableContinuation = 0x03

    case extendedDimensions = 0x04
}
