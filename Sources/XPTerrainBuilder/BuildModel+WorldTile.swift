import Foundation
import SceneryKit

extension BuildModel {
    /// The tile pane's "Remove from World Pack…" (`TileWorldRow`; Qt:
    /// `O4_Qt_Tile_World_Row`): the engine writes the tile's package, then
    /// puts the placeholder over it (`world_tile_remove`; originals/ and
    /// other drives untouched). Returns the note to show; the map rescans.
    func removeFromWorldPack(_ coord: TileCoord) async -> String {
        guard engineCapabilities.supports(O4EngineCapabilities.worldTileRemove),
              let context = libraryContext() else {
            return "This engine cannot remove a tile from the World pack."
        }
        do {
            let done = try await context.client.worldTileRemove(
                lat: coord.lat, lon: coord.lon, sceneryDir: context.sceneryDir)
            rescan()
            return done.note
        } catch {
            return error.localizedDescription
        }
    }
}
