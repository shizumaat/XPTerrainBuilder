import Testing
import Foundation
@testable import SceneryKit

/// The `tile_customizations` reply (#1350). The JSON is what
/// `Ortho4XP/tests/test_tile_customizations.py` round-trips on the engine
/// side; a renamed key on either side fails one of the two.
struct TileCustomizationsTests {

    private func decode(_ json: String) throws -> O4TileCustomizations {
        let object = try JSONSerialization.jsonObject(with: Data(json.utf8))
        let reply = O4Reply(ok: true, result: O4JSON.from(object), error: nil)
        let result: Result<O4TileCustomizations, Error> =
            OrthoEngineClient.decodeReply(reply, command: "tile_customizations")
        return try result.get()
    }

    @Test func twoOverridesDecodeWithTheirDefaults() throws {
        let reply = try decode(#"""
        {"lat": 45, "lon": 5, "customizations": [
          {"key": "road_level", "label": "Which roads should the ground be levelled for?",
           "tile_value": "5", "default_value": "4", "tile_text": "+ dirt tracks",
           "default_text": "+ service roads", "affects_output": true},
          {"key": "color_harmonization", "label": "Colour harmonization",
           "tile_value": "False", "default_value": "True", "tile_text": "Off",
           "default_text": "On", "affects_output": false}]}
        """#)
        #expect(reply.lat == 45 && reply.lon == 5)
        #expect(reply.customizations.map(\.key) == ["road_level", "color_harmonization"])
        let road = reply.customizations[0]
        #expect(road.defaultValue == "4" && road.affectsOutput)
        #expect(road.displayText
                == "◆ Which roads should the ground be levelled for: + dirt tracks (default + service roads)")
        #expect(reply.customizations[1].displayText == "Colour harmonization: Off (default On)")
        #expect(reply.customizations[1].helpText == "color_harmonization")
    }

    @Test func noOverridesIsAnEmptyList() throws {
        let reply = try decode(#"{"lat": 45, "lon": 5, "customizations": []}"#)
        #expect(reply.customizations.isEmpty)
    }

    @Test func anEngineWithoutTheCommandThrows() {
        let reply = O4Reply(ok: false, result: nil, error: "unknown command")
        let result: Result<O4TileCustomizations, Error> =
            OrthoEngineClient.decodeReply(reply, command: "tile_customizations")
        #expect((try? result.get()) == nil)
    }
}
