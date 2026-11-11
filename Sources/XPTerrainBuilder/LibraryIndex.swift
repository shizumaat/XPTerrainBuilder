import SwiftUI
import SceneryKit

/// The Library table's rows, indexed once per scan (#2006): by id and by
/// tile coordinate, so the map's selection becomes the table's (one
/// selection, RULINGS 2026-11-10j) in O(selected) instead of re-filtering
/// every tile against every tile (O(n²); ~15 times per redraw on the
/// owner's 2,590 tiles held the main thread at 100 %).
struct LibraryIndex {
    typealias ID = O4LibraryTile.ID

    private(set) var tiles: [O4LibraryTile] = []
    private var position: [ID: Int] = [:]
    private var idByCoord: [BuildModel.TileCoord: ID] = [:]

    init(_ tiles: [O4LibraryTile] = []) {
        self.tiles = tiles
        position.reserveCapacity(tiles.count)
        idByCoord.reserveCapacity(tiles.count)
        for (index, row) in tiles.enumerated() {
            position[row.id] = index
            idByCoord[BuildModel.TileCoord(lat: row.lat, lon: row.lon)] = row.id
        }
    }

    func row(_ id: ID) -> O4LibraryTile? {
        position[id].map { tiles[$0] }
    }

    /// The rows of the selected map tiles.
    func ids(of coords: Set<BuildModel.TileCoord>) -> Set<ID> {
        Set(coords.compactMap { idByCoord[$0] })
    }

    /// `ids`' rows, in table-model order.
    func rows(_ ids: Set<ID>) -> [O4LibraryTile] {
        ids.compactMap { position[$0] }.sorted().map { tiles[$0] }
    }

    /// `ids`' tiles, in table-model order.
    func coords(_ ids: Set<ID>) -> [BuildModel.TileCoord] {
        rows(ids).map { BuildModel.TileCoord(lat: $0.lat, lon: $0.lon) }
    }

    /// The rows the search keeps, in the table's sort order.
    func shown(query: String, sortOrder: [KeyPathComparator<O4LibraryTile>]) -> [O4LibraryTile] {
        let query = query.lowercased()
        let kept = query.isEmpty ? tiles : tiles.filter { $0.matches(query) }
        return kept.sorted(using: sortOrder)
    }

    /// The map's installed set, between scans (no folder walk).
    mutating func applyInstalled(_ installed: Set<BuildModel.TileCoord>) {
        for index in tiles.indices {
            let now = installed.contains(BuildModel.TileCoord(lat: tiles[index].lat, lon: tiles[index].lon))
            if tiles[index].inXPlane != now { tiles[index].inXPlane = now }
        }
    }
}
