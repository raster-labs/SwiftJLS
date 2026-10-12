// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription
let package = Package(name: "FuzzConsumer", platforms: [.macOS(.v26)],
    dependencies: [.package(path: "../..")],
    targets: [.executableTarget(name: "FuzzConsumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])],
    swiftLanguageModes: [.v6])
