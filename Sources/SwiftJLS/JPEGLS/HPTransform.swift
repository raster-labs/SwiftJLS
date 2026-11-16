// SPDX-License-Identifier: MIT
// Copyright 2026 Raster Images Private Limited
// Original scalar implementation of the HP reversible RGB lifting transforms.
// APP8 `mrfx` is a private convention, not a claim of T.870 conformance.
// Independently qualified against isolated CharLS 2.4.2; see migration evidence.

/// All arithmetic is in Int / Int32; only the reversible modular outputs are narrowed.
/// Callers admit precisely three components and 8/16-bit full-range lossless data.
enum HPTransform {
    @inline(__always)
    static func forward(_ r: Int, _ g: Int, _ b: Int,
                        transform: CodecOptions.ColourTransform, bits: Int) -> (Int, Int, Int) {
        let modulus = 1 << bits, mask = modulus - 1, bias = modulus / 2
        let redDifference = (r - g + bias) & mask
        let blueDifference = (b - g + bias) & mask
        switch transform {
        case .none: return (r, g, b)
        case .hp1: return (redDifference, g, blueDifference)
        case .hp2: return (redDifference, g, (b - ((r + g) >> 1) + bias) & mask)
        case .hp3:
            let luma = (g + ((redDifference + blueDifference) >> 2) - (modulus >> 2)) & mask
            return (luma, blueDifference, redDifference)
        }
    }

    @inline(__always)
    static func forwardSIMD8(
        _ r: SIMD8<Int32>, _ g: SIMD8<Int32>, _ b: SIMD8<Int32>,
        transform: CodecOptions.ColourTransform, bits: Int
    ) -> (SIMD8<Int32>, SIMD8<Int32>, SIMD8<Int32>) {
        let mod = Int32(1 << bits)
        let maskVec = SIMD8<Int32>(repeating: mod &- 1)
        let biasVec = SIMD8<Int32>(repeating: mod >> 1)
        let redDiff = (r &- g &+ biasVec) & maskVec
        let blueDiff = (b &- g &+ biasVec) & maskVec
        switch transform {
        case .none:
            return (r, g, b)
        case .hp1:
            return (redDiff, g, blueDiff)
        case .hp2:
            let halfRG = (r &+ g) &>> 1
            return (redDiff, g, (b &- halfRG &+ biasVec) & maskVec)
        case .hp3:
            let quarterVec = SIMD8<Int32>(repeating: mod >> 2)
            let quarterSum = (redDiff &+ blueDiff) &>> 2
            let luma = (g &+ quarterSum &- quarterVec) & maskVec
            return (luma, blueDiff, redDiff)
        }
    }

