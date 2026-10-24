// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "SameProcessDiagnostic", platforms: [.macOS(.v26)], dependencies: [
    .package(path: "/Users/pushparaj/Documents/Codex/2026-10-13/che/work/JLSwift"),
    .package(path: "/Users/pushparaj/Documents/Codex/2026-10-13/che/work/SwiftJLS")
], targets: [.executableTarget(name: "Benchmark", dependencies: [
    .product(name: "JPEGLS", package: "JLSwift"),
    .product(name: "SwiftJLS", package: "SwiftJLS")
])], swiftLanguageModes: [.v6])
