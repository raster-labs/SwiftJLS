// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "Benchmark", platforms: [.macOS(.v26)], dependencies: [.package(path: "/Users/pushparaj/Documents/Codex/2026-10-13/che/work/JLSwift")], targets: [.executableTarget(name: "Benchmark", dependencies: [.product(name: "JPEGLS", package: "JLSwift")], swiftSettings: [.define("PREDECESSOR")])], swiftLanguageModes: [.v6])
