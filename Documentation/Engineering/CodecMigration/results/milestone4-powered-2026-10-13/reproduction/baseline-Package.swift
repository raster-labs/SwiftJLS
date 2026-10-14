// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "Benchmark", platforms: [.macOS(.v26)], dependencies: [.package(path: "<repo>/work/m4-baseline-source")], targets: [.executableTarget(name: "Benchmark", dependencies: [.product(name: "SwiftJLS", package: "m4-baseline-source")])], swiftLanguageModes: [.v6])
