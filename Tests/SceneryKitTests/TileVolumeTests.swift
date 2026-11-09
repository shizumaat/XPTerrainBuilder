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
}
