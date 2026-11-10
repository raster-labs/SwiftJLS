// swift-tools-version: 6.2
// SPDX-License-Identifier: MIT
import PackageDescription
let package = Package(name: "CopyProbe", platforms: [.macOS(.v26)], dependencies: [.package(name: "SwiftJLS", path: "../..")], targets: [
    .target(name: "CopyInstrumentation", cSettings: [.unsafeFlags(["-fno-builtin-memcpy", "-fno-builtin-memmove"])], linkerSettings: [.linkedLibrary("dl", .when(platforms: [.linux]))]),
    .executableTarget(name: "CopyProbe", dependencies: ["CopyInstrumentation", .product(name: "SwiftJLS", package: "SwiftJLS")])], swiftLanguageModes: [.v6])
