// SPDX-License-Identifier: Apache-2.0
// Copyright 2026 Raster Images Private Limited
// Adapted from JLSwift 15aa75164145414f3d5ffb801401c52d40cc5bcc, Sources/JPEGLS/Decoder/JPEGLSRunModeDecoder.swift.
// Internal implementation; the successor public API is defined in CodecAPI.swift.

/// JPEG-LS run mode decoding implementation per ITU-T.87.
///
/// Run mode decoding reverses the encoding process:
/// 1. Decode run length from bitstream using J[RUNindex] mapping
/// 2. Reconstruct run of identical pixel values
/// 3. Decode run interruption sample when run terminates
/// 4. Update context statistics for adaptation

import Foundation

/// Run mode decoder for JPEG-LS decompression.
///
/// The run mode decoder implements the inverse of the encoding algorithm:
/// 1. Detect if we should enter run mode (Ra == Rb)
/// 2. Decode run length from continuation bits and remainder
/// 3. Reconstruct the run of identical pixels using the run value (Ra)
/// 4. When run is interrupted, decode the interruption sample
/// 5. Update run index for adaptation
struct JPEGLSRunModeDecoder: Sendable {
    // MARK: - Properties

    /// Preset parameters controlling thresholds and limits
    private let parameters: JPEGLSPresetParameters

    /// Near-lossless parameter (0 for lossless mode)
    private let near: Int

    /// Maximum run length that can be decoded in one iteration
    private let maxRunLength: Int

    // MARK: - Initialization

    /// Initialize run mode decoder with preset parameters.
    ///
    /// - Parameters:
    ///   - parameters: Preset parameters (thresholds, MAXVAL, RESET)
    ///   - near: Near-lossless parameter (0 for lossless mode)
    ///   - maxRunLength: Maximum run length to decode (default: 65536)
    /// - Throws: `JPEGLSError.invalidNearParameter` if NEAR is invalid
    init(
        parameters: JPEGLSPresetParameters,
        near: Int = 0,
        maxRunLength: Int = 65536
    ) throws {
        guard near >= 0 && near <= 255 else {
            throw JPEGLSError.invalidNearParameter(near: near)
        }

        self.parameters = parameters
        self.near = near
        self.maxRunLength = maxRunLength
    }

    // MARK: - Run Detection

    /// Check if run mode should be entered.
    ///
    /// Per ITU-T.87 Section 4.5.1, run mode is entered when:
    /// - Ra == Rb (left and top neighbors are equal)
    ///
    /// This indicates a potentially flat region where run-length decoding
    /// should be used.
    ///
    /// - Parameters:
    ///   - a: Left neighbor pixel value (Ra)
    ///   - b: Top neighbor pixel value (Rb)
    /// - Returns: True if run mode should be entered
    func shouldEnterRunMode(a: Int, b: Int) -> Bool {
        return a == b
    }

    // MARK: - J[RUNindex] Mapping

    /// Standard J table per ITU-T.87 Annex J (Table J.1)
    private static let jTable: [Int] = [
        0, 0, 0, 0, 1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3,
        4, 4, 5, 5, 6, 6, 7, 7, 8, 9, 10, 11, 12, 13, 14, 15
    ]

    /// Compute the number of bits for encoding/decoding a run length.
    ///
    /// Per ITU-T.87 Annex J, J[RUNindex] determines the run length
    /// block size as 2^J[RUNindex].
    ///
    /// - Parameter runIndex: Current run index (0 to 31)
    /// - Returns: Number of bits for run length encoding (J value)
    func computeJ(runIndex: Int) -> Int {
        let idx = max(0, min(runIndex, Self.jTable.count - 1))
        return Self.jTable[idx]
    }

    // MARK: - Run-Length Decoding

    /// Decode a run length from continuation bits and remainder.
    ///
    /// Per ITU-T.87 Section 4.5, run decoding reverses the encoding:
    /// 1. Each '1' bit represents a full block of 2^J pixels
    /// 2. A '0' bit indicates termination
    /// 3. Following J bits contain the remainder
    ///
    /// This method reconstructs the total run length from the decoded values.
    ///
    /// - Parameters:
    ///   - continuationBits: Number of '1' continuation bits (each = 2^J pixels)
    ///   - remainder: Remainder value decoded from J bits
    ///   - runIndex: Current run index (determines J value)
    /// - Returns: Decoded run result with total run length
    func decodeRunLength(
        continuationBits: Int,
        remainder: Int,
        runIndex: Int
    ) -> DecodedRun {
        let j = computeJ(runIndex: runIndex)
        let blockSize = 1 << j  // 2^J

        // Total run length = (continuation blocks × block size) + remainder
        let totalRunLength = continuationBits * blockSize + remainder

        return DecodedRun(
            runIndex: runIndex,
            j: j,
            continuationBits: continuationBits,
            remainder: remainder,
            totalRunLength: totalRunLength
        )
    }

