# swiftjls-cli

Version 1.1.0-dev.2. Swift tools 6.2 minimum, Swift 6 mode, Apple OS 26. Hosts: macOS and Linux. The CLI has no external parser or codec dependencies.

`encode` reads an attached raw 2D unsigned 16-bit NRRD and writes JPEG-LS. `decode` writes that NRRD profile from a 16-bit JPEG-LS source. `inspect` validates the header and reports dimensions/precision; `validate` additionally decodes all samples. The library also supports 2–15 meaningful bits, but CLI NRRD output rejects these because a plain uint16 NRRD cannot preserve the narrower declared precision. Mapping tables and APP/COM/SPIFF metadata can be inspected and validated through the library-supported profiles. NRRD export rejects retained metadata with status 4 before writing payload bytes or replacing an existing file; this interchange profile cannot preserve that interpretation. Explicit predecessor compatibility and mapped-output options are library APIs, not CLI flags.

```sh
swift run swiftjls-cli encode -i input.nrrd -o output.jls
swift run swiftjls-cli inspect -i output.jls --json
swift run swiftjls-cli validate -i output.jls
swift run swiftjls-cli decode -i output.jls -o restored.nrrd
swift run swiftjls-cli encode -i input.nrrd -o near.jls --mode near-lossless --max-error 3
swift run swiftjls-cli capabilities --json
```

`-` means stdin/stdout. Binary payloads use stdout exclusively; encode/decode `--json` reports use stderr. Pipe serialisation involves copies. Slow pipes obey the deadline and cancellation; a failed binary stdout operation may leave partial bytes. Files use a sibling final-output transaction, atomic no-replace publication by default and atomic replacement with `--overwrite`; failure removes the incomplete transaction.

The bounded NRRD profile follows the [official specification](https://teem.sourceforge.net/nrrd/format.html), reviewed 10 October 2026 (format versions 1–5, attached header, type, dimensions, sizes, raw encoding and explicit endian). Headers are limited to 16 KiB, 32 lines and 1024 bytes per line. Duplicate/unknown fields, detached files/URLs, key-value extensions, compression, signed/colour types and ancillary interpretation fields are rejected. LF and CRLF and both endians are accepted. Comments are ignored. This is a deliberately restricted interchange profile, not a general NRRD implementation.

Use `help [command]` or `--help` for command-local options. `--threads` is a ceiling; this scalar implementation uses one worker. `--max-memory` defaults to 1 GiB and `--timeout` to 120 seconds. Unsupported acceleration fails before input opens. Lossless is the default; near-lossless requires `--max-error 1...255`.

Diagnostics are on stderr: `-v` through `-vvvvv`, repeated `-v`, `--verbose LEVEL`, `--verbose=LEVEL`, `-verbose: LEVEL` and plus strings select levels 1–5. Explicit values set; repeated flags increment. Quiet conflicts with verbosity. No payload bytes, metadata, addresses or filenames are logged.

Exit statuses: 0 success, 2 usage, 3 malformed input, 4 unsupported format/feature/layout/backend, 5 resource/deadline, 6 I/O, 7 internal failure, 130 cancellation.

`Scripts/install-cli.sh --prefix /absolute/prefix` installs the executable and [manual](ManPages/swiftjls-cli.1) together. `--destdir /absolute/staging` stages packaging. `--binary /absolute/swiftjls-cli` uses a prebuilt matching version. No system installation is performed by tests. `man -M PREFIX/share/man swiftjls-cli` finds a custom-prefix manual.

`Scripts/test-cli.py` checks help, diagnostics and staged installation. `Scripts/test-payload-cli.py` checks real round trips, streams, malformed headers, overwrite refusal, cleanup and cancellation. Both accept `--binary` and `--output`; see [migration evidence](Documentation/Engineering/CodecMigration/README.md) for executed results and open gates.
