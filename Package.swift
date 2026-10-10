// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription

let package = Package(
    name: "SwiftJLS",
    platforms: [.macOS(.v26), .iOS(.v26), .tvOS(.v26), .visionOS(.v26), .watchOS(.v26)],
    products: [.library(name: "SwiftJLS", targets: ["SwiftJLS"]),
               .executable(name: "swiftjls-cli", targets: ["SwiftJLSCLI"])],
    targets: [
        .target(name: "SwiftJLS"),
        .executableTarget(name: "SwiftJLSCLI", dependencies: ["SwiftJLS"]),
        .testTarget(name: "SwiftJLSTests", dependencies: ["SwiftJLS"], resources: [.copy("Fixtures")])
    ],
    swiftLanguageModes: [.v6]
)
