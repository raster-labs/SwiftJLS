// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

private final class ObservedZeroReader: JPEGSampleReader {
    let count: Int
    var prefixRanges: [Range<Int>] = []
    var readIndices: [Int] = []
    init(count: Int) { self.count = count }
    subscript(index: Int) -> UInt16 {
        precondition((0..<count).contains(index))
        readIndices.append(index)
        return 0
    }
    func fourEqual(at index: Int, to value: UInt16) -> Bool {
        (0..<4).allSatisfy { self[index + $0] == value }
    }
    func matchingPrefix(in range: Range<Int>, to value: UInt16) -> Int {
        prefixRanges.append(range)
        var end = range.lowerBound
        while end < range.upperBound, self[end] == value { end += 1 }
        return end - range.lowerBound
    }
}

private final class ObservedRunWriter: JPEGSampleWriter {
    var samples: [UInt16]
    var fillRanges: [Range<Int>] = []
    var writtenIndices: [Int] = []
    var count: Int { samples.count }
    init(count: Int) { samples = Array(repeating: .max, count: count) }
    subscript(index: Int) -> UInt16 {
        get { samples[index] }
        set {
            writtenIndices.append(index)
            samples[index] = newValue
        }
    }
    func fill(_ value: UInt16, range: Range<Int>) {
        fillRanges.append(range)
        for index in range { self[index] = value }
    }
}

@Suite("Bounded scalar run checkpoints")
struct RunCheckpointTests {
    @Test func encodeCancelsBeforeReadingTheSecondRunChunk() throws {
        let width = 1025
        let source = ObservedZeroReader(count: width)
        let parameters = try JPEGLSPresetParameters.defaultParameters(bitsPerSample: 12)
        let regular = try JPEGLSRegularMode(parameters: parameters)
        let run = try JPEGLSRunMode(parameters: parameters)
        var context = try JPEGLSContextModel(parameters: parameters)
        var writer = JPEGLSBitstreamWriter()
        let kernel = JPEGLSScalarKernel()
        let coding = kernel.computeGolombLimitInternal(parameters: parameters, near: 0, bitsPerSample: 12)
        var checks = 0
        do {
            try kernel.encodeFlatRowsLossless(buf: source, rowStride: width, rowRange: 0..<1,
                sampleMaximum: parameters.maxValue, width: width, regularMode: regular, runMode: run,
                context: &context, writer: &writer, limit: coding.limit, qbppBits: coding.qbppBits,
                checkpoint: {
                    checks += 1
                    if checks == 2 { throw CancellationError() }
                })
            Issue.record("Encoding continued after cancellation.")
        } catch is CancellationError {
            // Row admission covers the first bounded chunk; cancellation must
            // stop the source traversal before it examines the second chunk.
        }
        #expect(source.prefixRanges == [0..<256])
        #expect(source.readIndices == Array(0..<256))
    }

    private func zeroCodestream(width: Int, height: Int) async throws -> Data {
        let descriptor = try ImageDescriptor.greyscale16(width: width, height: height, meaningfulBits: 12)
        let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { _, _ in 0 }
        return try await Encoder().encode(image).data
    }

    private func checkCancelledDecode(width: Int, height: Int, expectedSamples: Int) async throws {
        let data = try await zeroCodestream(width: width, height: height)
        let header = try JPEGLSHeader.parse(data, budget: .init(limits: .default))
        let scan = try #require(header.scans.first)
        let reader = JPEGLSBitstreamReader(data: data[scan])
        let output = ObservedRunWriter(count: width * height)
        let kernel = JPEGLSScalarKernel()
        let coding = kernel.computeGolombLimitInternal(parameters: header.parameters, near: header.near,
            bitsPerSample: header.bits)
        var checks = 0
        do {
            try kernel.decodeFlatRegion(into: output, rowStride: width, reader: reader, rows: height,
                width: width, parameters: header.parameters, near: header.near,
                limit: coding.limit, qbppBits: coding.qbppBits, checkpoint: {
                    checks += 1
                    if checks == 2 { throw CancellationError() }
                })
            Issue.record("Decoding continued after cancellation.")
        } catch is CancellationError {
            // Observe actual written ranges and untouched samples, rather than
            // treating a particular callback count as sufficient evidence.
        }
        #expect(output.writtenIndices == Array(0..<expectedSamples))
        #expect(output.fillRanges == (expectedSamples == 0 ? [] : [0..<expectedSamples]))
        #expect(Array(output.samples.prefix(expectedSamples)) == [UInt16](repeating: 0, count: expectedSamples))
        #expect(output.samples.dropFirst(expectedSamples).allSatisfy { $0 == .max })
    }

    @Test func shortRunDecodeCancelsBeforeWritingTheNextRow() async throws {
        try await checkCancelledDecode(width: 37, height: 2, expectedSamples: 37)
    }

    @Test func longRunDecodeChecksAfterParsingBeforeWriting() async throws {
        try await checkCancelledDecode(width: 1025, height: 1, expectedSamples: 0)
    }
}
