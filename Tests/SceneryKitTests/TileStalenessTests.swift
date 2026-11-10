import Foundation
import Testing
@testable import SceneryKit

/// #1958: the engine's `tile_staleness` result and the scan's `origin`
/// reach the app (Python twin: Ortho4XP/tests/test_tile_staleness.py).
struct TileStalenessTests {
    @Test func aStaleVerdictDecodes() throws {
        let json = O4JSON.object([
            "tiles": .array([.object([
                "lat": .int(41), "lon": .int(12), "checked": .bool(true), "stale": .bool(true),
                "packs": .object(["LIRF": .string("LIRF pack"), "LIRA": .string("Global Airports")]),
                "airports": .array([
                    .object(["icao": .string("LIRF"), "reason": .string("disabled"),
                             "pack": .string("LIRF pack"), "now_pack": .string(""),
                             "text": .string("LIRF: its pack LIRF pack is disabled in scenery_packs.ini")]),
                    .object(["icao": .string("LIRA"), "reason": .string("superseded"),
                             "pack": .string("Global Airports"), "now_pack": .string("Rome pack"),
                             "text": .string("LIRA: X-Plane now draws Rome pack, not Global Airports")]),
                ]),
            ])]),
            "stale": .int(1), "checked": .int(1),
        ])
        let reply = try json.decode(O4TileStaleness.self)
        let tile = try #require(reply.tiles.first)
        #expect(tile.stale && tile.airports.count == 2)
        #expect(tile.airports[1].nowPack == "Rome pack")
        #expect(tile.label == "Stale: LIRF +1")
    }

    @Test func originSaysWhoBuiltTheTile() throws {
        let other = try #require(O4TileInfo(json: .object([
            "lat": .int(1), "lon": .int(2), "build_dir": .string("/t"), "origin": .string("other"),
        ])))
        #expect(other.builtElsewhere)
        let ours = try #require(O4TileInfo(json: .object([
            "lat": .int(1), "lon": .int(2), "build_dir": .string("/t"), "origin": .string("xptb"),
        ])))
        #expect(!ours.builtElsewhere)
        let older = try #require(O4TileInfo(json: .object([
            "lat": .int(1), "lon": .int(2), "build_dir": .string("/t"),
        ])))
        #expect(!older.builtElsewhere)
    }

    @Test func theEngineAnnouncesTheCheck() {
        let caps = O4EngineCapabilities(protocolVersion: "1.32", flags: ["tile_staleness"])
        #expect(caps.supports(O4EngineCapabilities.tileStaleness))
        #expect(!O4EngineCapabilities(protocolVersion: "1.32", flags: [])
            .supports(O4EngineCapabilities.tileStaleness))
    }
}
