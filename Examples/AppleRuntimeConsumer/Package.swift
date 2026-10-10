// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription
let package = Package(name: "AppleRuntimeConsumer", platforms: [.macOS(.v26), .iOS(.v26), .tvOS(.v26), .visionOS(.v26), .watchOS(.v26)],
    dependencies: [.package(path: "../..")],
    targets: [.executableTarget(name: "AppleRuntimeConsumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])],
    swiftLanguageModes: [.v6])
