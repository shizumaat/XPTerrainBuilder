import Testing
import Foundation
import SceneryKit
@testable import XPTerrainBuilder

/// #2137: which shapes the map draws as sloping rectangles, and the
/// inspector's field title per whole-shape form.
struct PatchSlopeShapeTests {
    static func document() throws -> PatchDocument {
        let load: [String: Any] = [
            "icao": "ZZZZ", "source": "auto", "path": "/tmp/ZZZZ_auto.patch.osm", "stale": false,
            "stale_inputs": [], "min_distinct_spacing_m": 0.5, "identity_dp": 11, "header": [:],
            "nodes": [[-1, 30.0, 31.0, NSNull()], [-2, 30.0007, 31.0, NSNull()], [-3, 30.0007, 31.0001, NSNull()],
                      [-4, 30.0, 31.0001, NSNull()]],
            "ways": [
                ["id": -10, "refs": [-1, -2, -3, -4, -1], "tags": ["altitude_high": "172.4", "altitude_low": "x"]],
                ["id": -11, "refs": [-1, -2, -3, -1], "tags": ["altitude_high": "1", "altitude_low": "0"]],
                ["id": -12, "refs": [-1, -2, -3, -4, -1], "tags": ["cst_alt_abs": "80"]],
            ],
        ]
        let data = try JSONSerialization.data(withJSONObject: load)
        return PatchDocument(tile: "+30+031", load: try JSONDecoder().decode(O4PatchLoad.self, from: data))
    }

    @Test func onlyValidSlopesAreDrawn() throws {
        let slopes = PatchSlopeShape.all(in: try Self.document())
        #expect(slopes.map(\.wayID) == [-10])
        #expect(slopes.first?.high == 172.4)
        #expect(slopes.first?.low == nil)
        #expect(PatchShapeAltitude.label(.low, slopes.first?.low) == "Low: mesh")
        let marks = try #require(slopes.first?.marks)
        #expect(marks.highLabel.lat < marks.lowLabel.lat) // refs[3]–[0] is the south edge
    }

    @Test func fieldTitlesNameTheForm() {
        #expect(PatchShapeAltitudeBox.title(.absolute) == PatchShapeAltitudeBox.levelTitle)
        #expect(PatchShapeAltitudeBox.title(.meanOffset) == PatchShapeAltitudeBox.meanOffsetTitle)
        #expect(PatchShapeAltitudeBox.title(.groundOffset) == PatchShapeAltitudeBox.groundOffsetTitle)
    }
}
