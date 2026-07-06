// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "XPSceneryDoctor",
    platforms: [.macOS(.v14)],
    targets: [
        .target(name: "SceneryKit"),
        .executableTarget(
            name: "XPSceneryDoctor",
            dependencies: ["SceneryKit"],
            resources: [.copy("Resources/land.json"), .copy("Resources/land50.json")]
        ),
        .executableTarget(
            name: "xpdoctor-cli",
            dependencies: ["SceneryKit"]
        ),
        .testTarget(
            name: "SceneryKitTests",
            dependencies: ["SceneryKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
