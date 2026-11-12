import Foundation
import Testing
@testable import SceneryKit

/// #1987: the scan's drive fields reach the app, and the words match the
/// engine's `O4_Tile_Volume` (Python twin: tests/test_tile_volume.py).
struct TileVolumeTests {
    @Test func aTileOnAnotherDriveCarriesItsDrive() throws {
        let info = try #require(O4TileInfo(json: .object([
            "lat": .int(10), "lon": .int(10),
            "build_dir": .string("/cs/zOrtho4XP_+10+010"),
            "resolved_dir": .string("/Volumes/Ext/zOrtho4XP_+10+010"),
            "volume": .string("Ext"), "volume_mounted": .bool(false),
        ])))
        #expect(info.volume == "Ext")
        #expect(info.folderPath == "/Volumes/Ext/zOrtho4XP_+10+010")
        #expect(!info.folderReachable)
    }

    @Test func aLocalTileOrAnOlderEngineHasNoDrive() throws {
        let local = try #require(O4TileInfo(json: .object([
            "lat": .int(1), "lon": .int(2), "build_dir": .string("/cs/t"),
            "resolved_dir": .string(""), "volume": .string(""),
            "volume_mounted": .bool(true),
        ])))
        #expect(local.volume == nil && local.folderPath == "/cs/t" && local.folderReachable)
        let older = try #require(O4TileInfo(json: .object([
            "lat": .int(1), "lon": .int(2), "build_dir": .string("/cs/t"),
        ])))
        #expect(older.volume == nil && older.folderPath == "/cs/t" && older.folderReachable)
    }

    @Test func theWordsAreTheEngines() {
        #expect(O4TileVolumeText.requiresLabel("ThunderBlade") == "Requires ThunderBlade")
        #expect(O4TileVolumeText.offlineNote("ThunderBlade") == "ThunderBlade is not connected.")
    }

    /// #2027: an adopted tile's folder holds only records, so "Show in
    /// Finder" reveals its DSF in the World pack (Python twin:
    /// test_world_state.py `world_dsf`).
    @Test func aRecordsOnlyTileRevealsItsWorldDSF() throws {
        let row = try #require(O4WorldTile.row([51, 22, "full", "adopted", 1, "lean", "",
                                                "/cs/World/a.dsf"] as [Any]))
        let records = try #require(O4TileInfo(json: .object([
            "lat": .int(51), "lon": .int(22), "build_dir": .string("/d/t"),
            "dsf_present": .bool(false),
        ])))
        let own = try #require(O4TileInfo(json: .object([
            "lat": .int(51), "lon": .int(22), "build_dir": .string("/d/t"),
            "dsf_present": .bool(true),
        ])))
        #expect(row.tile.revealDSF(records) == "/cs/World/a.dsf")
        #expect(row.tile.revealDSF(nil) == "/cs/World/a.dsf")
        #expect(row.tile.revealDSF(own) == nil)
        let older = try #require(O4WorldTile.row([51, 22, "full", "", 1, "", ""] as [Any]))
        #expect(older.tile.dsf == nil && older.tile.revealDSF(records) == nil)
    }
}