    /// Decode run length directly from raw bit values.
    ///
    /// This is an alternative interface that takes the raw continuation count
    /// and remainder bits as read from the bitstream.
    ///
    /// - Parameters:
    ///   - continuationCount: Number of '1' bits before the '0' terminator
    ///   - remainderBits: J-bit remainder value after the terminator
    ///   - runIndex: Current run index
    /// - Returns: Total decoded run length
    func decodeRunLengthDirect(
        continuationCount: Int,
        remainderBits: Int,
        runIndex: Int
    ) -> Int {
        let j = computeJ(runIndex: runIndex)
        let blockSize = 1 << j
        return continuationCount * blockSize + remainderBits
    }

    // MARK: - Run Interruption Decoding

    /// Decode a run interruption sample.
    ///
    /// When a run is interrupted, the differing pixel value is encoded
    /// using a prediction error similar to regular mode. This method
    /// reverses that encoding.
    ///
    /// Per ITU-T.87 Section 4.5.4:
    /// - The prediction is the run value (Ra == Rb)
    /// - MErrval is decoded using Golomb-Rice from bitstream
    /// - Errval is unmapped from non-negative
    /// - Sample = prediction + Errval
    ///
    /// - Parameters:
    ///   - mappedError: Non-negative mapped error (MErrval) from bitstream
    ///   - runValue: The value of the run (Ra == Rb)
    /// - Returns: Decoded run interruption result with sample value
    func decodeRunInterruption(
        mappedError: Int,
        runValue: Int
    ) -> DecodedRunInterruption {
        // The prediction is simply the run value
        let prediction = runValue

        // Unmap from non-negative to signed error
        let error = unmapError(mappedError)

        // Compute raw sample value
        var sample = prediction + error

        // Apply modular reduction if necessary
        let range = parameters.maxValue + 1
        if sample < 0 {
            sample += range
        } else if sample > parameters.maxValue {
            sample -= range
        }

        // Clamp to valid range [0, MAXVAL]
        sample = max(0, min(parameters.maxValue, sample))

        return DecodedRunInterruption(
            prediction: prediction,
            mappedError: mappedError,
            error: error,
            sample: sample
        )
    }

    /// Unmap a non-negative error back to signed error.
    ///
    /// Per ITU-T.87 Section 4.4.1, this reverses the mapping:
    /// - If MErrval is even: Errval = MErrval / 2
    /// - If MErrval is odd: Errval = -(MErrval + 1) / 2
    ///
    /// - Parameter mappedError: Non-negative mapped error (MErrval)
    /// - Returns: Signed prediction error
    func unmapError(_ mappedError: Int) -> Int {
        if mappedError % 2 == 0 {
            // Even: positive error
            return mappedError / 2
        } else {
            // Odd: negative error
            return -((mappedError + 1) / 2)
        }
    }

    /// Decode run interruption from Golomb-Rice encoded bitstream values.
    ///
    /// This method takes the raw Golomb-Rice decoded value and
    /// computes the interruption sample.
    ///
    /// - Parameters:
    ///   - unaryCount: Number of zeros in unary prefix (quotient)
    ///   - remainder: Binary remainder (k bits)
    ///   - k: Golomb-Rice parameter
    ///   - runValue: The value of the run (Ra == Rb)
    /// - Returns: Decoded run interruption result
    func decodeRunInterruptionFromBits(
        unaryCount: Int,
        remainder: Int,
        k: Int,
        runValue: Int
    ) -> DecodedRunInterruption {
        // Reconstruct mapped error from Golomb-Rice encoding
        let mappedError = (unaryCount << k) | remainder

        return decodeRunInterruption(mappedError: mappedError, runValue: runValue)
    }

    /// Reconstruct a sample from prediction and error with modular arithmetic.
    ///
    /// Per ITU-T.87 §A.4.4 fix_reconstructed_value:
    /// - Rx = prediction + error × (2·NEAR + 1)
    /// - If Rx < −NEAR:       Rx += RANGE × (2·NEAR + 1)
    /// - If Rx > MAXVAL+NEAR: Rx -= RANGE × (2·NEAR + 1)
    /// - Clamp Rx to [0, MAXVAL]
    ///
    /// For lossless (NEAR=0), the quantisation step is 1 and thresholds collapse
    /// to 0 and MAXVAL, matching the original formulation.
    ///
    /// - Parameters:
    ///   - prediction: The prediction value (Ra or Rb depending on RItype)
    ///   - error: Signed error value (possibly sign-corrected)
    /// - Returns: Reconstructed sample value
    func reconstructSample(prediction: Int, error: Int) -> Int {
        let qbpp = near == 0 ? 1 : (2 * near + 1)
        let dequantized = error * qbpp
        var sample = prediction + dequantized

        // Per ITU-T.87 §A.4.4 fix_reconstructed_value
        let range: Int
        if near == 0 {
            range = parameters.maxValue + 1
        } else {
            range = (parameters.maxValue + 2 * near) / qbpp + 1
        }
        let wrapRange = range * qbpp
        if sample < -near {
            sample += wrapRange
        } else if sample > parameters.maxValue + near {
            sample -= wrapRange
        }
        return max(0, min(parameters.maxValue, sample))
    }

