// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
@testable import SwiftJLS

private enum QualifiedTestError: Error { case unexpectedOutcome }
private struct QualifiedTestCancellation {
    var calls = 0
    var cancelAt = Int.max
}

@Suite("Qualified monochrome caller workspace")
struct QualifiedMonochromeTests {
    private let decoder = QualifiedMonochromeDecoder(profile: .jlswift0101)

    private func fixture(_ name: String, _ ext: String = "jls") throws -> Data {
        let url = try #require(Bundle.module.url(forResource: name, withExtension: ext, subdirectory: "Fixtures"))
        return try Data(contentsOf: url)
    }
    private func value<T>(_ result: QualifiedOutcome<T>) throws -> T {
        switch result {
        case .success(let value): return value
        case .failure(let failure):
            Issue.record("Unexpected qualified failure: \(failure.code) [\(failure.operand0), \(failure.operand1)]")
            throw QualifiedTestError.unexpectedOutcome
        }
    }
    private func failure<T>(_ result: QualifiedOutcome<T>, _ code: QualifiedFailure.Code? = nil) {
        switch result {
        case .success: Issue.record("Expected qualified failure")
        case .failure(let actual): if let code { #expect(actual.code == code) }
        }
    }
    private func withWorkspace<T>(_ body: (UnsafeMutableRawBufferPointer) throws -> T) rethrows -> T {
        let count = QualifiedMonochromeDecoder.workspaceByteCount
        let raw = UnsafeMutableRawPointer.allocate(byteCount: count + 32, alignment: 16)
        raw.initializeMemory(as: UInt8.self, repeating: 0xa5, count: count + 32)
        defer {
            let all = UnsafeRawBufferPointer(start: raw, count: count + 32)
            #expect(all.prefix(16).allSatisfy { $0 == 0xa5 })
            #expect(all.suffix(16).allSatisfy { $0 == 0xa5 })
            raw.deallocate()
        }
        return try body(.init(start: raw.advanced(by: 16), count: count))
    }
    private func decode(_ data: Data) throws -> (QualifiedMonochromeDecoder.MonochromeInfo, [UInt16]) {
        try withWorkspace { scratch in
            try data.withUnsafeBytes { encoded in
                let info = try value(decoder.inspect(encoded, workspace: scratch))
                var guarded = [UInt16](repeating: 0xbeef, count: info.sampleCount + 3)
                let result = guarded.withUnsafeMutableBufferPointer { all in
                    decoder.decode(encoded, into: .init(rebasing: all[1..<(info.sampleCount + 2)]), workspace: scratch)
                }
                #expect(try value(result) == info)
                #expect(guarded[0] == 0xbeef && guarded[info.sampleCount + 1] == 0xbeef && guarded.last == 0xbeef)
                return (info, Array(guarded[1...info.sampleCount]))
            }
        }
    }
    private func samples(_ data: Data) -> [UInt16] {
        stride(from: 0, to: data.count, by: 2).map { UInt16(data[$0]) | UInt16(data[$0 + 1]) << 8 }
    }
    private var oneZero: Data {
        Data([0xff,0xd8, 0xff,0xf7,0,11,8,0,1,0,1,1,1,0x11,0,
              0xff,0xda,0,8,1,1,0,0,0,0, 0x80,0xff,0xd9])
    }

    @Test func nonthrowingSignaturesAndExactScratch() throws {
        let inspect: (UnsafeRawBufferPointer, UnsafeMutableRawBufferPointer, QualifiedCancellation)
            -> QualifiedOutcome<QualifiedMonochromeDecoder.MonochromeInfo> = decoder.inspect
        let reconstruct: (UnsafeRawBufferPointer, UnsafeMutableBufferPointer<UInt16>, UnsafeMutableRawBufferPointer, QualifiedCancellation)
            -> QualifiedOutcome<QualifiedMonochromeDecoder.MonochromeInfo> = decoder.decode
        try withWorkspace { scratch in
            try oneZero.withUnsafeBytes { input in
                #expect(try value(inspect(input, scratch, .init())).sampleCount == 1)
                var output: UInt16 = 99
                try withUnsafeMutablePointer(to: &output) { pixel in
                    let info = try value(reconstruct(input, .init(start: pixel, count: 1), scratch, .init()))
                    #expect(info.bitsPerSample == 8)
                }
                #expect(output == 0)
            }
        }
    }

    @Test func independentCharLSSamplesAndNearLossless() throws {
        // CharLS fixtures: see Fixtures/manifest.json. Low-MAXVAL defaults differ
        // deliberately in this profile, so those are tested as compatibility below.
        for bits in [8, 12, 16] {
            for name in ["p\(bits)-17x13-noise", "p\(bits)-33x9-zero", "p\(bits)-23x1-ramp"] {
                #expect(try decode(fixture(name)).1 == samples(fixture(name, "u16le")))
            }
            let name = "n3-p\(bits)-17x13-noise"
            #expect(try decode(fixture(name)).1 == samples(fixture(name, "decoded.u16le")))
        }
        for name in ["custom-p4-m10-n3-reset3", "custom-p16-m4095-n0-reset3"] {
            #expect(try decode(fixture(name)).1 == samples(fixture(name, "decoded.u16le")))
        }
    }

    @Test func standardHighNearThresholdsMustBeExplicitInLegacyProfile() throws {
        // The exact predecessor fails these original implicit-standard streams.
        // Supplying their independent standard defaults explicitly changes only
        // parameter signalling, never the CharLS entropy or expected samples.
        let cases: [(String, Int, Int)] = [
            ("n127-p8-1x19-noise",8,128), ("n127-p8-17x13-noise",8,128),
            ("n255-p9-1x19-noise",9,256), ("n255-p9-17x13-noise",9,256),
            ("n255-p10-17x13-noise",10,771),
            ("r13-n127-p8-1x19-noise",8,128), ("r65535-n127-p8-1x19-noise",8,128),
            ("r3-n127-p8-17x13-noise",8,128), ("r13-n127-p8-17x13-noise",8,128),
            ("r65535-n127-p8-17x13-noise",8,128)
        ]
        for (name,bits,threshold) in cases {
            var data = try fixture(name)
            let sos = try #require(data.range(of: Data([255,218])))
            var preset: [UInt8] = [255,248,0,13,1]
            for item in [(1 << bits) - 1,threshold,threshold,threshold,64] {
                preset += [UInt8(item >> 8),UInt8(item & 255)]
            }
            data.insert(contentsOf: preset, at: sos.lowerBound)
            #expect(try decode(data).1 == samples(fixture(name, "decoded.u16le")))
        }
    }

    @Test func restartEnvelopesAndMarkerFill() throws {
        for interval in [1, 3, 13, 65535] {
            let name = "r\(interval)-p12-17x13-noise"
            let original = try fixture(name)
            #expect(try decode(original).1 == samples(fixture(name, "u16le")))
            var filled = Data()
            for i in original.indices {
                if original[i] == 255, i + 1 < original.count,
                   original[i + 1] == 0xd9 || (0xd0...0xd7).contains(original[i + 1]) {
                    filled.append(contentsOf: [255, 255])
                }
                filled.append(original[i])
            }
            #expect(try decode(filled).1 == samples(fixture(name, "u16le")))
        }
        var bad = try fixture("r1-p12-17x13-noise")
        let restart = try #require(bad.range(of: Data([255,0xd0])))
        bad[restart.lowerBound + 1] = 0xd7
        withWorkspace { scratch in bad.withUnsafeBytes { failure(decoder.inspect($0, workspace: scratch), .restartCycle) } }
    }

    @Test func legacyMappingAndExtendedDimensionFixtures() throws {
        // Existing pinned predecessor fixtures and expected formula are recorded
        // in Fixtures/legacy-extra.json and PredecessorProfileTests.
        for width in [1, 2] {
            let result = try decode(fixture("legacy-mapping-w\(width)"))
            #expect(result.0.hasMappingTables)
            #expect(result.1 == [0,1,32764,32765,65535].map { UInt16(($0 * 271) & (width == 1 ? 255 : 65535)) })
        }
        for (width, height) in [(65537, 1), (1, 65537)] {
            let result = try decode(fixture("legacy-extended-\(width)x\(height)"))
            #expect(result.0.width == width && result.0.height == height)
            #expect(result.1 == (0..<(width * height)).map { UInt16((($0 % width) * 17 + ($0 / width) * 3) & 255) })
        }
    }

    @Test func explicitPointTransformAndLowPrecisionProfile() throws {
        var point = try fixture("p8-17x13-noise")
        let sos = try #require(point.range(of: Data([255,218])))
        point[sos.lowerBound + 9] = 3
        let result = try decode(point)
        #expect(result.0.pointTransform == 3)
        #expect(result.1 == samples(try fixture("p8-17x13-noise", "u16le")))
        for precision in 2...7 {
            var flat = oneZero; flat[6] = UInt8(precision)
            #expect(try decode(flat).1 == [0])
        }
        for marker in [1,2,3,4] {
            var hp = oneZero
            hp.insert(contentsOf: [255,232,0,7,0x6d,0x72,0x66,0x78,UInt8(marker)], at: 2)
            withWorkspace { scratch in hp.withUnsafeBytes { failure(decoder.inspect($0, workspace: scratch), .unsupportedProfile) } }
        }
    }

    @Test func rejectsTruncationSurplusEntropyAndNonzeroPadding() throws {
        let input = try fixture("p12-17x13-noise")
        withWorkspace { scratch in
            for end in 0..<input.count {
                input.prefix(end).withUnsafeBytes { failure(decoder.inspect($0, workspace: scratch)) }
            }
        }
        var extra = oneZero; extra.insert(0, at: extra.count - 2)
        var pad = oneZero; pad[pad.count - 3] |= 1
        for data in [extra, pad] {
            withWorkspace { scratch in
                data.withUnsafeBytes { encoded in
                    var output: UInt16 = 0xbeef
                    withUnsafeMutablePointer(to: &output) {
                        failure(decoder.decode(encoded, into: .init(start: $0, count: 1), workspace: scratch), .invalidEntropy)
                    }
                }
            }
        }
    }

    @Test func spansRejectBeforeWriting() throws {
        let data = oneZero
        try withWorkspace { scratch in
            try data.withUnsafeBytes { input in
                let before = Array(scratch)
                failure(decoder.inspect(input, workspace: .init(rebasing: scratch.dropLast())), .invalidCallerSpans)
                #expect(Array(scratch) == before)
                failure(decoder.inspect(input, workspace: .init(rebasing: scratch.dropFirst())), .invalidCallerSpans)
                #expect(Array(scratch) == before)
                scratch.copyBytes(from: input)
                let afterCopy = Array(scratch)
                failure(decoder.inspect(.init(rebasing: UnsafeRawBufferPointer(scratch).prefix(input.count)), workspace: scratch), .invalidCallerSpans)
                #expect(Array(scratch) == afterCopy)
                var output: UInt16 = 0xbeef
                withUnsafeMutablePointer(to: &output) { pixel in
                    failure(decoder.decode(input, into: .init(start: pixel, count: 0), workspace: scratch), .destinationTooSmall)
                }
                #expect(output == 0xbeef)
                let outputInScratch = scratch.bindMemory(to: UInt16.self)
                failure(decoder.decode(input, into: .init(rebasing: outputInScratch.prefix(1)), workspace: scratch), .overlappingBuffers)
                let raw = UnsafeMutableRawPointer.allocate(byteCount: 4, alignment: 2)
                defer { raw.deallocate() }
                raw.initializeMemory(as: UInt8.self, repeating: 0x5a, count: 4)
                let odd = raw.advanced(by: 1).assumingMemoryBound(to: UInt16.self)
                failure(decoder.decode(input, into: .init(start: odd, count: 1), workspace: scratch), .overlappingBuffers)
                #expect(UnsafeRawBufferPointer(start: raw, count: 4).allSatisfy { $0 == 0x5a })
                _ = try value(decoder.inspect(input, workspace: scratch))
            }
        }
    }

    @Test func independentBudgetsAndFiniteDeadlineAdmission() throws {
        let bytes = QualifiedMonochromeDecoder.workspaceByteCount
        let data = oneZero
        let limits: [QualifiedMonochromeDecoder.Limits] = [
            .init(maximumEncodedBytes: 1), .init(maximumWorkspaceBytes: bytes - 1),
            .init(maximumMemoryBytes: bytes + data.count - 1), .init(maximumPixels: 0),
            .init(deadlineSeconds: .nan), .init(deadlineSeconds: .infinity),
            .init(deadlineSeconds: 0), .init(deadlineSeconds: -.infinity)
        ]
        withWorkspace { scratch in data.withUnsafeBytes { input in
            for limit in limits {
                failure(QualifiedMonochromeDecoder(profile: .jlswift0101, limits: limit).inspect(input, workspace: scratch))
            }
            let expired = QualifiedMonochromeDecoder(profile: .jlswift0101, limits: .init(deadlineSeconds: .leastNonzeroMagnitude))
            failure(expired.inspect(input, workspace: scratch), .deadlineExceeded)
        } }
        try withWorkspace { scratch in try data.withUnsafeBytes { input in
            for duration in [Double.greatestFiniteMagnitude, Double(UInt64.max) / 1_000_000_000,
                             (Double(UInt64.max) / 1_000_000_000).nextDown] {
                let long = QualifiedMonochromeDecoder(profile: .jlswift0101, limits: .init(deadlineSeconds: duration))
                let info = try value(long.inspect(input, workspace: scratch))
                #expect(info.sampleCount == 1)
            }
            var output: UInt16 = 0xbeef
            withUnsafeMutablePointer(to: &output) { pixel in
                let total = QualifiedMonochromeDecoder(profile: .jlswift0101,
                    limits: .init(maximumMemoryBytes: bytes + data.count + 1))
                failure(total.decode(input, into: .init(start: pixel, count: 1), workspace: scratch), .decodedLimit)
            }
            #expect(output == 0xbeef)
        } }
    }

    @Test func cancellationBeforeAndDuringRunWrites() async throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 1025, height: 1, meaningfulBits: 8)
        let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { _,_ in 0 }
        let data = try await Encoder().encode(image).data
        withWorkspace { scratch in data.withUnsafeBytes { input in
            var output = [UInt16](repeating: 0xbeef, count: 1025)
            output.withUnsafeMutableBufferPointer { pixels in
                failure(decoder.decode(input, into: pixels, workspace: scratch,
                    cancellation: .init(check: { _ in true })), .cancelled)
                #expect(pixels.allSatisfy { $0 == 0xbeef })
                let check: @convention(c) (UnsafeMutableRawPointer?) -> Bool = { raw in
                    guard let raw else { return true }
                    let state = raw.assumingMemoryBound(to: QualifiedTestCancellation.self)
                    state.pointee.calls += 1
                    return state.pointee.calls >= state.pointee.cancelAt
                }
                // Establish the count with an independent callback-owned token.
                // No callback may read/write any borrowed codec span.
                var state = QualifiedTestCancellation()
                let baseline = withUnsafeMutablePointer(to: &state) { context in
                    decoder.decode(input, into: pixels, workspace: scratch,
                        cancellation: .init(check: check, context: context))
                }
                guard case .success = baseline else { Issue.record("Count-only decode failed"); return }
                #expect(pixels.allSatisfy { $0 == 0 })
                // After the second fill-chunk checkpoint, this single-row stream
                // has three further fill checks, EOI and palette checks. Cancel
                // there; assert the observable bounded write prefix after return.
                let cancelAt = state.calls - 5
                #expect(cancelAt > 0)
                pixels.update(repeating: 0xbeef)
                state = QualifiedTestCancellation(cancelAt: cancelAt)
                withUnsafeMutablePointer(to: &state) { context in
                    failure(decoder.decode(input, into: pixels, workspace: scratch,
                        cancellation: .init(check: check, context: context)), .cancelled)
                }
                let changed = pixels.filter { $0 != 0xbeef }.count
                #expect(changed > 0 && changed <= 256)
                #expect(pixels.dropFirst(changed).allSatisfy { $0 == 0xbeef })
            }
        } }
    }

    @Test func rejectsUnsupportedMarkersBeforeSampleWrites() throws {
        let segments: [[UInt8]] = [
            [255,0xc0,0,2], [255,0xf8,0,3,5],
            [255,0xf8,0,4,4,3], [255,0xdc,0,4,0,1], [255,0xd0]
        ]
        withWorkspace { scratch in
            for segment in segments {
                var data = oneZero
                data.insert(contentsOf: segment, at: data.count - 2)
                data.withUnsafeBytes { input in
                    var output: UInt16 = 0xbeef
                    withUnsafeMutablePointer(to: &output) {
                        failure(decoder.decode(input, into: .init(start: $0, count: 1), workspace: scratch))
                    }
                    #expect(output == 0xbeef)
                }
            }
        }
        // APP/COM remain uninterpreted ancillary payloads, including marker bytes.
        var opaque = oneZero
        opaque.insert(contentsOf: [255,0xe1,0,6,255,216,0,1,255,0xfe,0,4,255,0], at: 2)
        #expect(try decode(opaque).1 == [0])
    }

    @Test func selectedPaletteMustExistAndCoverEveryIndex() throws {
        var absent = oneZero; absent[21] = 7
        withWorkspace { scratch in absent.withUnsafeBytes { input in
            var output: UInt16 = 0xbeef
            withUnsafeMutablePointer(to: &output) {
                failure(decoder.decode(input, into: .init(start: $0, count: 1), workspace: scratch), .missingMappingTable)
            }
            #expect(output == 0xbeef)
        } }
        var short = try fixture("p8-17x13-noise")
        short.insert(contentsOf: [255,248,0,6,2,7,1,0], at: 2)
        let sos = try #require(short.range(of: Data([255,218])))
        short[sos.lowerBound + 6] = 7
        try withWorkspace { scratch in try short.withUnsafeBytes { input in
            let info = try value(decoder.inspect(input, workspace: scratch))
            var output = [UInt16](repeating: 0xbeef, count: info.sampleCount)
            output.withUnsafeMutableBufferPointer {
                failure(decoder.decode(input, into: $0, workspace: scratch), .mappingIndex)
            }
        } }
        // An unrelated valid table does not affect a scan whose selector is zero.
        var unused = oneZero; unused.insert(contentsOf: [255,248,0,6,2,7,1,99], at: 2)
        #expect(try decode(unused).1 == [0])
    }

    @Test func malformedUnaryAndInterruptedRunCannotGrowContextState() {
        // Run interruption at the first sample followed by an overlong unary code.
        var unary = oneZero; unary.replaceSubrange(25..<26, with: [0,0,0,0,0,0,0,0,128])
        // Twelve full run blocks give28 samples; an interruption remainder7
        // exceeds a width30 row. Bits1111111111110111 use FF stuffing.
        var run = oneZero; run[10] = 30
        run.replaceSubrange(25..<26, with: [255,0x7b,0x80])
        withWorkspace { scratch in
            for data in [unary, run] {
                data.withUnsafeBytes { input in
                    var output = [UInt16](repeating: 0xbeef, count: 30)
                    output.withUnsafeMutableBufferPointer {
                        failure(decoder.decode(input, into: $0, workspace: scratch), .invalidEntropy)
                    }
                    #expect(output.allSatisfy { $0 == 0xbeef })
                }
            }
        }
    }

    @Test func fullCapacityLimitsAndInputOutputAlias() throws {
        let count = QualifiedMonochromeDecoder.workspaceByteCount
        withWorkspace { scratch in oneZero.withUnsafeBytes { encoded in
            let input = UnsafeMutableRawPointer.allocate(byteCount: encoded.count + 4, alignment: 16)
            defer { input.deallocate() }
            guard let base = encoded.baseAddress else { Issue.record("Missing prepared input"); return }
            input.copyMemory(from: base, byteCount: encoded.count)
            let raw = UnsafeRawBufferPointer(start: input, count: encoded.count)
            let alias = UnsafeMutableBufferPointer(start: input.assumingMemoryBound(to: UInt16.self), count: 1)
            failure(decoder.decode(raw, into: alias, workspace: scratch), .overlappingBuffers)
            #expect(Array(raw) == Array(encoded))
            var output = [UInt16](repeating: 0xbeef, count: 2)
            output.withUnsafeMutableBufferPointer {
                let limits = QualifiedMonochromeDecoder.Limits(maximumDecodedBytes: 2)
                failure(QualifiedMonochromeDecoder(profile: .jlswift0101, limits: limits)
                    .decode(encoded, into: $0, workspace: scratch), .decodedLimit)
            }
            #expect(output == [0xbeef,0xbeef])
            let tooMuchScratch = UnsafeMutableRawPointer.allocate(byteCount: count + 16, alignment: 16)
            defer { tooMuchScratch.deallocate() }
            let limited = QualifiedMonochromeDecoder(profile: .jlswift0101, limits: .init(maximumWorkspaceBytes: count))
            failure(limited.inspect(encoded, workspace: .init(start: tooMuchScratch, count: count + 16)), .invalidCallerSpans)
        } }
        let large = try fixture("legacy-extended-65537x1")
        withWorkspace { scratch in large.withUnsafeBytes {
            failure(QualifiedMonochromeDecoder(profile: .jlswift0101, limits: .init(maximumDimension: 65535))
                .inspect($0, workspace: scratch), .decodedLimit)
        } }
        var maximum = oneZero
        for index in 7...10 { maximum[index] = 0 }
        maximum.insert(contentsOf: [255,248,0,12,4,4,255,255,255,255,255,255,255,255], at: 2)
        withWorkspace { scratch in maximum.withUnsafeBytes { failure(decoder.inspect($0, workspace: scratch)) } }
    }

    @Test func pinnedPredecessorNonflatLowPrecisionAndFinalPresetSelection() throws {
        // Generated by exact d175 source; retained script/source hashes/provenance
        // distinguish this compatibility oracle from the independent CharLS data.
        for name in ["p2-noise", "p7-noise", "p8-final-preset", "p8-near127"] {
            let encodedURL = try #require(Bundle.module.url(forResource: name, withExtension: "jls", subdirectory: "Fixtures/qualified-d175"))
            let expectedURL = try #require(Bundle.module.url(forResource: name, withExtension: "u16le", subdirectory: "Fixtures/qualified-d175"))
            let encoded = try Data(contentsOf: encodedURL)
            let expected = try Data(contentsOf: expectedURL)
            #expect(try decode(encoded).1 == samples(expected))
        }
    }
}
