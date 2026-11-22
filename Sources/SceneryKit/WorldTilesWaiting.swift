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

    public init(waiting: [String] = [], reload: [String] = []) {
        self.waiting = waiting
        self.reload = reload
    }

    /// Parses a `WorldTilesWaiting` event object.
    public static func parse(_ object: [String: Any]) -> O4WorldTilesWaiting {
        O4WorldTilesWaiting(
            waiting: (object["waiting"] as? [Any] ?? []).compactMap { $0 as? String },
            reload: (object["reload"] as? [Any] ?? []).compactMap { $0 as? String })
    }
}
