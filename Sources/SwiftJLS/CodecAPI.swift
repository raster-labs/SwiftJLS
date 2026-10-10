// SPDX-License-Identifier: Apache-2.0
import Foundation

/// Codec-specific controls are added only with independently tested behaviour.
public struct CodecOptions: Sendable, Equatable {
    /// HP reversible RGB transforms signalled by the private APP8 `mrfx` convention.
    /// Supported only for lossless, interleaved RGB with 8 or 16 meaningful bits.
    public enum ColourTransform: UInt8, Sendable { case none = 0, hp1 = 1, hp2 = 2, hp3 = 3 }
    public enum InterleaveMode: UInt8, Sendable { case none = 0, line = 1, sample = 2 }
    /// Explicit JPEG-LS coding parameters. These do not change sample signedness
    /// or the declared precision of the image container.
    public struct Preset: Sendable, Equatable {
        public let maximumSampleValue: Int
        public let threshold1: Int, threshold2: Int, threshold3: Int, reset: Int
        public init(maximumSampleValue: Int, threshold1: Int, threshold2: Int, threshold3: Int,
                    reset: Int = 64) throws {
            guard (1...65535).contains(maximumSampleValue),
                  (1...maximumSampleValue).contains(threshold1),
                  (threshold1...maximumSampleValue).contains(threshold2),
                  (threshold2...maximumSampleValue).contains(threshold3),
                  (3...max(255, maximumSampleValue)).contains(reset) else {
                throw CodecError(.invalidArgument, "Invalid JPEG-LS preset parameters.")
            }
            self.maximumSampleValue = maximumSampleValue
            self.threshold1 = threshold1; self.threshold2 = threshold2
            self.threshold3 = threshold3; self.reset = reset
        }
    }
    /// JPEG-LS restart interval in sample rows. Zero disables restart markers.
    public let restartIntervalLines: Int
    public let preset: Preset?
    public let interleaveMode: InterleaveMode
    public let colourTransform: ColourTransform
    public init() { restartIntervalLines = 0; preset = nil; interleaveMode = .none; colourTransform = .none }
    public init(restartIntervalLines: Int, preset: Preset? = nil, interleaveMode: InterleaveMode = .none, colourTransform: ColourTransform = .none) throws {
        guard (0...65535).contains(restartIntervalLines) else {
            throw CodecError(.invalidArgument, "Restart interval must be 0...65535 sample rows.")
        }
        self.restartIntervalLines = restartIntervalLines; self.preset = preset; self.interleaveMode = interleaveMode
        self.colourTransform = colourTransform
    }
}

public struct EncoderConfiguration: Sendable, Equatable {
    public let mode: CompressionMode
    public let codecOptions: CodecOptions
    public init(mode: CompressionMode = .lossless, codecOptions: CodecOptions = .init()) throws {
        if case .nearLossless(let bound) = mode, bound <= 0 {
            throw CodecError(.invalidArgument, "Near-lossless error must be positive.")
        }
        if case .nearLossless(let bound) = mode, bound > 255 {
            throw CodecError(.invalidArgument, "JPEG-LS NEAR must not exceed 255.")
        }
        guard mode != .lossy else {
            throw CodecError(.unsupportedFeature, "JPEG-LS supports lossless and bounded near-lossless coding.")
        }
        guard codecOptions.restartIntervalLines == 0 || codecOptions.interleaveMode == .none else {
            throw CodecError(.unsupportedFeature, "Restart intervals require non-interleaved scans.")
        }
        guard codecOptions.colourTransform == .none ||
              (mode == .lossless && codecOptions.interleaveMode != .none && codecOptions.preset == nil) else {
            throw CodecError(.unsupportedFeature, "HP transforms require lossless interleaved coding without explicit presets.")
        }
        self.mode = mode; self.codecOptions = codecOptions
    }
    private init() { mode = .lossless; codecOptions = .init() }
    public static let `default` = Self()
}
public struct DecoderConfiguration: Sendable, Equatable {
    public let codecOptions: CodecOptions
    public init(codecOptions: CodecOptions = .init()) { self.codecOptions = codecOptions }
}

public struct CodecCapabilities: Sendable, Equatable {
    public let formats: [String]
    public let compressionModes: [CompressionMode]
    public let sampleTypes: [SampleType]
    public let meaningfulPrecision: ClosedRange<Int>?
    public let layouts: [String]
    public let availableBackends: [Backend]
    public let canInspect: Bool
    public let canEncode: Bool
    public let canDecode: Bool
    public static let contractOnly = Self(formats: [], compressionModes: [], sampleTypes: [],
        meaningfulPrecision: nil, layouts: [], availableBackends: [],
        canInspect: false, canEncode: false, canDecode: false)
}

