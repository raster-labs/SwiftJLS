// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "DecodeReportDiagnostic", platforms: [.macOS(.v26)],
 dependencies: [.package(path: "/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS")],
 targets: [
  .executableTarget(name: "ReportBenchmark", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")], swiftSettings: [.define("REPORT_ELAPSED")]),
  .executableTarget(name: "ZeroBenchmark", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
  .target(name: "UUIDMicroCore"),
  .executableTarget(name: "UUIDBenchmark", dependencies: ["UUIDMicroCore"])
 ], swiftLanguageModes: [.v6])
