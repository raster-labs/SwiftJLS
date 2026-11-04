// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "FreshConsumer", platforms: [.macOS(.v26)],
 dependencies: [.package(name: "SwiftJLS", path: "/Users/pushparaj/projects/SwiftJLS-milestone5")],
 targets: [.executableTarget(name: "Consumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])],
 swiftLanguageModes: [.v6])