    @inline(__always)
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
                return (red, second, (third + ((red + second) >> 1)) & mask)
            case .hp3:
                let red = (first + third) & mask
                return (red, (second + ((red + third) >> 1)) & mask, third)
            }
        }
        switch transform {
        case .none: return (first, second, third)
        case .hp1: return ((first + second - bias) & mask, second, (third + second - bias) & mask)
        case .hp2:
            let red = (first + second - bias) & mask
            return (red, second, (third + ((red + second) >> 1) - bias) & mask)
        case .hp3:
            let green = (first - ((second + third) >> 2) + (modulus >> 2)) & mask
            return ((third + green - bias) & mask, green, (second + green - bias) & mask)
        }
    }

    @inline(__always)
    static func inverseSIMD8(
        _ first: SIMD8<Int32>, _ second: SIMD8<Int32>, _ third: SIMD8<Int32>,
        transform: CodecOptions.ColourTransform, bits: Int,
        interpretation: CodecOptions.HPInterpretation = .standard
    ) -> (SIMD8<Int32>, SIMD8<Int32>, SIMD8<Int32>) {
        let mod = Int32(1 << bits)
        let maskVec = SIMD8<Int32>(repeating: mod &- 1)
        let biasVec = SIMD8<Int32>(repeating: mod >> 1)
        if interpretation == .legacyJLSwift {
            switch transform {
            case .none:
                return (first, second, third)
            case .hp1:
                return ((first &+ second) & maskVec, second, (third &+ second) & maskVec)
            case .hp2:
                let red = (first &+ second) & maskVec
                return (red, second, (third &+ ((red &+ second) &>> 1)) & maskVec)
            case .hp3:
                let red = (first &+ third) & maskVec
                return (red, (second &+ ((red &+ third) &>> 1)) & maskVec, third)
            }
        }
        switch transform {
        case .none:
            return (first, second, third)
        case .hp1:
            return ((first &+ second &- biasVec) & maskVec, second, (third &+ second &- biasVec) & maskVec)
        case .hp2:
            let red = (first &+ second &- biasVec) & maskVec
            return (red, second, (third &+ ((red &+ second) &>> 1) &- biasVec) & maskVec)
        case .hp3:
            let quarterVec = SIMD8<Int32>(repeating: mod >> 2)
            let green = (first &- ((second &+ third) &>> 2) &+ quarterVec) & maskVec
            return ((third &+ green &- biasVec) & maskVec, green, (second &+ green &- biasVec) & maskVec)
        }
    }

    static func inverseInPlace(
        views: [ComponentSampleWriter],
        count: Int,
        transform: CodecOptions.ColourTransform,
        bits: Int,
        interpretation: CodecOptions.HPInterpretation,
        checkpoint: () throws -> Void
    ) throws {
        guard count > 0, views.count >= 3 else { return }
        let v0 = views[0], v1 = views[1], v2 = views[2]
        let width = v0.width, height = v0.height
        let sb = v0.sampleBytes
        #if _endian(little)
        let nativeEndian = v0.littleEndian && v1.littleEndian && v2.littleEndian
        #else
        let nativeEndian = !v0.littleEndian && !v1.littleEndian && !v2.littleEndian
        #endif
        let contiguousPlanes = v0.pixelStride == sb && v1.pixelStride == sb && v2.pixelStride == sb
            && v0.width == width && v1.width == width && v2.width == width
            && v0.height == height && v1.height == height
            && v0.bytes.baseAddress != nil && v1.bytes.baseAddress != nil && v2.bytes.baseAddress != nil

        if contiguousPlanes && (sb == 1 || nativeEndian) {
            for y in 0..<height {
                try checkpoint()
                let off0 = v0.offset &+ y &* v0.rowBytes
                let off1 = v1.offset &+ y &* v1.rowBytes
                let off2 = v2.offset &+ y &* v2.rowBytes
                var x = 0
                if sb == 1 {
                    while x &+ 8 <= width {
                        if x != 0 && (x & 255) == 0 { try checkpoint() }
                        let c0 = SIMD8<Int32>(truncatingIfNeeded: v0.bytes.loadUnaligned(fromByteOffset: off0 &+ x, as: SIMD8<UInt8>.self))
                        let c1 = SIMD8<Int32>(truncatingIfNeeded: v1.bytes.loadUnaligned(fromByteOffset: off1 &+ x, as: SIMD8<UInt8>.self))
                        let c2 = SIMD8<Int32>(truncatingIfNeeded: v2.bytes.loadUnaligned(fromByteOffset: off2 &+ x, as: SIMD8<UInt8>.self))
                        let (r, g, b) = inverseSIMD8(c0, c1, c2, transform: transform, bits: bits, interpretation: interpretation)
                        v0.bytes.storeBytes(of: SIMD8<UInt8>(truncatingIfNeeded: r), toByteOffset: off0 &+ x, as: SIMD8<UInt8>.self)
                        v1.bytes.storeBytes(of: SIMD8<UInt8>(truncatingIfNeeded: g), toByteOffset: off1 &+ x, as: SIMD8<UInt8>.self)
                        v2.bytes.storeBytes(of: SIMD8<UInt8>(truncatingIfNeeded: b), toByteOffset: off2 &+ x, as: SIMD8<UInt8>.self)
                        x &+= 8
                    }
                } else {
                    while x &+ 8 <= width {
                        if x != 0 && (x & 255) == 0 { try checkpoint() }
                        let byteX = x &* 2
                        let c0 = SIMD8<Int32>(truncatingIfNeeded: v0.bytes.loadUnaligned(fromByteOffset: off0 &+ byteX, as: SIMD8<UInt16>.self))
                        let c1 = SIMD8<Int32>(truncatingIfNeeded: v1.bytes.loadUnaligned(fromByteOffset: off1 &+ byteX, as: SIMD8<UInt16>.self))
                        let c2 = SIMD8<Int32>(truncatingIfNeeded: v2.bytes.loadUnaligned(fromByteOffset: off2 &+ byteX, as: SIMD8<UInt16>.self))
                        let (r, g, b) = inverseSIMD8(c0, c1, c2, transform: transform, bits: bits, interpretation: interpretation)
                        v0.bytes.storeBytes(of: SIMD8<UInt16>(truncatingIfNeeded: r), toByteOffset: off0 &+ byteX, as: SIMD8<UInt16>.self)
                        v1.bytes.storeBytes(of: SIMD8<UInt16>(truncatingIfNeeded: g), toByteOffset: off1 &+ byteX, as: SIMD8<UInt16>.self)
                        v2.bytes.storeBytes(of: SIMD8<UInt16>(truncatingIfNeeded: b), toByteOffset: off2 &+ byteX, as: SIMD8<UInt16>.self)
                        x &+= 8
                    }
                }
                let rowStart = y &* width
                while x < width {
                    let idx = rowStart &+ x
                    let rgb = inverse(Int(v0[idx]), Int(v1[idx]), Int(v2[idx]),
                        transform: transform, bits: bits, interpretation: interpretation)
                    v0[idx] = UInt16(rgb.0); v1[idx] = UInt16(rgb.1); v2[idx] = UInt16(rgb.2)
                    x &+= 1
                }
            }
            return
        }

        // General strided / interleaved SIMD8 path
        var i = 0
        while i &+ 8 <= count {
            if (i & 63) == 0 { try checkpoint() }
            let c0 = SIMD8<Int32>(
                Int32(v0[i]), Int32(v0[i &+ 1]), Int32(v0[i &+ 2]), Int32(v0[i &+ 3]),
                Int32(v0[i &+ 4]), Int32(v0[i &+ 5]), Int32(v0[i &+ 6]), Int32(v0[i &+ 7])
            )
            let c1 = SIMD8<Int32>(
                Int32(v1[i]), Int32(v1[i &+ 1]), Int32(v1[i &+ 2]), Int32(v1[i &+ 3]),
                Int32(v1[i &+ 4]), Int32(v1[i &+ 5]), Int32(v1[i &+ 6]), Int32(v1[i &+ 7])
            )
            let c2 = SIMD8<Int32>(
                Int32(v2[i]), Int32(v2[i &+ 1]), Int32(v2[i &+ 2]), Int32(v2[i &+ 3]),
                Int32(v2[i &+ 4]), Int32(v2[i &+ 5]), Int32(v2[i &+ 6]), Int32(v2[i &+ 7])
            )
            let (r, g, b) = inverseSIMD8(c0, c1, c2, transform: transform, bits: bits, interpretation: interpretation)
            for lane in 0..<8 {
                let idx = i &+ lane
                v0[idx] = UInt16(truncatingIfNeeded: r[lane])
                v1[idx] = UInt16(truncatingIfNeeded: g[lane])
                v2[idx] = UInt16(truncatingIfNeeded: b[lane])
            }
            i &+= 8
        }
        while i < count {
            if (i & 63) == 0 { try checkpoint() }
            let rgb = inverse(Int(v0[i]), Int(v1[i]), Int(v2[i]),
                transform: transform, bits: bits, interpretation: interpretation)
            v0[i] = UInt16(rgb.0); v1[i] = UInt16(rgb.1); v2[i] = UInt16(rgb.2)
            i &+= 1
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
        self[index] == value && self[index &+ 1] == value && self[index &+ 2] == value && self[index &+ 3] == value
    }
    func matchingPrefix(in range: Range<Int>, to value: UInt16) -> Int {
        var i = range.lowerBound
        guard i < range.upperBound, self[i] == value else { return 0 }
        i &+= 1
        let v0 = views[0], v1 = views[1], v2 = views[2]
        let target32 = SIMD8<Int32>(repeating: Int32(value))
        while i &+ 8 <= range.upperBound {
            let r = SIMD8<Int32>(
                Int32(v0[i]), Int32(v0[i &+ 1]), Int32(v0[i &+ 2]), Int32(v0[i &+ 3]),
                Int32(v0[i &+ 4]), Int32(v0[i &+ 5]), Int32(v0[i &+ 6]), Int32(v0[i &+ 7])
            )
            let g = SIMD8<Int32>(
                Int32(v1[i]), Int32(v1[i &+ 1]), Int32(v1[i &+ 2]), Int32(v1[i &+ 3]),
                Int32(v1[i &+ 4]), Int32(v1[i &+ 5]), Int32(v1[i &+ 6]), Int32(v1[i &+ 7])
            )
            let b = SIMD8<Int32>(
                Int32(v2[i]), Int32(v2[i &+ 1]), Int32(v2[i &+ 2]), Int32(v2[i &+ 3]),
                Int32(v2[i &+ 4]), Int32(v2[i &+ 5]), Int32(v2[i &+ 6]), Int32(v2[i &+ 7])
            )
            let f = HPTransform.forwardSIMD8(r, g, b, transform: transform, bits: bits)
            let out = component == 0 ? f.0 : (component == 1 ? f.1 : f.2)
            if out != target32 { break }
            i &+= 8
        }
        while i < range.upperBound && self[i] == value { i &+= 1 }
        return i &- range.lowerBound
    }
}
