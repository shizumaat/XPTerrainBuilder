import Foundation

/// The built tiles not yet in the World pack, and those that went in over
/// a version X-Plane loaded (engine `WorldTilesWaiting`, #2175, RULINGS
/// 2026-11-19e; capability `world_tiles_waiting`). The field names are the
/// JSON keys of `class WorldTilesWaiting` in
/// `Ortho4XP/src/o4_engine/events.py`; an empty pair clears the notes.
public struct O4WorldTilesWaiting: Sendable, Equatable {
    /// Tile names ("+41-088") staged while X-Plane loads them.
    public let waiting: [String]
    /// Tile names a "Reload scenery" would show now.
    public let reload: [String]
    /// The built tiles that did NOT go into the World pack (#2226, engine
    /// `world_publish_failed`), until the tile's next publish succeeds.
    public let failed: [O4WorldPublishFailure]

    public init(waiting: [String] = [], reload: [String] = [],
                failed: [O4WorldPublishFailure] = []) {
        self.waiting = waiting
        self.reload = reload
        self.failed = failed
    }

    /// The failure of tile `tile`, if it did not go in.
    public func failure(tile: String) -> O4TileFailure? {
        failed.first { $0.tile == tile }?.failure
    }

    /// Parses a `WorldTilesWaiting` event object.
    public static func parse(_ object: [String: Any]) -> O4WorldTilesWaiting {
        let failed = (object["failed"] as? [[String: Any]] ?? []).compactMap { entry -> O4WorldPublishFailure? in
            guard let tile = entry["tile"] as? String,
                  let failure = O4TileFailure.parseList([entry], defaultSeverity: "degraded").first
            else { return nil }
            return O4WorldPublishFailure(tile: tile, utc: entry["utc"] as? String ?? "", failure: failure)
        }
        return O4WorldTilesWaiting(
            waiting: (object["waiting"] as? [Any] ?? []).compactMap { $0 as? String },
            reload: (object["reload"] as? [Any] ?? []).compactMap { $0 as? String },
            failed: failed)
    }
}

/// One built tile the World pack refused (#2226): the engine's words in a
/// `BuildDone.warnings`-shaped entry, its tile and when it was noted.
public struct O4WorldPublishFailure: Sendable, Equatable {
    public let tile: String
    public let utc: String
    public let failure: O4TileFailure

    public init(tile: String, utc: String = "", failure: O4TileFailure) {
        self.tile = tile
        self.utc = utc
        self.failure = failure
    }

    /// Identifies one occurrence: an app raises each once.
    public var key: String { tile + "|" + utc }
}
