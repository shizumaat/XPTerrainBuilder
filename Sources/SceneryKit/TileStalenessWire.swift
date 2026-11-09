import Foundation

// MARK: - Stale tiles (#1958)

/// The engine's `tile_staleness` result (`Ortho4XP/src/O4_Tile_Staleness.py`):
/// for every built tile whose airport packs are on record, whether the
/// packs X-Plane draws now are still the ones its patches were fitted to.
public struct O4TileStaleness: Decodable, Equatable, Sendable {
    public let tiles: [O4StaleTile]
    public let stale: Int
    public let checked: Int
}

/// One tile's verdict. `packs` is the pack each airport was built on.
public struct O4StaleTile: Decodable, Equatable, Sendable {
    public let lat: Int
    public let lon: Int
    public let checked: Bool
    public let stale: Bool
    public let airports: [O4StaleAirport]
    public let packs: [String: String]

    /// The map's pill on a stale tile: "Stale: EGKK" or "Stale: EGKK +2".
    public var label: String {
        guard let first = airports.first else { return "" }
        return airports.count > 1 ? "Stale: \(first.icao) +\(airports.count - 1)"
                                  : "Stale: \(first.icao)"
    }
}

/// Why the tile is stale for one airport: `gone`, `disabled`,
/// `superseded` or `changed` (`O4_Tile_Staleness.REASONS`), and the
/// sentence the tile pane shows.
public struct O4StaleAirport: Decodable, Equatable, Sendable {
    public let icao: String
    public let reason: String
    public let pack: String
    public let nowPack: String
    public let text: String

    private enum CodingKeys: String, CodingKey {
        case icao, reason, pack, text
        case nowPack = "now_pack"
    }
}

/// The words of #1958, shared with the Qt app (`O4_Qt_Map_Legend`).
public enum O4TileStaleText {
    /// The tile pane's row title.
    public static let rowTitle = "Airport packs"
    /// The tile pane's sentence under a stale tile's reasons.
    public static let rebuildNote = "Rebuild to fit the airports X-Plane draws now."
    /// The rebuild button.
    public static let rebuildButton = "Rebuild Tile"
}

extension OrthoEngineClient {
    /// Checks `tiles` (`(lat, lon, build folder)`) against what X-Plane
    /// draws from `customSceneryDir` now. Runs on the engine's worker.
    public func tileStaleness(customSceneryDir: String,
                              tiles: [(Int, Int, String)]) async throws -> O4TileStaleness {
        try await libraryRequest("tile_staleness", [
            "custom_scenery_dir": customSceneryDir,
            "tiles": tiles.map { [$0.0, $0.1, $0.2] as [Any] },
        ])
    }
}
