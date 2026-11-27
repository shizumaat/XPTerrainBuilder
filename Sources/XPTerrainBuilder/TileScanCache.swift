import Foundation
import SceneryKit

/// Persisted engine tile-scan results (built + installed tiles and the
/// World pack's tile states), keyed by the exact (working dir, Custom
/// Scenery dir) pair the scan ran against. Powers optimistic launch for
/// the build map: last session's tiles appear the moment the window opens,
/// drawn in their World states; the engine's first rescan revalidates in
/// the background and swaps in the truth on ScanDone.
enum TileScanCache {
    /// One World-pack tile state (`ScanBatch.world`, #2024).
    struct WorldEntry: Codable, Equatable {
        let lat: Int
        let lon: Int
        let tile: O4WorldTile
    }

    struct Contents: Equatable {
        let built: [O4TileInfo]
        /// [lat, lon] pairs (TileCoord is a MainActor-nested type; raw
        /// pairs keep the codec actor-free).
        let installed: [[Int]]
        let world: [WorldEntry]
    }

    private struct Snapshot: Codable {
        let version: Int
        let workingDir: String
        let customSceneryDir: String
        let built: [O4TileInfo]
        let installed: [[Int]]
        let world: [WorldEntry]
    }

    // v7: the World pack's tile states (#2301: without them every built
    // tile drew as Full until the scan's last phase, ~20 s on a World
    // install, and the World borders filled in tile by tile);
    // v6: O4TileInfo gained origin (#1958);
    // v5: O4TileInfo gained resolvedDir/volume/volumeMounted (#1987);
    // v4: O4TileInfo gained detectedProvider/detectedZL (#1334);
    // v3: providers cached with legacy cfg quotes ('Arc') poisoned the
    // imagery-source audit; v2: O4TileInfo gained highZLAirports/coverZL.
    static let version = 7

    static let defaultURL = LaunchCacheFile.url("tile-scan.json")

    /// Last session's tiles, or nil when the cache is missing or was
    /// scanned against different folders.
    static func load(workingDir: String, customSceneryDir: String,
                     url: URL = defaultURL) -> Contents? {
        guard let snap = LaunchCacheFile.read(Snapshot.self, from: url),
              snap.version == version,
              snap.workingDir == workingDir,
              snap.customSceneryDir == customSceneryDir
        else { return nil }
        return Contents(built: snap.built, installed: snap.installed, world: snap.world)
    }

    static func save(_ contents: Contents, workingDir: String, customSceneryDir: String,
                     url: URL = defaultURL) {
        LaunchCacheFile.write(
            Snapshot(version: version, workingDir: workingDir,
                     customSceneryDir: customSceneryDir, built: contents.built,
                     installed: contents.installed, world: contents.world),
            to: url)
    }
}
