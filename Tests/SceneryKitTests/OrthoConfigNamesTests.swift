import Testing
import Foundation
@testable import SceneryKit

/// This app's own config names (#1229, RULINGS 2026-10-26c); the engine twin is
/// `Ortho4XP/tests/test_config_names.py`. Also the `custom_patches` /
/// `use_auto_patch` replies (`Ortho4XP/tests/test_custom_patches.py`).
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
        let setAside: Result<O4UseAutoPatchReply, Error> = OrthoEngineClient.decodeReply(
            try reply(#"{"set_aside": ["/p/HECA.patch.osm.disabled"]}"#),
            command: "use_auto_patch")
        #expect(try setAside.get().setAside == ["/p/HECA.patch.osm.disabled"])
        #expect(O4CustomPatchText.info(["HECA.patch.osm"])
                == "HECA.patch.osm — the auto patch does not run for this airport")
    }
}
