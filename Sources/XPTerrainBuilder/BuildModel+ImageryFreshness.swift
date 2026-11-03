import Foundation
import SceneryKit

extension BuildModel {
    /// Re-check the tile's imagery (#1666) when the tile, its folder, a
    /// scan or a build changes.
    func imageryFreshnessKey(for coord: TileCoord?) -> String {
        guard let coord else { return "freshness|" }
        return "freshness|\(coord.key)|\(built[coord]?.buildDir ?? "")|\(built.count)|\(isBuilding)"
    }

    /// "Update Imagery": outside a run only — remove the tile's downloaded
    /// imagery, then rebuild it. The sentence why not, or nil.
    func updateImagery(_ coord: TileCoord) async -> String? {
        if isBuilding { return "Wait for the current run to finish, then update the imagery." }
        if let refusal = rebuildRefusal(coord) { return refusal }
        if let failure = await discardTileImagery(coord) { return failure }
        startRebuild(coord)
        return nil
    }
}
