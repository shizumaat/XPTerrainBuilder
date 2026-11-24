import Testing
import Foundation
@testable import SceneryKit

/// This app's own config names (#1229, RULINGS 2026-10-26c); the engine twin is
/// `Ortho4XP/tests/test_config_names.py`. Also the `custom_patches` /
/// `custom_patch_use` replies (`Ortho4XP/tests/test_custom_patches.py`).
struct OrthoConfigNamesTests {

    @Test func names() {
        #expect(OrthoConfigNames.globalFileName == "XPTerrainBuilder.cfg")
        #expect(OrthoConfigNames.tileFileName(lat: 47, lon: 11) == "XPTerrainBuilder_+47+011.cfg")
        #expect(OrthoConfigNames.tileFileName(lat: -5, lon: -120) == "XPTerrainBuilder_-05-120.cfg")
    }

    @Test func customPatchRepliesDecode() throws {
        func reply(_ json: String) throws -> O4Reply {
            let object = try JSONSerialization.jsonObject(with: Data(json.utf8))
            return O4Reply(ok: true, result: O4JSON.from(object), error: nil)
        }
        let listed: Result<O4CustomPatches, Error> = OrthoEngineClient.decodeReply(
            try reply(#"{"tiles": [{"lat": 30, "lon": 31, "files": ["HECA.patch.osm"]}]}"#),
            command: "custom_patches")
        #expect(try listed.get().tiles == [O4CustomPatchTile(lat: 30, lon: 31, files: ["HECA.patch.osm"])])
        // #2179: one picker row per airport; the `custom_patch_use` reply
        // is the same row.
        let used: Result<O4CustomPatchUse, Error> = OrthoEngineClient.decodeReply(
            try reply(#"{"icao": "HECA", "tile": [30, 31], "files": ["HECA.patch.osm"], "use": "auto_patch", "chosen": true, "warning": ""}"#),
            command: "custom_patch_use")
        #expect(try used.get() == O4CustomPatchUse(
            icao: "HECA", tile: O4TileRef(lat: 30, lon: 31), files: ["HECA.patch.osm"],
            use: O4CustomPatchUse.autoPatch, chosen: true))
        let rows: Result<O4CustomPatches, Error> = OrthoEngineClient.decodeReply(
            try reply(#"{"tiles": [{"lat": 30, "lon": 31, "files": ["HECA.patch.osm"], "airports": [{"icao": "HECA", "tile": [30, 31], "files": ["HECA.patch.osm"], "use": "as_made", "chosen": false, "warning": "Higher-resolution elevation is available for this airport, but it requires our auto patch."}]}]}"#),
            command: "custom_patches")
        #expect(try rows.get().tiles.first?.airports.first?.warning == O4CustomPatchText.asMadeWarning)
        #expect(try listed.get().tiles.first?.airports == [])
        // #2179: the elevation notice rides on the tile row; an older
        // engine sends none.
        let noticed: Result<O4CustomPatches, Error> = OrthoEngineClient.decodeReply(
            try reply(#"{"tiles": [{"lat": 30, "lon": 31, "files": ["HECA.patch.osm"], "notices": [{"icao": "HECA", "file": "HECA.patch.osm", "source": "base elevation (Viewfinderpanoramas)", "text": "This custom patch …"}]}]}"#),
            command: "custom_patches")
        #expect(try noticed.get().tiles.first?.notices
                == [O4CustomPatchNotice(icao: "HECA", file: "HECA.patch.osm",
                                        source: "base elevation (Viewfinderpanoramas)",
                                        text: "This custom patch …")])
        #expect(try listed.get().tiles.first?.notices == [])
        #expect(O4CustomPatchText.info(["HECA.patch.osm"]) == "HECA.patch.osm")
        #expect(O4CustomPatchText.title(of: O4CustomPatchUse.autoPatch) == "Our auto patch")
        #expect(O4CustomPatchText.title(of: O4CustomPatchUse.asMade) == "As made")
    }
}
