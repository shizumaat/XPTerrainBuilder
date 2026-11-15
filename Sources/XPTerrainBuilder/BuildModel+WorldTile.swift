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

    /// The tile menu's "Use XPTerrainBuilder here" (#2100; Qt:
    /// `O4_Qt_Tile_Menu` `use_here`): offered for a tile the World pack
    /// holds, checked while it is on; nil otherwise or with an older engine.
    func useHereItem(_ coord: TileCoord) -> (on: Bool, set: (Bool) -> Void)? {
        let world = worldTiles[coord]
        guard engineCapabilities.supports(O4EngineCapabilities.worldTileUse),
              O4WorldStateText.useOffered(world) else { return nil }
        return (O4WorldStateText.useOn(world), { [weak self] use in
            Task { @MainActor in _ = await self?.setUseHere(coord, use) }
        })
    }

    /// XPTerrainBuilder on or off on the tile (`world_tile_use`): the
    /// engine keeps the built tile aside while it is off. The note goes to
    /// the console (Qt: the status bar) and is returned; the map rescans.
    @discardableResult
    func setUseHere(_ coord: TileCoord, _ use: Bool) async -> String {
        var note = "This engine cannot turn XPTerrainBuilder off on a tile."
        if let context = libraryContext() {
            do {
                note = try await context.client.worldTileUse(
                    lat: coord.lat, lon: coord.lon, use: use, sceneryDir: context.sceneryDir).note
                rescan()
            } catch {
                note = error.localizedDescription
            }
        }
        console.append(note)
        return note
    }
}
