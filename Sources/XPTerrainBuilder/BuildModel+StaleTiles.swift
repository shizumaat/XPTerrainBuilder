import Foundation
import SceneryKit

extension BuildModel {
    /// Asks the engine which built tiles no longer fit the airport packs
    /// X-Plane draws (#1958, `O4_Tile_Staleness`). Runs after every scan —
    /// at launch, and whenever Custom Scenery changes (its watcher
    /// rescans) — and after a build, which rescans too.
    func refreshStaleTiles() {
        guard engineCapabilities.supports(O4EngineCapabilities.tileStaleness),
              let (client, _, scenery) = libraryContext() else { return }
        guard !scenery.isEmpty else { staleTiles = [:]; return }
        let tiles = built.filter { !$0.value.builtElsewhere && $0.value.lastBuild != nil }
            .map { ($0.key.lat, $0.key.lon, $0.value.buildDir) }
        guard !tiles.isEmpty else { staleTiles = [:]; return }
        Task { [weak self] in
            guard let reply = try? await client.tileStaleness(customSceneryDir: scenery,
                                                              tiles: tiles) else { return }
            var found: [TileCoord: O4StaleTile] = [:]
            for row in reply.tiles where row.stale {
                found[TileCoord(lat: row.lat, lon: row.lon)] = row
            }
            self?.staleTiles = found
        }
    }
}
