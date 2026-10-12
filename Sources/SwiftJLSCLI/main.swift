// SPDX-License-Identifier: Apache-2.0
import Foundation
import SwiftJLS
#if canImport(Darwin)
import Darwin
#elseif canImport(Glibc)
import Glibc
#endif

private let tool = "swiftjls-cli"
private let version = "1.1.0-dev.2"
private let reserved = ["encode", "decode", "inspect", "validate"]
private let valueOptions: Set<String> = ["--input", "-i", "--output", "-o", "--input-format", "--output-format",
    "--mode", "--max-error", "--backend", "--copy-policy", "--threads", "--max-memory", "--timeout"]

struct UsageError: Error { let message: String }
struct Options {
    var command: String? = nil
    var help = false
    var version = false
    var json = false
    var quiet = false
    var verbosity = 0
    var codecOptions = false
    var values: [String: String] = [:]
    var overwrite = false
}

private func parse(_ args: [String]) throws -> Options {
    var options = Options()
    var index = 0
    var positionalOnly = false
    func level(_ value: String) throws -> Int {
        let number: Int?
        if !value.isEmpty && value.allSatisfy({ $0 == "+" }) { number = value.count }
        else if !value.isEmpty && value.utf8.allSatisfy({ (48...57).contains($0) }) { number = Int(value) }
        else { number = nil }
        guard let number, (1...5).contains(number) else {
            throw UsageError(message: "Verbosity must be 1 through 5, or + through +++++.")
        }
        return number
    }
    func consumeValue() throws -> String {
        guard index + 1 < args.count, args[index + 1] == "-" || !args[index + 1].hasPrefix("-") else {
            throw UsageError(message: "An option is missing its value. Use --help for syntax.")
        }
        index += 1
        return args[index]
    }
    while index < args.count {
        let arg = args[index]
        if !positionalOnly && arg == "--" { positionalOnly = true }
        else if !positionalOnly && ["-h", "--help"].contains(arg) { options.help = true }
        else if !positionalOnly && arg == "--version" { options.version = true }
        else if !positionalOnly && arg == "--json" { options.json = true }
        else if !positionalOnly && ["-q", "--quiet"].contains(arg) { options.quiet = true }
        else if !positionalOnly && ["-v", "--verbose", "-verbose"].contains(arg) {
            // An optional numeric/plus value sets the level. A bare flag increments it.
            if index + 1 < args.count,
               let first = args[index + 1].first, first.isNumber || first == "+" {
                index += 1; options.verbosity = try level(args[index])
            } else { options.verbosity += 1 }
        } else if !positionalOnly,
                  let prefix = ["--verbose=", "--verbose:", "-verbose=", "-verbose:"].first(where: { arg.hasPrefix($0) }) {
            let attached = String(arg.dropFirst(prefix.count))
            options.verbosity = try level(attached.isEmpty ? consumeValue() : attached)
        } else if !positionalOnly && arg.hasPrefix("-v") && arg.count > 2 && arg.dropFirst().allSatisfy({ $0 == "v" }) {
            options.verbosity += arg.count - 1
        } else if !positionalOnly && valueOptions.contains(arg) {
            let key = arg == "-i" ? "--input" : arg == "-o" ? "--output" : arg
            guard options.values[key] == nil else { throw UsageError(message: "Duplicate option.") }
            options.values[key] = try consumeValue()
            options.codecOptions = true
        } else if !positionalOnly && arg == "--overwrite" { options.codecOptions = true; options.overwrite = true }
        else if !positionalOnly && arg.hasPrefix("-") {
            throw UsageError(message: "Unknown option. Use \(tool) --help.")
        } else if options.command == nil { options.command = arg }
        else if options.command == "help" && !options.help { options.command = arg; options.help = true }
        else { throw UsageError(message: "Unexpected positional argument. Use --input or --output for future codec commands.") }
        guard options.verbosity <= 5 else { throw UsageError(message: "Verbosity exceeds the maximum level 5.") }
        index += 1
    }
    if options.command == "help" { options.command = nil; options.help = true }
    if options.command == "version" { options.command = nil; options.version = true }
    if let command = options.command, command != "capabilities" && !reserved.contains(command) {
        throw UsageError(message: "Unknown command. Use \(tool) --help.")
    }
    if options.quiet && options.verbosity > 0 { throw UsageError(message: "--quiet and verbosity cannot be combined.") }
    if options.version && (options.command != nil || options.codecOptions || options.json) {
        throw UsageError(message: "--version cannot be combined with a command or command options.")
    }
    if options.codecOptions && (options.command == nil || options.command == "capabilities") {
        throw UsageError(message: "Input/output and codec options require a codec command.")
    }
    if options.json && options.command == nil { throw UsageError(message: "--json requires capabilities or a codec command.") }
    return options
}

