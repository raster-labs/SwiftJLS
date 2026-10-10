// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
import SwiftJLS

@Suite struct APITests {
    @Test func nativeCodecCapabilitiesAndMalformedInputAreExplicit() async throws {
        let encoder = try SwiftJLS.Encoder()
        let decoder = try SwiftJLS.Decoder()
        #expect(encoder.capabilities.formats == ["JPEG-LS"])
        #expect(encoder.capabilities.canEncode && decoder.capabilities.canDecode && decoder.capabilities.canInspect)
        #expect(throws: CodecError.self) { try decoder.inspect(Data()) }
        await #expect(throws: CodecError.self) { try await decoder.decode(Data()) }
        let descriptor = try ImageDescriptor.greyscale16(width: 3, height: 2)
        let destination = try ImageDestination.allocate(descriptor: descriptor)
        await #expect(throws: CodecError.self) { try await decoder.decode(Data(), into: destination) }
        let after = try destination.writeUInt16 { _, _ in 42 }
        #expect(try after.sampleUInt16(x: 2, y: 1) == 42)
    }

    @Test func defaultsAndUnsupportedFidelityAreExplicit() throws {
        #expect(try EncoderConfiguration().mode == .lossless)
        #expect(EncodeOptions().copyPolicy == .requireSharedStorage)
        #expect(DecodeOptions().metadataPolicy == .preserve)
        #expect(throws: CodecError.self) { try EncoderConfiguration(mode: .nearLossless(maximumAbsoluteError: 0)) }
        #expect(try EncoderConfiguration(mode: .nearLossless(maximumAbsoluteError: 1)).mode == .nearLossless(maximumAbsoluteError: 1))
        #expect(throws: CodecError.self) { try EncoderConfiguration(mode: .lossy) }
        let unknown = OperationReport(backend: .scalarCPU, fidelity: .exactSamples)
        #expect(unknown.pixelAllocationCount == nil)
        #expect(unknown.peakPixelBytes == nil)
        #expect(unknown.peakWorkspaceBytes == nil)
    }

    @Test func resourceAndRequiredBackendErrorsPrecedeUnsupportedCodec() async throws {
        let decoder = try Decoder()
        let small = try ResourceLimits(maximumCompressedBytes: 2, maximumDecodedBytes: 4, maximumMemoryBytes: 4)
        #expect(throws: CodecError(.resourceLimitExceeded, "Compressed input exceeds operation limits.")) {
            try decoder.inspect(Data([1, 2, 3]), options: DecodeOptions(resourceLimits: small))
        }
        #expect(throws: CodecError(.backendUnavailable, "No accelerated backend is implemented.")) {
            try decoder.inspect(Data(), options: DecodeOptions(executionPolicy: .required(.accelerated)))
        }
        #expect(throws: CodecError.self) { try OwnedImageStorage(byteCount: 5, limits: small) }
        #expect(throws: CodecError.self) { try ResourceLimits(deadlineSeconds: .infinity) }
        #expect(throws: CodecError.self) { try ResourceLimits(maximumWorkers: 0) }
        let edge = try OwnedImageStorage(byteCount: 4, limits: small)
        #expect(edge.byteCount == 4)
    }

    @Test func cancellationKeepsSwiftCancellationError() async throws {
        let task = Task {
            withUnsafeCurrentTask { $0?.cancel() }
            return try await Decoder().decode(Data())
        }
        await #expect(throws: CancellationError.self) { try await task.value }
    }

    @Test(arguments: [12, 16]) func exactSamplesAndZeroedPadding(precision: Int) throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 5, height: 3, meaningfulBits: precision,
                                                        rowBytes: 14, offset: 2)
        let maximum: UInt16 = precision == 12 ? 4095 : 65535
        let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { x, y in
            x == 0 ? 0 : (x == 4 ? maximum : UInt16(x * 251 + y * 17))
        }
        #expect(image.descriptor.meaningfulBits == precision)
        for y in 0..<3 {
            for x in 0..<5 {
                #expect(try image.sampleUInt16(x: x, y: y) == (x == 0 ? 0 : (x == 4 ? maximum : UInt16(x * 251 + y * 17))))
            }
        }
        try image.storage.withUnsafeBytes { bytes in
            #expect(bytes[0] == 0 && bytes[1] == 0)
            for y in 0..<3 {
                for offset in (2 + y * 14 + 10)..<(2 + (y + 1) * 14) { #expect(bytes[offset] == 0) }
            }
        }
        #expect(throws: CodecError.self) { try image.sampleUInt16(x: -1, y: 0) }
        #expect(throws: CodecError.self) { try image.sampleUInt16(x: 0, y: 3) }
    }

    @Test func outOfRangeTwelveBitSampleInvalidatesDestination() throws {
        let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1, meaningfulBits: 12)
        let destination = try ImageDestination.allocate(descriptor: descriptor)
        #expect(throws: CodecError.self) { try destination.writeUInt16 { _, _ in 4096 } }
        #expect(throws: CodecError.self) { try destination.writeUInt16 { _, _ in 0 } }
        #expect(throws: CodecError.self) { try destination.storage.reserveWrite() }
    }

    @Test func sampleHelperPreservesExplicitBigEndian() throws {
        let plane = try PlaneDescriptor(width: 1, height: 1, rowBytes: 2, byteCount: 2)
        let descriptor = try ImageDescriptor(width: 1, height: 1, byteOrder: .bigEndian, planes: [plane])
        let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { _, _ in 0xABCD }
        #expect(try image.sampleUInt16(x: 0, y: 0) == 0xABCD)
        try image.storage.withUnsafeBytes { #expect(Array($0) == [0xAB, 0xCD]) }
    }
}

@Test func metadataAndDestinationLimitsUseCallerBudget() throws {
    let descriptor = try ImageDescriptor.greyscale16(width: 1, height: 1)
    let image = try ImageDestination.allocate(descriptor: descriptor).writeUInt16 { _, _ in 7 }
    let metadata = ImageMetadata(entries: ["a": Data([1, 2])])
    let adequate = try ResourceLimits(maximumDecodedBytes: 2, maximumMetadataBytes: 3, maximumMemoryBytes: 5)
    let accepted = try Image(descriptor: descriptor, storage: image.storage, metadata: metadata, limits: adequate)
    #expect(accepted.metadata == metadata)
    let shortMetadata = try ResourceLimits(maximumMetadataBytes: 2)
    #expect(throws: CodecError.self) {
        try Image(descriptor: descriptor, storage: image.storage, metadata: metadata, limits: shortMetadata)
    }
    let shortMemory = try ResourceLimits(maximumMemoryBytes: 4)
    #expect(throws: CodecError.self) {
        try Image(descriptor: descriptor, storage: image.storage, metadata: metadata, limits: shortMemory)
    }
    let tooSmall = try ResourceLimits(maximumDecodedBytes: 1)
    #expect(throws: CodecError.self) { try ImageDestination.allocate(descriptor: descriptor, limits: tooSmall) }
}

@Test func actualTaskCancellationDuringFillPreventsPublication() async throws {
    let descriptor = try ImageDescriptor.greyscale16(width: 3, height: 2)
    let destination = try ImageDestination.allocate(descriptor: descriptor)
    let task = Task {
        try destination.write { bytes in
            bytes[0] = 1
            withUnsafeCurrentTask { $0?.cancel() }
        }
    }
    await #expect(throws: CancellationError.self) { try await task.value }
    #expect(throws: CodecError.self) { try destination.writeUInt16 { _, _ in 0 } }
    #expect(throws: CodecError.self) { try destination.storage.reserveWrite() }
}
