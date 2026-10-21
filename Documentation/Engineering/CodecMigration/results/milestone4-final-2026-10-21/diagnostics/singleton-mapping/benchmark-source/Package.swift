// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "Benchmark", platforms: [.macOS(.v26)], dependencies: [.package(path: "../source")], targets: [.executableTarget(name: "Benchmark", dependencies: [.product(name: "SwiftJLS", package: "source")])], swiftLanguageModes: [.v6])
