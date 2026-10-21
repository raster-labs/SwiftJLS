// SPDX-License-Identifier: Apache-2.0
import Foundation
import JPEGLS

// Diagnostic only: the codec and its checks are unchanged. Both controls use
// an explicitly preserved call boundary; no unchecked Sendability is added.
public enum AsyncBaselineCore {
    @inline(never) @concurrent public static func encode(_ image: MultiComponentImageData,
                                         configuration: JPEGLSEncoder.Configuration) async throws -> Data {
        try JPEGLSEncoder().encode(image, configuration: configuration)
    }

    @inline(never) @concurrent public static func decode(_ data: Data) async throws -> MultiComponentImageData {
        try JPEGLSDecoder().decode(data)
    }
}

// Matched ordinary-call control: same inputs/results and codec body, synchronous.
public enum SyncBaselineCore {
    @inline(never) public static func encode(_ image: MultiComponentImageData,
                                           configuration: JPEGLSEncoder.Configuration) throws -> Data {
        try JPEGLSEncoder().encode(image, configuration: configuration)
    }
    @inline(never) public static func decode(_ data: Data) throws -> MultiComponentImageData {
        try JPEGLSDecoder().decode(data)
    }
}
