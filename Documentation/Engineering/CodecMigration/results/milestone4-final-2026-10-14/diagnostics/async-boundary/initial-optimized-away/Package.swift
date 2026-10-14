// swift-tools-version: 6.2
import PackageDescription
let package = Package(
    name: "AsyncBoundaryDiagnostic", platforms: [.macOS(.v26)],
    dependencies: [.package(path: "/Users/pushparaj/Documents/Codex/2026-10-13/che/work/JLSwift")],
    targets: [
        .target(name: "AsyncBaselineCore", dependencies: [.product(name: "JPEGLS", package: "JLSwift")]),
        .executableTarget(name: "Benchmark", dependencies: ["AsyncBaselineCore",
            .product(name: "JPEGLS", package: "JLSwift")], swiftSettings: [.define("PREDECESSOR")])
    ], swiftLanguageModes: [.v6])
