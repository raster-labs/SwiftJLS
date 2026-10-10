// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Original scalar implementation of the HP reversible RGB lifting transforms.
// APP8 `mrfx` is a private convention, not a claim of T.870 conformance.
// Independently qualified against isolated CharLS 2.4.2; see migration evidence.

/// All arithmetic is in Int; only the reversible modular outputs are narrowed.
/// Callers admit precisely three components and 8/16-bit full-range lossless data.
enum HPTransform {
    static func forward(_ r: Int, _ g: Int, _ b: Int,
                        transform: CodecOptions.ColourTransform, bits: Int) -> (Int, Int, Int) {
        let modulus = 1 << bits, mask = modulus - 1, bias = modulus / 2
        let redDifference = (r - g + bias) & mask
        let blueDifference = (b - g + bias) & mask
        switch transform {
        case .none: return (r, g, b)
        case .hp1: return (redDifference, g, blueDifference)
        case .hp2: return (redDifference, g, (b - (r + g) / 2 + bias) & mask)
        case .hp3:
            let luma = (g + (redDifference + blueDifference) / 4 - modulus / 4) & mask
            return (luma, blueDifference, redDifference)
        }
    }
    static func inverse(_ first: Int, _ second: Int, _ third: Int,
                        transform: CodecOptions.ColourTransform, bits: Int,
                        interpretation: CodecOptions.HPInterpretation = .standard) -> (Int, Int, Int) {
        let modulus = 1 << bits, mask = modulus - 1, bias = modulus / 2
        if interpretation == .legacyJLSwift {
            // Adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc,
            // Core/JPEGLSColorTransformation.swift; explicit opt-in only.
            switch transform {
            case .none: return (first, second, third)
            case .hp1: return ((first + second) & mask, second, (third + second) & mask)
            case .hp2:
                let red = (first + second) & mask
                return (red, second, (third + (red + second) / 2) & mask)
            case .hp3:
                let red = (first + third) & mask
                return (red, (second + (red + third) / 2) & mask, third)
            }
        }
        switch transform {
        case .none: return (first, second, third)
        case .hp1: return ((first + second - bias) & mask, second, (third + second - bias) & mask)
        case .hp2:
            let red = (first + second - bias) & mask
            return (red, second, (third + (red + second) / 2 - bias) & mask)
        case .hp3:
            let green = (first - (second + third) / 4 + modulus / 4) & mask
            return ((third + green - bias) & mask, green, (second + green - bias) & mask)
        }
    }
}

/// Reads transformed values from the sealed RGB owner without a frame copy.
/// The three small views share the same synchronous borrow, never escaping it.
struct HPComponentReader: JPEGSampleReader {
    let views: [ComponentSampleReader]
    let component: Int
    let transform: CodecOptions.ColourTransform
    let bits: Int
    var count: Int { views[0].count }
    subscript(index: Int) -> UInt16 {
        let value = HPTransform.forward(Int(views[0][index]), Int(views[1][index]), Int(views[2][index]),
            transform: transform, bits: bits)
        return UInt16(component == 0 ? value.0 : component == 1 ? value.1 : value.2)
    }
    func fourEqual(at index: Int, to value: UInt16) -> Bool {
        (index..<(index + 4)).allSatisfy { self[$0] == value }
    }
}
