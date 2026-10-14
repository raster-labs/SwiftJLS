// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Scan scheduling adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc,
// JPEGLSEncoder.encodeLineInterleaved/encodeSampleInterleaved and corresponding
// decoder paths. Full-frame Int matrices are replaced by scoped component views
// and, for near-lossless coding, two UInt16 predictor rows per component.
import Foundation

extension JPEGLSScalarKernel {
    struct Neighbours {
        let a: Int, b: Int, c: Int, d: Int
        static let zero = Self(a: 0, b: 0, c: 0, d: 0)
    }
    struct PredictorRows {
        var previous: [UInt16], current: [UInt16]
        var edge = 0, oldEdge = 0
        init(width: Int) {
            previous = .init(repeating: 0, count: width)
            current = .init(repeating: 0, count: width)
        }
        mutating func beginRow() { oldEdge = edge; edge = Int(previous[0]) }
        mutating func finishRow() { swap(&previous, &current) }
        func neighbours(x: Int) -> Neighbours {
            Neighbours(a: x == 0 ? Int(previous[0]) : Int(current[x - 1]), b: Int(previous[x]),
                c: x == 0 ? oldEdge : Int(previous[x - 1]), d: Int(previous[min(x + 1, previous.count - 1)]))
        }
    }
    func encodeInterleaved<Reader: JPEGSampleReader>(views: [Reader], width: Int, height: Int,
                           mode: CodecOptions.InterleaveMode, near: Int, parameters: JPEGLSPresetParameters,
                           bits: Int, writer: inout JPEGLSBitstreamWriter, checkpoint: () throws -> Void) throws {
        guard (1...4).contains(views.count) else { throw CodecError(.unsupportedFeature, "Invalid component count.") }
        let regular = try JPEGLSRegularMode(parameters: parameters, near: near)
        let run = try JPEGLSRunMode(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)
        let coding = computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: bits)
        if mode == .line && near == 0 {
            var indices = InlineArray<4, Int>(repeating: 0)
            for y in 0..<height {
                for c in views.indices {
                    context.setRunIndex(indices[c])
                    try encodeFlatRowsLossless(buf: views[c], rowStride: width, rowRange: y..<(y + 1),
                        scanFirstRow: 0, width: width, regularMode: regular, runMode: run,
                        context: &context, writer: &writer, limit: coding.limit,
                        qbppBits: coding.qbppBits, checkpoint: checkpoint)
                    indices[c] = context.currentRunIndex
                }
            }
            return
        }
        // Exact reconstruction can read already-encoded neighbours from the
        // scoped source. Only near-lossless coding needs reconstructed rows.
        var states = near == 0 ? [] : views.map { _ in PredictorRows(width: width) }
        var indices = InlineArray<4, Int>(repeating: 0)
        var neighbours = InlineArray<4, Neighbours>(repeating: .zero)
        for y in 0..<height {
            try checkpoint(); try writer.checkLimit()
            for c in states.indices { states[c].beginRow() }
            for group in 0..<(mode == .line ? views.count : 1) {
                let active = mode == .line ? group..<(group + 1) : 0..<views.count
                if mode == .line { context.setRunIndex(indices[group]) }
                var x = 0
                while x < width {
                    if x & 63 == 0 { try checkpoint(); try writer.checkLimit() }
                    var isRun = true
                    for c in active {
                        let n = near == 0 ? sourceNeighbours(views[c], width: width, x: x, y: y)
                            : states[c].neighbours(x: x)
                        neighbours[c] = n
                        if abs(n.d - n.b) > near || abs(n.b - n.c) > near || abs(n.c - n.a) > near { isRun = false }
                    }
                    if isRun {
                        let first = x
                        if near == 0 {
                            // Scan each component through its scoped local view.
                            // The shortest matching prefix is the joint run;
                            // later components never scan beyond that prefix.
                            var end = width
                            for c in active {
                                let view = views[c], value = UInt16(neighbours[c].a)
                                var candidate = first
                                while candidate < end {
                                    try checkpoint(); try writer.checkLimit()
                                    let stop = min(end, candidate + 256)
                                    let base = y * width
                                    candidate += view.matchingPrefix(in: (base + candidate)..<(base + stop), to: value)
                                    if candidate < stop { break }
                                }
                                end = candidate
                                if end == first { break }
                            }
                            x = end
                        }
                        while x < width {
                            if x & 63 == 0 { try checkpoint(); try writer.checkLimit() }
                            var matches = true
                            for c in active {
                                if abs(Int(views[c][y * width + x]) - neighbours[c].a) > near { matches = false; break }
                            }
                            if !matches { break }
                            x += 1
                        }
                        // Reconstruct a whole bounded run slice per component.
                        // Predictor rows are not read again until the run ends.
                        for start in stride(from: first, to: near == 0 ? first : x, by: 64) {
                            try checkpoint(); try writer.checkLimit()
                            let end = min(x, start + 64)
                            for c in active {
                                let value = UInt16(neighbours[c].a)
                                states[c].current.withUnsafeMutableBufferPointer { row in
                                    for index in start..<end { row[index] = value }
                                }
                            }
                        }
                        let encoded = run.encodeRunLength(runLength: x - first, runIndex: context.currentRunIndex)
                        writer.writeOnes(encoded.continuationBits)
                        context.setRunIndex(min(encoded.runIndex + encoded.continuationBits, 31))
                        if x < width {
                            writeRunTermination(encoded: encoded, writer: &writer)
                            for c in active {
                                let value = writeRunInterruptionBits(interruptionValue: Int(views[c][y * width + x]),
                                    runValue: neighbours[c].a,
                                    rb: near == 0 ? (y == 0 ? 0 : Int(views[c][(y - 1) * width + x])) : Int(states[c].previous[x]), near: near,
                                    context: &context, regularMode: regular, runMode: run, writer: &writer,
                                    limit: coding.limit, qbppBits: coding.qbppBits, overrideRiType: mode == .sample ? 0 : nil)
                                if near > 0 { states[c].current[x] = UInt16(value) }
                            }
                            context.decrementRunIndex(); x += 1
                        } else if encoded.remainder > 0 { writer.writeBits(1, count: 1) }
                    } else {
                        for c in active {
                            let n = neighbours[c]
                            let value = encodePixel(actual: Int(views[c][y * width + x]), a: n.a, b: n.b, c: n.c,
                                q1: regular.quantizeGradient(n.d - n.b), q2: regular.quantizeGradient(n.b - n.c),
                                q3: regular.quantizeGradient(n.c - n.a), regularMode: regular, context: &context,
                                writer: &writer, limit: coding.limit, qbppBits: coding.qbppBits)
                            if near > 0 { states[c].current[x] = UInt16(value) }
                        }
                        x += 1
                    }
                }
                if mode == .line { indices[group] = context.currentRunIndex }
            }
            for c in states.indices { states[c].finishRow() }
        }
    }
    @inline(__always)
    private func sourceNeighbours<Reader: JPEGSampleReader>(_ view: Reader, width: Int, x: Int, y: Int) -> Neighbours {
        let previous = (y - 1) * width
        let b = y > 0 ? Int(view[previous + x]) : 0
        return Neighbours(a: x == 0 ? b : Int(view[y * width + x - 1]), b: b,
            c: x == 0 ? (y > 1 ? Int(view[(y - 2) * width]) : 0)
                : (y > 0 ? Int(view[previous + x - 1]) : 0),
            d: y > 0 ? Int(view[previous + min(x + 1, width - 1)]) : 0)
    }
    func decodedNeighbours(_ view: ComponentSampleWriter, x: Int, y: Int, edge: Int) -> Neighbours {
        let width = view.width
        let b = y > 0 ? Int(view[(y - 1) * width + x]) : 0
        return Neighbours(a: x == 0 ? b : Int(view[y * width + x - 1]), b: b,
            c: x == 0 ? edge : (y > 0 ? Int(view[(y - 1) * width + x - 1]) : 0),
            d: y > 0 ? Int(view[(y - 1) * width + min(x + 1, width - 1)]) : 0)
    }
    func decodeInterleaved(views: [ComponentSampleWriter], width: Int, height: Int,
                           mode: JPEGLSInterleaveMode, near: Int, parameters: JPEGLSPresetParameters,
                           bits: Int, reader: JPEGLSBitstreamReader, verticalSampling: [Int]? = nil, checkpoint: () throws -> Void) throws {
        guard (1...4).contains(views.count) else { throw CodecError(.unsupportedFeature, "Invalid component count.") }
        let decoder = try JPEGLSRegularModeDecoder(parameters: parameters, near: near)
        let run = try JPEGLSRunModeDecoder(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)
        let coding = computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: bits)
        var indices = InlineArray<4, Int>(repeating: 0)
        var edges = InlineArray<4, Int>(repeating: 0)
        let vertical = verticalSampling ?? Array(repeating: 1, count: views.count)
        let vMax = vertical.max() ?? 1
        let stripes = mode == .line ? (height + vMax - 1) / vMax : height
        if mode == .line {
            for stripe in 0..<stripes {
                for c in views.indices {
                    let view = views[c]
                    for row in 0..<vertical[c] {
                        let y = stripe * vertical[c] + row
                        if y >= view.height { continue }
                        try checkpoint()
                        let edge = edges[c]
                        if y > 0 { edges[c] = Int(view[(y - 1) * view.width]) }
                        context.setRunIndex(indices[c])
                        if view.pixelStride == view.sampleBytes && view.rowBytes % view.sampleBytes == 0 {
                            let scalar = ScalarSampleWriter(bytes: .init(rebasing: view.bytes[view.offset...]),
                                littleEndian: view.littleEndian, sampleBytes: view.sampleBytes)
                            try decodeRow(into: scalar, rowStride: view.rowBytes / view.sampleBytes, row: y, width: view.width,
                                edgeForThisRow: edge, reader: reader, decoder: decoder, runDecoder: run,
                                context: &context, parameters: parameters, near: near,
                                limit: coding.limit, qbppBits: coding.qbppBits, checkpointMask: 63,
                                checkpoint: checkpoint)
                        } else {
                            try decodeRow(into: view, rowStride: view.width, row: y, width: view.width,
                                edgeForThisRow: edge, reader: reader, decoder: decoder, runDecoder: run,
                                context: &context, parameters: parameters, near: near,
                                limit: coding.limit, qbppBits: coding.qbppBits, checkpointMask: 63,
                                checkpoint: checkpoint)
                        }
                        indices[c] = context.currentRunIndex
                    }
                }
            }
            return
        }
        var oldEdges = edges
        var neighbours = InlineArray<4, Neighbours>(repeating: .zero)
        let active = views.indices
        for y in 0..<height {
            try checkpoint()
            for c in active {
                oldEdges[c] = edges[c]
                if y > 0 { edges[c] = Int(views[c][(y - 1) * width]) }
            }
            var x = 0
            while x < width {
                if x & 63 == 0 { try checkpoint() }
                var isRun = true
                for c in active {
                    let n = decodedNeighbours(views[c], x: x, y: y, edge: oldEdges[c]); neighbours[c] = n
                    if abs(n.d - n.b) > near || abs(n.b - n.c) > near || abs(n.c - n.a) > near { isRun = false }
                }
                if isRun {
                    let remaining = width - x
                    let length = try readRunLength(reader: reader, runDecoder: run, context: &context, remainingInLine: remaining)
                    for start in stride(from: x, to: x + length, by: 64) {
                        try checkpoint()
                        let end = min(x + length, start + 64)
                        for c in active { views[c].fill(UInt16(neighbours[c].a), range: (y * width + start)..<(y * width + end)) }
                    }
                    x += length
                    if length < remaining {
                        let adjustedLimit = coding.limit - run.computeJ(runIndex: context.currentRunIndex) - 1
                        for c in active {
                            let ra = neighbours[c].a
                            let rb = y > 0 ? Int(views[c][(y - 1) * width + x]) : 0
                            let type = 0
                            let k = context.computeRunInterruptionGolombK(riType: type)
                            let mapped = try readGolombCode(reader: reader, k: k, limit: adjustedLimit, qbppBits: coding.qbppBits)
                            let error = context.computeRunInterruptionErrorValue(temp: mapped + type, k: k, riType: type)
                            let value = run.reconstructSample(prediction: type == 1 ? ra : rb,
                                error: type == 1 ? error : error * (rb >= ra ? 1 : -1))
                            context.updateRunInterruptionContext(errorValue: error, eMappedErrorValue: mapped, riType: type)
                            views[c][y * width + x] = UInt16(value)
                        }
                        context.decrementRunIndex(); x += 1
                    }
                } else {
                    for c in active {
                        let n = neighbours[c]
                        let value = try decodeSinglePixel(reader: reader, decoder: decoder, runDecoder: run,
                            context: &context, a: n.a, b: n.b, c: n.c,
                            q1: decoder.quantizeGradient(n.d - n.b), q2: decoder.quantizeGradient(n.b - n.c),
                            q3: decoder.quantizeGradient(n.c - n.a), parameters: parameters, near: near,
                            limit: coding.limit, qbppBits: coding.qbppBits)
                        views[c][y * width + x] = UInt16(value)
                    }
                    x += 1
                }
            }
        }
    }
}