public struct CopyEvent: Sendable, Equatable {
    public let reason: String
    public let bytesMoved: Int
    public let sourceLayout: String
    public let destinationLayout: String
    public init(reason: String, bytesMoved: Int, sourceLayout: String, destinationLayout: String) throws {
        guard bytesMoved >= 0 else { throw CodecError(.invalidArgument, "Copy byte count must not be negative.") }
        self.reason = reason; self.bytesMoved = bytesMoved
        self.sourceLayout = sourceLayout; self.destinationLayout = destinationLayout
    }
}
public enum Fidelity: Sendable, Equatable { case exactSamples, boundedError(Int), lossy, originalBitstream }
public struct OperationReport: Sendable, Equatable {
    public let backend: Backend
    public let fallbackReason: String?
    public let fidelity: Fidelity
    public let copyEvents: [CopyEvent]
    public let pixelAllocationCount: Int?
    public let peakPixelBytes: Int?
    public let peakWorkspaceBytes: Int?
    public let elapsedSeconds: Double?
    public init(backend: Backend, fallbackReason: String? = nil, fidelity: Fidelity,
                copyEvents: [CopyEvent] = [], pixelAllocationCount: Int? = nil,
                peakPixelBytes: Int? = nil, peakWorkspaceBytes: Int? = nil, elapsedSeconds: Double? = nil) {
        self.backend = backend; self.fallbackReason = fallbackReason; self.fidelity = fidelity
        self.copyEvents = copyEvents; self.pixelAllocationCount = pixelAllocationCount
        self.peakPixelBytes = peakPixelBytes; self.peakWorkspaceBytes = peakWorkspaceBytes
        self.elapsedSeconds = elapsedSeconds
    }
}
public struct ImageInfo: Sendable {
    public let format: String
    public let descriptor: ImageDescriptor
    public let frameCount: Int
    public let metadata: ImageMetadata
}
public struct EncodingDescription: Sendable, Equatable {
    public let format: String
    public let mode: CompressionMode
}
public struct EncodedImage: Sendable {
    public let data: Data
    public let encoding: EncodingDescription
    public let report: OperationReport
}
public struct DecodedImage: Sendable {
    public let image: Image
    public let report: OperationReport
}

/// Native JPEG-LS encoder. Capabilities describe the currently migrated profile.
public struct Encoder: Sendable {
    public let configuration: EncoderConfiguration
    public static let capabilities = ScalarCodec.capabilities
    public var capabilities: CodecCapabilities { Self.capabilities }
    public init(configuration: EncoderConfiguration = .default) throws { self.configuration = configuration }

    /// `@concurrent` explicitly selects the generic executor (available since Swift 6.2).
    @concurrent public func encode(_ image: Image, options: EncodeOptions = .init()) async throws -> EncodedImage {
        try Task.checkCancellation()
        try validateOperation(options.resourceLimits, options.executionPolicy)
        guard image.storage.byteCount <= options.resourceLimits.maximumDecodedBytes,
              image.storage.byteCount <= options.resourceLimits.maximumMemoryBytes else {
            throw CodecError(.resourceLimitExceeded, "Image exceeds operation limits.")
        }
        if image.descriptor.components.count > 1 {
            return try ComponentCodec.encode(image, configuration: configuration, options: options)
        }
        return try ScalarCodec.encode(image, configuration: configuration, options: options)
    }
}

/// Bounded inspection and native decoding into owned sample storage.
public struct Decoder: Sendable {
    public let configuration: DecoderConfiguration
    public static let capabilities = ScalarCodec.capabilities
    public var capabilities: CodecCapabilities { Self.capabilities }
    public init(configuration: DecoderConfiguration = .init()) throws {
        guard configuration.codecOptions == CodecOptions() else {
            throw CodecError(.invalidArgument, "Decode parameters come from the codestream; preset and restart overrides are encoder-only.")
        }
        self.configuration = configuration
    }

    public func inspect(_ data: Data, options: DecodeOptions = .init()) throws -> ImageInfo {
        try validateInput(data, options)
        return try ScalarCodec.inspect(data, options: options)
    }
    @concurrent public func decode(_ data: Data, options: DecodeOptions = .init()) async throws -> DecodedImage {
        try Task.checkCancellation()
        try validateInput(data, options)
        return try ScalarCodec.decode(data, into: nil, options: options)
    }
    @concurrent public func decode(_ data: Data, into destination: ImageDestination,
                                  options: DecodeOptions = .init()) async throws -> DecodedImage {
        try Task.checkCancellation()
        try validateInput(data, options)
        // Preflight rejection performs no write; the caller may still initialise it.
        return try ScalarCodec.decode(data, into: destination, options: options)
    }
}

private func validateOperation(_ limits: ResourceLimits, _ policy: ExecutionPolicy) throws {
    if case .required(.accelerated) = policy {
        throw CodecError(.backendUnavailable, "No accelerated backend is implemented.")
    }
}
private func validateInput(_ data: Data, _ options: DecodeOptions) throws {
    try validateOperation(options.resourceLimits, options.executionPolicy)
    guard data.count <= options.resourceLimits.maximumCompressedBytes,
          data.count <= options.resourceLimits.maximumMemoryBytes else {
        throw CodecError(.resourceLimitExceeded, "Compressed input exceeds operation limits.")
    }
}
