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
            // Resources/VERSION is the app's tracked version (scripts/make_app.sh
            // bumps it and stamps the same string into Info.plist); shipping it
            // as a resource means `swift run` reports the same version as the
            // packaged app.
            resources: [.copy("Resources/land.json"), .copy("Resources/land50.json"),
                        .copy("Resources/VERSION")]
        ),
        .testTarget(
            name: "SceneryKitTests",
            dependencies: ["SceneryKit"],
            resources: [.copy("Fixtures")]
        ),
    ]
)
