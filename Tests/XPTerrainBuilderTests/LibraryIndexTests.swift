import Foundation
import Testing
@testable import XPTerrainBuilder
@testable import SceneryKit

/// #2006: the Library table's selection, indexed once per scan. The
/// synthetic library is 3,000 tiles (the owner's held ~2,590); the old
/// per-redraw work re-filtered every tile against every tile.
struct LibraryIndexTests {
    static func library(_ count: Int) throws -> [O4LibraryTile] {
        let rows = (0..<count).map { i -> [String: Any] in
            let lat = i / 360 - 60, lon = i % 360 - 180
            return ["tile": TileMath.key(lat: lat, lon: lon), "lat": lat, "lon": lon,
                    "build_dir": "/t/\(i)", "size_bytes": i * 1000, "zl": 17, "provider": "BI",
                    "built": 1.7e9, "airports": [], "packs_modified": [], "link_status": "installed",
                    "in_xplane": i % 2 == 0, "built_by": "XPTerrainBuilder", "read_only": false]
        }
        let data = try JSONSerialization.data(withJSONObject: rows)
        return try JSONDecoder().decode([O4LibraryTile].self, from: data)
    }

    static func coords(_ tiles: [O4LibraryTile], every step: Int) -> Set<BuildModel.TileCoord> {
        Set(stride(from: 0, to: tiles.count, by: step).map {
            BuildModel.TileCoord(lat: tiles[$0].lat, lon: tiles[$0].lon)
        })
    }

    @Test func selectionMatchesTheMapAndKeepsTableOrder() throws {
        let tiles = try Self.library(500)
        let index = LibraryIndex(tiles)
        let selected = Self.coords(tiles, every: 7)
        let ids = index.ids(of: selected)
        let old = Set(tiles.filter {
            selected.contains(BuildModel.TileCoord(lat: $0.lat, lon: $0.lon))
        }.map(\.id))
        #expect(ids == old)
        #expect(index.rows(ids) == tiles.filter { ids.contains($0.id) })
        #expect(Set(index.coords(ids)) == selected)
        #expect(index.row(tiles[3].id) == tiles[3])
    }

    @Test func installedSetUpdatesTheSwitchWithoutAScan() throws {
        var index = LibraryIndex(try Self.library(10))
        index.applyInstalled([BuildModel.TileCoord(lat: index.tiles[1].lat, lon: index.tiles[1].lon)])
        #expect(index.tiles.filter(\.inXPlane).map(\.id) == [index.tiles[1].id])
    }

    @Test func searchAndSortKeepTheOldRows() throws {
        let tiles = try Self.library(400)
        let order = [KeyPathComparator(\O4LibraryTile.sizeBytes, order: .reverse)]
        let shown = LibraryIndex(tiles).shown(query: "+10", sortOrder: order)
        #expect(shown == tiles.filter { $0.matches("+10") }.sorted(using: order))
    }

    /// One redraw's selection work (~15 accesses), before and after, on
    /// 3,000 tiles with every 10th selected. Printed for the lane report;
    /// the bound is loose so a loaded CI machine passes.
    @Test func oneRedrawIsFastOnThreeThousandTiles() throws {
        let tiles = try Self.library(3000)
        let selected = Self.coords(tiles, every: 10)
        let clock = ContinuousClock()
        let before = clock.measure {
            // The pre-#2006 `selectedRows`: the selection getter (itself a
            // filter over every tile) evaluated inside a filter over every tile.
            func selection() -> Set<String> {
                Set(tiles.filter { selected.contains(BuildModel.TileCoord(lat: $0.lat, lon: $0.lon)) }.map(\.id))
            }
            for _ in 0..<2 { _ = tiles.filter { selection().contains($0.id) } }
        }
        let after = clock.measure {
            let index = LibraryIndex(tiles)
            for _ in 0..<15 { _ = index.rows(index.ids(of: selected)) }
        }
        print("LibraryIndex 3000 tiles: old 2 accesses \(before), new index + 15 accesses \(after)")
        #expect(after < .milliseconds(250))
        #expect(after < before)
    }
}
