// SPDX-License-Identifier: Apache-2.0
import Foundation
import Testing
import SwiftJLS

func expectCodecError(_ category: CodecError.Category,
                      _ operation: () throws -> Void,
                      sourceLocation: SourceLocation = #_sourceLocation) {
    do {
        try operation()
        Issue.record("Expected a defined codec error", sourceLocation: sourceLocation)
    } catch let error as CodecError {
        #expect(error.category == category, sourceLocation: sourceLocation)
    } catch {
        Issue.record("Expected CodecError; received \(error)", sourceLocation: sourceLocation)
    }
}

@Suite("Descriptor validation")
struct DescriptorTests {
    @Test func singletonMappingErrorPrecedesAlignment() throws {
        let mappingError = CodecError(.invalidArgument, "Each component must occur in exactly one plane.")
        for plane in [
            try PlaneDescriptor(width: 1, height: 1, components: [1], offset: 1, rowBytes: 2, byteCount: 4),
            try PlaneDescriptor(width: 1, height: 1, components: [1], sampleStride: 3, rowBytes: 2, byteCount: 4),
            try PlaneDescriptor(width: 1, height: 1, components: [1], pixelStride: 3, rowBytes: 4, byteCount: 4),
            try PlaneDescriptor(width: 1, height: 1, components: [1], rowBytes: 3, byteCount: 4)
        ] {
            #expect(throws: mappingError) {
                _ = try ImageDescriptor(width: 1, height: 1, planes: [plane])
            }
        }
        // Plane geometry still wins over both invalid mapping and alignment.
        let wrongWidth = try PlaneDescriptor(width: 2, height: 1, components: [1],
                                             offset: 1, rowBytes: 4, byteCount: 6)
        #expect(throws: CodecError(.incompatibleImageLayout,
                                  "Plane dimensions disagree with their explicit sampling factors.")) {
            _ = try ImageDescriptor(width: 1, height: 1, planes: [wrongWidth])
        }
    }

    @Test func singletonAndGeneralMappingMatrix() throws {
        // Valid singleton coverage includes every admitted storage width and
        // odd geometry with padding/prefix; this must retain exact extents.
        for (storageBits, sampleType) in [(8, SampleType.unsignedInteger),
                                          (16, .unsignedInteger), (32, .floatingPoint)] {
            let sampleBytes = storageBits / 8
            for offset in [0, sampleBytes * 2] {
                let rowBytes = sampleBytes * 4
                let capacity = offset + rowBytes + sampleBytes * 3
                let plane = try PlaneDescriptor(width: 3, height: 2, offset: offset,
                    sampleStride: sampleBytes, pixelStride: sampleBytes,
                    rowBytes: rowBytes, byteCount: capacity)
                let descriptor = try ImageDescriptor(width: 3, height: 2, sampleType: sampleType,
                    storageBits: storageBits, meaningfulBits: storageBits, planes: [plane])
                #expect(descriptor.requiredByteCount == capacity)
                #expect(descriptor.planes == [plane])
            }
        }
        let roles: [ComponentRole] = [.uninterpreted("A"), .uninterpreted("B")]
        let first = try PlaneDescriptor(width: 1, height: 1, components: [0], rowBytes: 2, byteCount: 4)
        let second = try PlaneDescriptor(width: 1, height: 1, components: [1], offset: 2,
                                         rowBytes: 2, byteCount: 4)
        let duplicate = try PlaneDescriptor(width: 1, height: 1, components: [0], offset: 2,
                                            rowBytes: 2, byteCount: 4)
        let overlap = try PlaneDescriptor(width: 1, height: 1, components: [1], rowBytes: 2, byteCount: 4)
        let packed = try PlaneDescriptor(width: 1, height: 1, components: [0, 1],
                                         pixelStride: 4, rowBytes: 4, byteCount: 4)
        for planes in [[first, second], [packed]] {
            let descriptor = try ImageDescriptor(width: 1, height: 1,
                components: roles, colour: .unknown, planes: planes)
            #expect(descriptor.requiredByteCount == 4)
        }
        for (components, planes, expected) in [
            (roles, [first], CodecError(.invalidArgument, "A component has no plane.")),
            (roles, [first, duplicate], CodecError(.invalidArgument, "Each component must occur in exactly one plane.")),
            ([.grey], [packed], CodecError(.invalidArgument, "Each component must occur in exactly one plane.")),
            ([.grey], [first, duplicate], CodecError(.invalidArgument, "Each component must occur in exactly one plane.")),
            (roles, [first, overlap], CodecError(.incompatibleImageLayout, "Writable plane ranges overlap."))
        ] {
            #expect(throws: expected) {
                _ = try ImageDescriptor(width: 1, height: 1,
                    components: components, colour: .unknown, planes: planes)
            }
        }
        // A valid singleton mapping must still reach alignment and byte limits.
        let misaligned = try PlaneDescriptor(width: 1, height: 1, offset: 1, rowBytes: 2, byteCount: 4)
        #expect(throws: CodecError(.incompatibleImageLayout, "Sample offsets and strides must be aligned.")) {
            _ = try ImageDescriptor(width: 1, height: 1, planes: [misaligned])
        }
        let small = try ResourceLimits(maximumDecodedBytes: 3)
        #expect(throws: CodecError(.resourceLimitExceeded, "Decoded storage limit exceeded.")) {
            _ = try ImageDescriptor(width: 1, height: 1, planes: [first], limits: small)
        }
    }

    @Test func paddedOddDimensionsAndPrecision() throws {
        let descriptor = try ImageDescriptor.greyscale16(
            width: 3, height: 5, meaningfulBits: 12, rowBytes: 8, offset: 2)
        #expect(descriptor.requiredByteCount == 42)
        #expect(descriptor.meaningfulBits == 12)
        #expect(descriptor.storageBits == 16)
        #expect(descriptor.planes[0].rowBytes == 8)
        #expect(descriptor.byteOrder == .littleEndian)
    }

    @Test func finalRowNeedsOnlyItsActualSampleBytes() throws {
        let plane = try PlaneDescriptor(width: 3, height: 2, offset: 2,
                                        rowBytes: 8, byteCount: 16)
        let descriptor = try ImageDescriptor(width: 3, height: 2, planes: [plane])
        #expect(descriptor.requiredByteCount == 16)
        let short = try PlaneDescriptor(width: 3, height: 2, offset: 2,
                                        rowBytes: 8, byteCount: 15)
        expectCodecError(.incompatibleImageLayout) {
            _ = try ImageDescriptor(width: 3, height: 2, planes: [short])
        }
    }

    @Test func rejectsInvalidGeometryAndPrecision() throws {
        for width in [0, -1, Int.min] {
            expectCodecError(.invalidArgument) {
                _ = try ImageDescriptor.greyscale16(width: width, height: 1)
            }
        }
        for bits in [-1, 0, 17, Int.max] {
            expectCodecError(.invalidArgument) {
                _ = try ImageDescriptor.greyscale16(width: 1, height: 1, meaningfulBits: bits)
            }
        }
        #expect(try ImageDescriptor.greyscale16(width: 1, height: 1).requiredByteCount == 2)
    }

    @Test func rejectsArithmeticOverflowBeforeAllocation() {
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor.greyscale16(width: Int.max, height: 1)
        }
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor.greyscale16(width: 1, height: 3, rowBytes: Int.max - 1)
        }
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor.greyscale16(width: 1, height: 1, offset: Int.max - 1)
        }
    }

    @Test func rejectsMisalignedOffsetsAndStrides() throws {
        for plane in [
            try PlaneDescriptor(width: 2, height: 2, offset: 1, rowBytes: 4, byteCount: 9),
            try PlaneDescriptor(width: 2, height: 2, pixelStride: 3, rowBytes: 6, byteCount: 12),
            try PlaneDescriptor(width: 2, height: 2, rowBytes: 5, byteCount: 10),
            try PlaneDescriptor(width: 2, height: 2, rowBytes: 2, byteCount: 8)
        ] {
            expectCodecError(.incompatibleImageLayout) {
                _ = try ImageDescriptor(width: 2, height: 2, planes: [plane])
            }
        }
        expectCodecError(.invalidArgument) {
            _ = try PlaneDescriptor(width: 1, height: 1, rowBytes: -2, byteCount: 2)
        }
    }

    @Test func rejectsInvalidPlaneComponentLists() throws {
        for components in [[-1], [0, 0]] {
            expectCodecError(.invalidArgument) {
                _ = try PlaneDescriptor(width: 1, height: 1, components: components,
                                        rowBytes: 4, byteCount: 4)
            }
        }
        let outOfRange = try PlaneDescriptor(width: 1, height: 1, components: [1],
                                            rowBytes: 2, byteCount: 2)
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor(width: 1, height: 1, planes: [outOfRange])
        }
    }

    @Test func rejectsOverlappingPlanesAndIncompleteMapping() throws {
        let first = try PlaneDescriptor(width: 1, height: 1, components: [0], rowBytes: 2, byteCount: 4)
        let overlap = try PlaneDescriptor(width: 1, height: 1, components: [1], rowBytes: 2, byteCount: 4)
        expectCodecError(.incompatibleImageLayout) {
            _ = try ImageDescriptor(width: 1, height: 1,
                                    components: [.uninterpreted("A"), .uninterpreted("B")],
                                    colour: .unknown, planes: [first, overlap])
        }
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor(width: 1, height: 1,
                                    components: [.uninterpreted("A"), .uninterpreted("B")],
                                    colour: .unknown, planes: [first])
        }
        let second = try PlaneDescriptor(width: 1, height: 1, components: [1], offset: 2,
                                         rowBytes: 2, byteCount: 4)
        #expect(try ImageDescriptor(width: 1, height: 1,
                                    components: [.uninterpreted("A"), .uninterpreted("B")],
                                    colour: .unknown, planes: [first, second]).planes.count == 2)
    }

    @Test func semanticMetadataMustAgreeWithComponents() throws {
        let plane = try PlaneDescriptor(width: 1, height: 1, rowBytes: 2, byteCount: 2)
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor(width: 1, height: 1, colour: .rgb, planes: [plane])
        }
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor(width: 1, height: 1, alpha: .straight, planes: [plane])
        }
        expectCodecError(.invalidArgument) {
            _ = try ImageDescriptor(width: 1, height: 1, components: [.alpha],
                                    colour: .unknown, planes: [plane])
        }
        let native = try ImageDescriptor(width: 1, height: 1, byteOrder: .native, planes: [plane])
        #expect(native.byteOrder != .native)
    }

    @Test func deterministicLayoutMutation() throws {
        // No random source: all offset/row-stride pairs for a 3x2 UInt16 image.
        for offset in 0..<8 {
            for rowBytes in 1..<12 {
                let plane = try PlaneDescriptor(width: 3, height: 2, offset: offset,
                                                rowBytes: rowBytes, byteCount: 32)
                let valid = offset.isMultiple(of: 2) && rowBytes.isMultiple(of: 2) && rowBytes >= 6
                if valid {
                    _ = try ImageDescriptor(width: 3, height: 2, planes: [plane])
                } else {
                    expectCodecError(.incompatibleImageLayout) {
                        _ = try ImageDescriptor(width: 3, height: 2, planes: [plane])
                    }
                }
            }
        }
    }
}
