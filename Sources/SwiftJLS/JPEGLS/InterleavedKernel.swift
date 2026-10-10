// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Scan scheduling adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc,
// JPEGLSEncoder.encodeLineInterleaved/encodeSampleInterleaved and corresponding
// decoder paths. Full-frame Int matrices are replaced by scoped component views
// and two UInt16 predictor rows per encoded component.
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
    func encodeInterleaved(views: [ComponentSampleReader], width: Int, height: Int,
                           mode: CodecOptions.InterleaveMode, near: Int, parameters: JPEGLSPresetParameters,
                           bits: Int, writer: JPEGLSBitstreamWriter, checkpoint: () throws -> Void) throws {
        let regular = try JPEGLSRegularMode(parameters: parameters, near: near)
        let run = try JPEGLSRunMode(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)
        let coding = computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: bits)
        var states = views.map { _ in PredictorRows(width: width) }
        var indices = [Int](repeating: 0, count: views.count)
        var neighbours = [Neighbours](repeating: .zero, count: views.count)
        for y in 0..<height {
            try checkpoint()
            for c in views.indices { states[c].beginRow() }
            for group in 0..<(mode == .line ? views.count : 1) {
                let active = mode == .line ? group..<(group + 1) : 0..<views.count
                if mode == .line { context.setRunIndex(indices[group]) }
                var x = 0
                while x < width {
                    if x & 63 == 0 { try checkpoint() }
                    var isRun = true
                    for c in active {
                        let n = states[c].neighbours(x: x); neighbours[c] = n
                        if regular.quantizeGradient(n.d - n.b) != 0 || regular.quantizeGradient(n.b - n.c) != 0 || regular.quantizeGradient(n.c - n.a) != 0 { isRun = false }
                    }
                    if isRun {
                        let first = x
                        while x < width {
                            if x & 63 == 0 { try checkpoint() }
                            var matches = true
                            for c in active {
                                if abs(Int(views[c][y * width + x]) - neighbours[c].a) > near { matches = false; break }
                            }
                            if !matches { break }
                            for c in active { states[c].current[x] = UInt16(neighbours[c].a) }
                            x += 1
                        }
                        let encoded = run.encodeRunLength(runLength: x - first, runIndex: context.currentRunIndex)
                        writer.writeOnes(encoded.continuationBits)
                        context.setRunIndex(min(encoded.runIndex + encoded.continuationBits, 31))
                        if x < width {
                            writeRunTermination(encoded: encoded, writer: writer)
                            for c in active {
                                let value = writeRunInterruptionBits(interruptionValue: Int(views[c][y * width + x]),
                                    runValue: neighbours[c].a, rb: Int(states[c].previous[x]), near: near,
                                    context: &context, regularMode: regular, runMode: run, writer: writer,
                                    limit: coding.limit, qbppBits: coding.qbppBits, overrideRiType: mode == .sample ? 0 : nil)
                                states[c].current[x] = UInt16(value)
                            }
                            context.decrementRunIndex(); x += 1
                        } else if encoded.remainder > 0 { writer.writeBits(1, count: 1) }
                    } else {
                        for c in active {
                            let n = neighbours[c]
                            let value = encodePixel(actual: Int(views[c][y * width + x]), a: n.a, b: n.b, c: n.c,
                                q1: regular.quantizeGradient(n.d - n.b), q2: regular.quantizeGradient(n.b - n.c),
                                q3: regular.quantizeGradient(n.c - n.a), regularMode: regular, context: &context,
                                writer: writer, limit: coding.limit, qbppBits: coding.qbppBits)
                            states[c].current[x] = UInt16(value)
                        }
                        x += 1
                    }
                }
                if mode == .line { indices[group] = context.currentRunIndex }
            }
            for c in views.indices { states[c].finishRow() }
        }
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
                           bits: Int, reader: JPEGLSBitstreamReader, checkpoint: () throws -> Void) throws {
        let decoder = try JPEGLSRegularModeDecoder(parameters: parameters, near: near)
        let run = try JPEGLSRunModeDecoder(parameters: parameters, near: near)
        var context = try JPEGLSContextModel(parameters: parameters, near: near)
        let coding = computeGolombLimitInternal(parameters: parameters, near: near, bitsPerSample: bits)
        var indices = [Int](repeating: 0, count: views.count)
        var edges = [Int](repeating: 0, count: views.count)
        var oldEdges = edges
        var neighbours = [Neighbours](repeating: .zero, count: views.count)
        for y in 0..<height {
            try checkpoint()
            for c in views.indices {
                oldEdges[c] = edges[c]
                if y > 0 { edges[c] = Int(views[c][(y - 1) * width]) }
            }
            for group in 0..<(mode == .line ? views.count : 1) {
                let active = mode == .line ? group..<(group + 1) : 0..<views.count
                if mode == .line { context.setRunIndex(indices[group]) }
                var x = 0
                while x < width {
                    if x & 63 == 0 { try checkpoint() }
                    var isRun = true
                    for c in active {
                        let n = decodedNeighbours(views[c], x: x, y: y, edge: oldEdges[c]); neighbours[c] = n
                        if decoder.quantizeGradient(n.d - n.b) != 0 || decoder.quantizeGradient(n.b - n.c) != 0 || decoder.quantizeGradient(n.c - n.a) != 0 { isRun = false }
                    }
                    if isRun {
                        let remaining = width - x
                        let length = try readRunLength(reader: reader, runDecoder: run, context: &context, remainingInLine: remaining)
                        for column in x..<(x + length) {
                            if column & 63 == 0 { try checkpoint() }
                            for c in active { views[c][y * width + column] = UInt16(neighbours[c].a) }
                        }
                        x += length
                        if length < remaining {
                            let adjustedLimit = coding.limit - run.computeJ(runIndex: context.currentRunIndex) - 1
                            for c in active {
                                let ra = neighbours[c].a
                                let rb = y > 0 ? Int(views[c][(y - 1) * width + x]) : 0
                                let type = mode == .sample ? 0 : (abs(ra - rb) <= near ? 1 : 0)
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
                if mode == .line { indices[group] = context.currentRunIndex }
            }
        }
    }
}
