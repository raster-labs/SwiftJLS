from pathlib import Path
import hashlib,json,difflib,datetime
here=Path(__file__).resolve().parent;root=here.parents[3]
original=(root/'Scripts/Benchmark/Consumer.swift').read_text()
assert hashlib.sha256(original.encode()).hexdigest()=='27e4ca75529bf1a0e27ae4be14ec6c906945cc2ee6f0fa22170594144fe00c34'
s=original.replace('func decode(_ data: Data, verify: Bool) async throws {\n    let image = try await Decoder().decode(data, options: .init(resourceLimits: benchmarkLimits, executionPolicy: .scalarCPU)).image', 'func decode(_ data: Data, verify: Bool) async throws -> Double {\n    let decoded = try await Decoder().decode(data, options: .init(resourceLimits: benchmarkLimits, executionPolicy: .scalarCPU))\n    guard let reportedElapsed = decoded.report.elapsedSeconds else { throw Failure() }\n    let image = decoded.image')
old='    }\n}\n#endif\nlet image = try makeImage()'
new='''    }
    #if REPORT_ELAPSED
    return reportedElapsed
    #else
    _ = reportedElapsed
    return 0
    #endif
}
#endif
let image = try makeImage()'''
assert old in s;s=s.replace(old,new)
s=s.replace('var preparation: [Double] = [], preparedEncoding: [Double] = []','var preparation: [Double] = [], preparedEncoding: [Double] = []\nvar reportedDecoding: [Double] = []')
s=s.replace('    try await decode(reference, verify: false)\n    decoding.append(ProcessInfo.processInfo.systemUptime - start)', '    let reported = try await decode(reference, verify: false)\n    decoding.append(ProcessInfo.processInfo.systemUptime - start)\n    reportedDecoding.append(reported)')
s=s.replace('    "encode_seconds": encoding, "decode_seconds": decoding,','    "encode_seconds": encoding, "decode_seconds": decoding,\n    "reported_decode_seconds": reportedDecoding,')
assert s!=original and 'reportedDecoding.append(reported)' in s
(here/'original-Consumer.swift').write_text(original)
zero_source = s
s=s.replace('let endToEnd = ProcessInfo.processInfo.environment["SWIFTJLS_BENCHMARK_END_TO_END"] == "1"', 'let endToEnd = ProcessInfo.processInfo.environment["SWIFTJLS_BENCHMARK_END_TO_END"] == "1"\nlet retainReport = ProcessInfo.processInfo.environment["SWIFTJLS_DIAGNOSTIC_REPORT"] == "1"')
s=s.replace('    #if REPORT_ELAPSED\n    return reportedElapsed\n    #else\n    _ = reportedElapsed\n    return 0\n    #endif', '    return reportedElapsed')
s=s.replace('reportedDecoding.append(reported)', 'reportedDecoding.append(retainReport ? reported : 0)')
s=s.replace('    "reported_decode_seconds": reportedDecoding,', '    "reported_decode_seconds": reportedDecoding,\n    "retain_report": retainReport,')
for target in ['ReportBenchmark','ZeroBenchmark']:(here/'Sources'/target/'main.swift').write_text(zero_source if target == 'ZeroBenchmark' else s)
(here/'consumer.patch').write_text(''.join(difflib.unified_diff(original.splitlines(True),s.splitlines(True),fromfile='original-Consumer.swift',tofile='diagnostic-Consumer.swift')))
(here/'Package.swift').write_text('''// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "DecodeReportDiagnostic", platforms: [.macOS(.v26)],
 dependencies: [.package(path: "'''+str(root)+'''")],
 targets: [
  .executableTarget(name: "ReportBenchmark", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")], swiftSettings: [.define("REPORT_ELAPSED")]),
  .executableTarget(name: "ZeroBenchmark", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
  .target(name: "UUIDMicroCore"),
  .executableTarget(name: "UUIDBenchmark", dependencies: ["UUIDMicroCore"])
 ], swiftLanguageModes: [.v6])
''')
(here/'preparation.json').write_text(json.dumps(dict(utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),source='bee49a2ad47eae4ea149bdced2043b7a45df3dae',original_consumer_sha256=hashlib.sha256(original.encode()).hexdigest(),diagnostic_consumer_sha256=hashlib.sha256(s.encode()).hexdigest(),scope='Public production unchanged. Matched report/zero Double-return ABI. Result/image destruction remains inside helper and outer timer. Report covers CodecBudget start through report construction; outer-minus-report also contains final progress/checks/destruction, not only executor overhead.'),indent=2)+'\n')
