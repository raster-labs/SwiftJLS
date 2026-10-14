// SPDX-License-Identifier: Apache-2.0
import Foundation
import JPEGLS

// Diagnostic only: the codec and its checks are unchanged. No forced inlining,
// unchecked Sendability, detached tasks or actor annotations are introduced.
public enum AsyncBaselineCore {
    @concurrent public static func encode(_ image: MultiComponentImageData,
                                         configuration: JPEGLSEncoder.Configuration) async throws -> Data {
        try JPEGLSEncoder().encode(image, configuration: configuration)
    }

    @concurrent public static func decode(_ data: Data) async throws -> MultiComponentImageData {
        try JPEGLSDecoder().decode(data)
    }
}
