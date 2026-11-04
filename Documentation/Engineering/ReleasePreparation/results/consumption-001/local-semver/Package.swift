// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "ReleaseConsumer", platforms: [.macOS(.v26)],
dependencies: [.package(url: "file:///private/tmp/SwiftJLS-m5-preparation-001/SwiftJLS.git", exact: "1.1.0-dev.2")],
targets: [.executableTarget(name: "Consumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
.executableTarget(name: "ReadmeExample", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
.executableTarget(name: "MigrationExample", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])], swiftLanguageModes: [.v6])