private func help(_ command: String?) -> String {
    let common = """
    OPTIONS
      -h, --help                 Show this help; also: help [command].
      --version                  Show the development version.
      -v, -vv ... -vvvvv         Increase verbosity (maximum 5).
      --verbose LEVEL           Set verbosity to 1..5 or + through +++++.
      --verbose=LEVEL            Equivalent explicit form; -verbose: LEVEL is accepted.
      -q, --quiet                Suppress optional diagnostics; errors remain visible.

    VERBOSITY (stderr only; default 0)
      1 summary; 2 command stages; 3 capability details; 4 elapsed timing;
      5 bounded diagnostic trace. Levels are cumulative. Quiet conflicts with verbosity.
      Payload bytes, metadata, raw addresses and input/output paths are never logged.

    EXIT STATUS
      0 success/help/version; 2 invalid usage; 4 unsupported codec operation;
      6 I/O failure (including a closed pipe); 3 malformed input;
      5 resource/deadline; 7 internal failure; 130 cancellation.

    MANUAL
      man \(tool) (installed with the executable by Scripts/install-cli.sh).
    """
    if let command {
        if command == "capabilities" {
            return """
            USAGE: \(tool) capabilities [--json] [OPTIONS]

            Report this library's current encode/decode/inspect support without reading files.
            --json writes one JSON document to stdout; diagnostics stay on stderr.
            Empty formats and false support values mean codec algorithms are unavailable.

            \(common)

            EXAMPLES
              \(tool) capabilities --json
              \(tool) capabilities --verbose=+++
            """ + "\n"
        }
        let output = command == "encode" || command == "decode" ? "\n  -o, --output PATH           Final output or '-'; --overwrite permits replacement.\n  --output-format FORMAT      jls for encode; nrrd for decode." : ""
        let mode = command == "encode" ? "\n  --mode lossless|near-lossless  Default lossless.\n  --max-error N               Required for near-lossless; 1...255." : ""
        return """
        USAGE: \(tool) \(command) --input PATH [OPTIONS]

        Native scalar JPEG-LS. Encode reads attached 2D raw uint16 NRRD.
        Decode writes that NRRD profile and requires 16 meaningful source bits.
        Inspect validates headers; validate decodes the complete sample payload.
        Unsupported layouts and metadata fail explicitly.

          -i, --input PATH           Input or '-' for standard input.
          --input-format FORMAT     nrrd for encode; jls otherwise.\(output)\(mode)
          --backend NAME            automatic (default) or scalar-cpu.
          --copy-policy POLICY      require-sharing (default) or allow-copy.
          --threads N               Worker ceiling; scalar codec uses one worker.
          --max-memory BYTES        Operation memory ceiling (default 1 GiB).
          --timeout SECONDS         Positive deadline (default 120).
          --json                    JSON on stdout for inspect/validate;
                                    encode/decode reports on stderr.
        Pipe serialisation involves copies. Binary stdout may contain partial
        output after failure; file transactions are removed on failure.

        \(common)
        """ + "\n"
    }
    return """
    \(tool) \(version) — JPEG-LS
    USAGE: \(tool) [OPTIONS] <command> [OPTIONS]

    COMMANDS
      capabilities [--json]      Report actual library support (currently empty).
      help [command]             Show global or command-specific help.
      version                    Show the development version.
      \(reserved.joined(separator: ", "))
                                Native scalar JPEG-LS and bounded NRRD stream operations.

    Requires Swift 6.2 or newer; Apple OS baseline 26.0. CLI hosts: macOS/Linux.
    Lossless and near-lossless greyscale; advanced extensions remain unsupported.

    \(common)

    EXAMPLES
      \(tool) -h
      \(tool) help capabilities
      \(tool) capabilities --json -vv
      \(tool) capabilities -verbose: 3
    """ + "\n"
}

