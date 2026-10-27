import Testing
import Foundation
@testable import SceneryKit

/// The `tile_texture_check` reply (protocol 1.22). The JSON and the words
/// are what `Ortho4XP/tests/test_tile_texture_check.py` pins on the
/// engine side; a renamed key or a changed sentence fails one of the two.
struct TileTextureCheckTests {

    private func decode(_ json: String) throws -> O4TileTextureCheck {
        let object = try JSONSerialization.jsonObject(with: Data(json.utf8))
        let reply = O4Reply(ok: true, result: O4JSON.from(object), error: nil)
        let result: Result<O4TileTextureCheck, Error> =
            OrthoEngineClient.decodeReply(reply, command: "tile_texture_check")
        return try result.get()
    }

    @Test func missingTexturesDecodeWithTheEngineWords() throws {
        let check = try decode(#"""
        {"build_dir": "/t/zOrtho4XP_-42+175", "checked": true, "missing_count": 5,
         "missing": ["a.dds", "b.dds", "c.dds", "d.dds"]}
        """#)
        #expect(check.checked && check.missingCount == 5)
        #expect(check.warningText == "5 textures missing — X-Plane cannot load this tile")
        #expect(check.detailText.contains("(a.dds, b.dds, c.dds and 2 more)"))
        let one = O4TileTextureCheck(buildDir: "", checked: true, missingCount: 1, missing: ["a.dds"])
        #expect(one.warningText == "1 texture missing — X-Plane cannot load this tile")
        let many = O4TileTextureCheck(buildDir: "", checked: true, missingCount: 1805, missing: [])
        #expect(many.warningText.hasPrefix("1,805 textures missing"))
    }

    @Test func aTileWithoutTerrainIsNotChecked() throws {
        let check = try decode(#"{"build_dir": "", "checked": false, "missing_count": 0, "missing": []}"#)
        #expect(!check.checked && check.missingCount == 0)
    }
}
