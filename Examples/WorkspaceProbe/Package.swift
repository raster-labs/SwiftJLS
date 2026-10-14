// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription
let package = Package(name: "WorkspaceProbe", platforms: [.macOS(.v26)],
    dependencies: [.package(path: "../..")],
    targets: [
        .target(name: "PhaseMarkers"),
        .executableTarget(name: "WorkspaceProbe", dependencies: ["PhaseMarkers", .product(name: "SwiftJLS", package: "SwiftJLS")])
    ], swiftLanguageModes: [.v6])