    // MARK: - Context Adaptation

    /// Update run index based on completed run length.
    ///
    /// Per ITU-T.87 Section 4.5.3, the run index adapts based on:
    /// - Longer runs → increase RUNindex (up to maximum of 31)
    /// - Shorter runs → decrease RUNindex (down to minimum of 0)
    ///
    /// This is identical to the encoder adaptation to maintain sync.
    ///
    /// - Parameters:
    ///   - currentRunIndex: Current run index before adaptation
    ///   - completedRunLength: Length of the just-decoded run
    /// - Returns: Updated run index
    func adaptRunIndex(
        currentRunIndex: Int,
        completedRunLength: Int
    ) -> Int {
        // Already at maximum, can't increase
        if currentRunIndex >= 31 {
            return 31
        }

        // Already at minimum, can't decrease
        if currentRunIndex <= 0 {
            return 0
        }

        let j = computeJ(runIndex: currentRunIndex)
        let blockSize = 1 << j  // 2^J

        var newRunIndex = currentRunIndex

        // Increase index if run was long
        if completedRunLength > blockSize {
            newRunIndex = min(currentRunIndex + 1, 31)
        }
        // Decrease index if run was short
        else if j > 0 && completedRunLength < (1 << (j - 1)) {
            newRunIndex = max(currentRunIndex - 1, 0)
        }

        return newRunIndex
    }

    // MARK: - Run Pixel Reconstruction

    /// Reconstruct run pixels from decoded run length.
    ///
    /// Given a run value and length, generates the array of pixels
    /// representing the run.
    ///
    /// - Parameters:
    ///   - runValue: The pixel value for the run
    ///   - runLength: Number of pixels in the run
    /// - Returns: Array of pixel values (all equal to runValue)
    func reconstructRunPixels(runValue: Int, runLength: Int) -> [Int] {
        return Array(repeating: runValue, count: runLength)
    }

    // MARK: - Golomb-Rice Decoding

    /// Decode a Golomb-Rice encoded value.
    ///
    /// Per ITU-T.87 Section 4.4, Golomb-Rice decoding:
    /// - Read unary code (count zeros until a 1)
    /// - Read k bits for the remainder
    /// - Reconstruct value: (quotient << k) | remainder
    ///
    /// - Parameters:
    ///   - unaryCount: Number of zeros in unary prefix (quotient)
    ///   - remainder: Binary remainder (k bits)
    ///   - k: Golomb-Rice parameter
    /// - Returns: Decoded non-negative value (MErrval)
    func golombDecode(unaryCount: Int, remainder: Int, k: Int) -> Int {
        return (unaryCount << k) | remainder
    }

    // MARK: - Complete Run Mode Decoding Pipeline

    /// Decode a complete run from bitstream-style input.
    ///
    /// This method combines all steps of run mode decoding:
    /// 1. Decode run length from continuation and remainder
    /// 2. Optionally decode run interruption sample
    ///
    /// - Parameters:
    ///   - continuationBits: Number of '1' bits representing full blocks
    ///   - remainder: Remainder bits
    ///   - runIndex: Current run index
    ///   - runValue: The pixel value for the run (Ra == Rb)
    ///   - isRunTerminated: Whether the run was interrupted (not at end of line)
    ///   - interruptionMappedError: Mapped error for interruption sample (if terminated)
    /// - Returns: Complete decoded run result
    func decodeCompleteRun(
        continuationBits: Int,
        remainder: Int,
        runIndex: Int,
        runValue: Int,
        isRunTerminated: Bool,
        interruptionMappedError: Int?
    ) -> CompleteDecodedRun {
        // Decode run length
        let decodedRun = decodeRunLength(
            continuationBits: continuationBits,
            remainder: remainder,
            runIndex: runIndex
        )

        // Generate run pixels
        let runPixels = reconstructRunPixels(
            runValue: runValue,
            runLength: decodedRun.totalRunLength
        )

        // Decode interruption sample if present
        var interruptionSample: Int?
        var decodedInterruption: DecodedRunInterruption?

        if isRunTerminated, let mappedError = interruptionMappedError {
            let interruption = decodeRunInterruption(
                mappedError: mappedError,
                runValue: runValue
            )
            interruptionSample = interruption.sample
            decodedInterruption = interruption
        }

        // Compute adapted run index
        let adaptedRunIndex = adaptRunIndex(
            currentRunIndex: runIndex,
            completedRunLength: decodedRun.totalRunLength
        )

        return CompleteDecodedRun(
            runLength: decodedRun.totalRunLength,
            runValue: runValue,
            runPixels: runPixels,
            interruptionSample: interruptionSample,
            decodedInterruption: decodedInterruption,
            adaptedRunIndex: adaptedRunIndex
        )
    }

