// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription
let package = Package(
    name: "CrossCodecConsumer",
    platforms: [.macOS(.v26)],
    dependencies: [
        .package(path: "../.."),
        .package(url: "https://github.com/raster-labs/SwiftJ2K.git",
                 revision: "be4e7a3ad352759e7a78a90f6a2e2c3b7aa0f748")
    ],
    targets: [.executableTarget(name: "CrossCodecConsumer", dependencies: [
        .product(name: "SwiftJLS", package: "SwiftJLS"),
        .product(name: "SwiftJ2K", package: "SwiftJ2K")
    ])],
    swiftLanguageModes: [.v6]
)
