import Foundation

/// `world_tile_use` result (#2100, capability `world_tile_use`): the tile,
/// whether it was asked on or off, and where it stands now — "on", "off",
/// "turning_off" or "turning_on" (X-Plane may hold the tile; the engine
/// completes it once X-Plane lets go).
public struct O4WorldTileUse: Decodable, Equatable, Sendable {
    public let tile: String
    public let use: Bool
    public let state: String

    public init(tile: String, use: Bool, state: String) {
        self.tile = tile
        self.use = use
        self.state = state
    }

    /// The note after the change (Qt: `O4_World_State_Text.use_note`).
    public var note: String {
        (O4WorldStateText.useNotes[state] ?? "").replacingOccurrences(of: "{tile}", with: tile)
    }
}

extension OrthoEngineClient {
    /// `world_tile_use`: XPTerrainBuilder on (`use`) or off on a tile of
    /// the World pack in `sceneryDir`; sync (a few renames).
    public func worldTileUse(lat: Int, lon: Int, use: Bool, sceneryDir: String) async throws -> O4WorldTileUse {
        try await request("world_tile_use", ["lat": lat, "lon": lon, "use": use,
                                             "scenery_dir": sceneryDir])
    }
}