    // MARK: - Run Limit Checking

    /// Check if run length is within valid bounds.
    ///
    /// - Parameter runLength: Decoded run length
    /// - Returns: True if run length is valid
    func isValidRunLength(_ runLength: Int) -> Bool {
        return runLength >= 0 && runLength <= maxRunLength
    }
}

// MARK: - Decoded Run Result

/// Result of decoding a run of identical pixels.
///
/// Contains the decoded values and metadata from run decoding.
struct DecodedRun: Sendable, Equatable {
    /// Run index used for decoding (determines J value)
    let runIndex: Int

    /// J value (number of bits for remainder)
    let j: Int

    /// Number of continuation bits decoded
    let continuationBits: Int

    /// Remainder value decoded from J bits
    let remainder: Int

    /// Total decoded run length
    let totalRunLength: Int

    /// Initialize a decoded run result.
    ///
    /// - Parameters:
    ///   - runIndex: Run index used for decoding
    ///   - j: J value (bits for remainder)
    ///   - continuationBits: Number of continuation bits
    ///   - remainder: Remainder value
    ///   - totalRunLength: Total decoded run length
    init(
        runIndex: Int,
        j: Int,
        continuationBits: Int,
        remainder: Int,
        totalRunLength: Int
    ) {
        self.runIndex = runIndex
        self.j = j
        self.continuationBits = continuationBits
        self.remainder = remainder
        self.totalRunLength = totalRunLength
    }
}

// MARK: - Decoded Run Interruption Result

/// Result of decoding a run interruption sample.
///
/// When a run is interrupted, the differing pixel is decoded with
/// its prediction error.
struct DecodedRunInterruption: Sendable, Equatable {
    /// Predicted value (the run value)
    let prediction: Int

    /// Mapped non-negative error (MErrval) from bitstream
    let mappedError: Int

    /// Signed prediction error
    let error: Int

    /// Reconstructed sample value
    let sample: Int

    /// Initialize a decoded run interruption result.
    ///
    /// - Parameters:
    ///   - prediction: Predicted value (run value)
    ///   - mappedError: Mapped non-negative error
    ///   - error: Signed prediction error
    ///   - sample: Reconstructed sample value
    init(
        prediction: Int,
        mappedError: Int,
        error: Int,
        sample: Int
    ) {
        self.prediction = prediction
        self.mappedError = mappedError
        self.error = error
        self.sample = sample
    }
}

// MARK: - Complete Decoded Run Result

/// Complete result of decoding a run with optional interruption.
///
/// Contains the run pixels, optional interruption sample, and
/// adapted run index for the next iteration.
struct CompleteDecodedRun: Sendable, Equatable {
    /// Length of the decoded run
    let runLength: Int

    /// Pixel value of the run
    let runValue: Int

    /// Array of run pixel values
    let runPixels: [Int]

    /// Interruption sample value (nil if run ended at line end)
    let interruptionSample: Int?

    /// Full decoded interruption result (nil if no interruption)
    let decodedInterruption: DecodedRunInterruption?

    /// Adapted run index for next iteration
    let adaptedRunIndex: Int

    /// Total number of pixels decoded (run + optional interruption)
    var totalPixels: Int {
        return runLength + (interruptionSample != nil ? 1 : 0)
    }

    /// Initialize a complete decoded run result.
    ///
    /// - Parameters:
    ///   - runLength: Length of the decoded run
    ///   - runValue: Pixel value of the run
    ///   - runPixels: Array of run pixel values
    ///   - interruptionSample: Interruption sample value (optional)
    ///   - decodedInterruption: Full decoded interruption (optional)
    ///   - adaptedRunIndex: Adapted run index
    init(
        runLength: Int,
        runValue: Int,
        runPixels: [Int],
        interruptionSample: Int?,
        decodedInterruption: DecodedRunInterruption?,
        adaptedRunIndex: Int
    ) {
        self.runLength = runLength
        self.runValue = runValue
        self.runPixels = runPixels
        self.interruptionSample = interruptionSample
        self.decodedInterruption = decodedInterruption
        self.adaptedRunIndex = adaptedRunIndex
    }
}
