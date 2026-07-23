import Foundation
import SceneryKit

/// Persisted engine tile-scan results (built + installed tiles), keyed by
/// the exact (working dir, Custom Scenery dir) pair the scan ran against.
/// Powers optimistic launch for the build map: last session's tile squares
/// appear the moment the window opens; the engine's first rescan
/// revalidates in the background and swaps in the truth on ScanDone.
enum TileScanCache {
    private struct Snapshot: Codable {
        let version: Int
        let workingDir: String
        let customSceneryDir: String
        let built: [O4TileInfo]
        /// [lat, lon] pairs (TileCoord is a MainActor-nested type; raw
        /// pairs keep the codec actor-free).
        let installed: [[Int]]
    }

    private static let version = 1

    private static var fileURL: URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first!
            .appendingPathComponent("XPTerrainBuilder", isDirectory: true)
            .appendingPathComponent("tile-scan.json")
    }

    /// Last session's tiles, or nil when the cache is missing or was
    /// scanned against different folders.
    static func load(workingDir: String, customSceneryDir: String)
        -> (built: [O4TileInfo], installed: [[Int]])? {
        guard let data = try? Data(contentsOf: fileURL),
              let snap = try? JSONDecoder().decode(Snapshot.self, from: data),
              snap.version == version,
              snap.workingDir == workingDir,
              snap.customSceneryDir == customSceneryDir
        else { return nil }
        return (snap.built, snap.installed)
    }

    static func save(built: [O4TileInfo], installed: [[Int]],
                     workingDir: String, customSceneryDir: String) {
        let snap = Snapshot(version: version, workingDir: workingDir,
                            customSceneryDir: customSceneryDir,
                            built: built, installed: installed)
        guard let data = try? JSONEncoder().encode(snap) else { return }
        try? FileManager.default.createDirectory(
            at: fileURL.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: fileURL, options: .atomic)
    }
}