private func write(_ text: String, to handle: FileHandle) throws {
    try handle.write(contentsOf: Data(text.utf8))
}

private func run() async throws -> Int32 {
    let start = ProcessInfo.processInfo.systemUptime
    let options: Options
    do { options = try parse(Array(CommandLine.arguments.dropFirst())) }
    catch let error as UsageError {
        try write("\(tool): \(error.message)\n", to: .standardError)
        return 2
    }
    if options.help || (options.command == nil && !options.version) {
        try write(help(options.command), to: .standardOutput); return 0
    }
    if options.version { try write("\(tool) \(version)\n", to: .standardOutput); return 0 }
    func diagnostic(_ level: Int, _ message: String) throws {
        if !options.quiet && options.verbosity >= level {
            try write("[\(level)] \(tool): \(message)\n", to: .standardError)
        }
    }
    try diagnostic(1, "development version \(version)")
    try diagnostic(2, "reporting \(options.command ?? "help")")
    guard options.command == "capabilities" else {
        try await runPayload(options)
        try diagnostic(1, "operation completed")
        return 0
    }
    let encoder = Encoder.capabilities
    let decoder = Decoder.capabilities
    let formats = Array(Set(encoder.formats + decoder.formats)).sorted()
    if options.json {
        let payload: [String: Any] = ["tool": tool, "version": version, "minimumAppleOS": "26.0",
            "canEncode": encoder.canEncode, "canDecode": decoder.canDecode,
            "canInspect": decoder.canInspect, "formats": formats]
        let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
        try FileHandle.standardOutput.write(contentsOf: data + Data([10]))
    } else {
        try write("\(tool) \(version)\nencode: \(encoder.canEncode)\ndecode: \(decoder.canDecode)\ninspect: \(decoder.canInspect)\nformats: \(formats.isEmpty ? "none" : formats.joined(separator: ", "))\n", to: .standardOutput)
    }
    try diagnostic(3, "advertised formats: \(formats.count); capability values read from the library")
    try diagnostic(4, "elapsed seconds: \(ProcessInfo.processInfo.systemUptime - start)")
    try diagnostic(5, "arguments validated; capability report emitted; no codec payload opened")
    return 0
}

// CLI process boundary only: a closed pipe is reported as exit 6, never SIGPIPE success.
_ = signal(SIGPIPE, SIG_IGN)
let operation = Task { try await run() }
_ = signal(SIGINT, SIG_IGN)
let interrupt = DispatchSource.makeSignalSource(signal: SIGINT, queue: .global())
interrupt.setEventHandler { @Sendable [operation] in operation.cancel() }
interrupt.resume()
var status: Int32 = 0
do { status = try await operation.value }
catch is CancellationError { status = 130 }
catch let error as UsageError {
    try? write("\(tool): \(error.message)\n", to: .standardError); status = 2
}
catch let error as CodecError {
    switch error.category {
    case .invalidArgument: status = 2
    case .malformedInput: status = 3
    case .unsupportedFormat, .unsupportedFeature, .incompatibleImageLayout, .backendUnavailable: status = 4
    case .resourceLimitExceeded: status = 5
    case .storageUnavailable, .ioFailure: status = 6
    case .internalFailure: status = 7
    }
    try? write("\(tool): \(error.message)\n", to: .standardError)
}
catch {
    try? write("\(tool): input/output failure.\n", to: .standardError); status = 6
}
interrupt.cancel()
exit(status)
