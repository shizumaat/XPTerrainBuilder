// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "XPTerrainBuilder",
    platforms: [.macOS(.v14)],
    targets: [
        .target(
            name: "SceneryKit",
            resources: [
                .copy("Resources/o4_driver.py"),
                .copy("Resources/o4_schema_dump.py"),
                .copy("Resources/o4_schema_snapshot.json"),
            ]
        ),
        .executableTarget(
            name: "XPTerrainBuilder",
            dependencies: ["SceneryKit"],
            resources: [.copy("Resources/land.json"), .copy("Resources/land50.json")]
        ),
        .executableTarget(
            name: "xptb-cli",
            dependencies: ["SceneryKit"]
        ),
        .testTarget(
            name: "SceneryKitTests",
            dependencies: ["SceneryKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
