// swift-tools-version: 6.2
// SPDX-License-Identifier: Apache-2.0
import PackageDescription

let package = Package(name: "QualifiedAllocationProbe", platforms: [.macOS(.v26)],
    dependencies: [.package(path: "../..")], targets: [
        .target(name: "AllocationInstrumentation", cSettings: [.unsafeFlags(["-fno-builtin"])]),
        .executableTarget(name: "QualifiedAllocationProbe", dependencies: ["AllocationInstrumentation",
            .product(name: "SwiftJLS", package: "SwiftJLS")],
            linkerSettings: [.unsafeFlags(["-Xlinker", "--export-dynamic"], .when(platforms: [.linux]))])
    ], swiftLanguageModes: [.v6])
