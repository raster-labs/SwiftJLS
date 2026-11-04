// swift-tools-version: 6.2
import PackageDescription
let package = Package(name: "ReleaseConsumer", platforms: [.macOS(.v26)],
dependencies: [.package(url: "https://github.com/raster-labs/SwiftJLS.git", revision: "68b0b6385bca135e1532a7e22ceb00992af549b9")],
targets: [.executableTarget(name: "Consumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
.executableTarget(name: "ReadmeExample", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")]),
.executableTarget(name: "MigrationExample", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])], swiftLanguageModes: [.v6])
