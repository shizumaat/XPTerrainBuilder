import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// #2301: a launch draws last session's map (tiles, World states, imagery
/// sources) before the engine has booted; each cache describes only what
/// it was taken against.
final class LaunchCacheTests: XCTestCase {
    private var dir: URL!

    override func setUpWithError() throws {
        dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("LaunchCacheTests-\(UUID().uuidString)", isDirectory: true)
    }

    override func tearDownWithError() throws {
        try? FileManager.default.removeItem(at: dir)
    }

    private func tile(_ lat: Int, _ lon: Int) -> O4TileInfo {
        O4TileInfo(json: .object(["lat": .int(lat), "lon": .int(lon),
                                  "build_dir": .string("/w/t"), "provider": .string("BI")]))!
    }

    private func contents(world: Int) -> TileScanCache.Contents {
        TileScanCache.Contents(
            built: [tile(48, -6)], installed: [[48, -6], [49, -6]],
            world: (0..<world).map {
                .init(lat: $0 / 360 - 90, lon: $0 % 360 - 180,
                      tile: O4WorldTile(state: .meshLowRes, origin: "xptb", sharp: 0.5,
                                        source: "lean", volume: "", dsf: "/p/x.dsf",
                                        provider: "BI"))
            })
    }

    func testTileScanKeepsTheWorldStates() {
        let url = dir.appendingPathComponent("tile-scan.json")
        let saved = contents(world: 3)
        TileScanCache.save(saved, workingDir: "/w", customSceneryDir: "/cs", url: url)
        XCTAssertEqual(TileScanCache.load(workingDir: "/w", customSceneryDir: "/cs", url: url),
                       saved)
        XCTAssertNil(TileScanCache.load(workingDir: "/other", customSceneryDir: "/cs", url: url))
        XCTAssertNil(TileScanCache.load(workingDir: "/w", customSceneryDir: "/other", url: url))
    }

    /// A World install lists ~18,000 tiles; reading them back is part of
    /// the window opening, so it must stay well under a second.
    func testAFullWorldInstallReadsBackQuickly() {
        let url = dir.appendingPathComponent("tile-scan.json")
        TileScanCache.save(contents(world: 18_260), workingDir: "/w", customSceneryDir: "/cs",
                           url: url)
        let start = Date()
        let loaded = TileScanCache.load(workingDir: "/w", customSceneryDir: "/cs", url: url)
        let seconds = Date().timeIntervalSince(start)
        XCTAssertEqual(loaded?.world.count, 18_260)
        XCTAssertLessThan(seconds, 1.0)
        print("tile-scan cache: 18260 World tiles read back in \(Int(seconds * 1000)) ms")
    }

    func testImagerySourcesAreKeptPerEngineVersion() throws {
        let url = dir.appendingPathComponent("imagery-sources.json")
        let json = Data(#"[{"code":"BI","region":"Global","name":"Bing","combined":false,"members":[],"buildable":true,"previewable":true,"reason":"","preview":{"template":"https://t/{z}/{x}/{y}","referer":""},"attribution":"","max_zl":19}]"#.utf8)
        let sources = try JSONDecoder().decode([O4ImagerySource].self, from: json)
        ImagerySourcesCache.save(sources, engineVersion: "1.50.1902", url: url)
        XCTAssertEqual(ImagerySourcesCache.load(engineVersion: "1.50.1902", url: url), sources)
        XCTAssertNil(ImagerySourcesCache.load(engineVersion: "1.50.1903", url: url))
        ImagerySourcesCache.save([], engineVersion: "1.50.1903", url: url)
        XCTAssertNil(ImagerySourcesCache.load(engineVersion: "1.50.1903", url: url),
                     "an empty answer never replaces a kept list")
    }
}
