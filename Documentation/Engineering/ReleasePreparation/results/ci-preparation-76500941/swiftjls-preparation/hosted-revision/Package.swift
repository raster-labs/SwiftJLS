// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "ReleaseConsumer", platforms: [.macOS(.v26)],
dependencies: [.package(url: "https://github.com/raster-labs/SwiftJLS.git", revision: "765009418bc4a2cdc75c75f676d1834eb88e3de7")],
targets: [.executableTarget(name: "Consumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
.executableTarget(name: "ReadmeExample", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
.executableTarget(name: "MigrationExample", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])], swiftLanguageModes: [.v6])
