// swift-tools-version: 6.2
// SPDX-License-Identifier: MIT
import PackageDescription
let package = Package(name: "ResourceStress", platforms: [.macOS(.v26)],
    dependencies: [.package(name: "SwiftJLS", path: "../..")],
    targets: [.executableTarget(name: "ResourceStress", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])],
    swiftLanguageModes: [.v6])
