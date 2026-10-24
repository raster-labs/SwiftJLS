// swift-tools-version: 6.2
import PackageDescription
let package = Package(
    name: "Interop",
    platforms: [.macOS(.v26)],
    dependencies: [.package(name: "SwiftJLS", path: "/Users/pushparaj/.gemini/antigravity/brain/fe0e1849-2821-43e4-93ba-6e59adfa578b/scratch/m4_20261023/snapshots/candidate_004/SwiftJLS")],
    targets: [.executableTarget(name: "Consumer", dependencies: [.product(name: "SwiftJLS", package: "SwiftJLS")])],
    swiftLanguageModes: [.v6]
)
