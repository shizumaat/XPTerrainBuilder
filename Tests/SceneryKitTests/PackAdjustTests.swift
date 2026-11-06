import Testing
import Foundation
@testable import SceneryKit

/// An airport pack's adjustments as one question (capability
/// `pack_adjust`, issue #1916). The wire names are STRING LITERALS matched
/// against `Ortho4XP/src/o4_engine/events.py`; these tests are the drift
/// alarm.
struct PackAdjustTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackAdjust",
            "pack": "Some Pack", "pack_root": "/X/Custom Scenery/Some Pack",
            "lat": 29, "lon": -96, "state": "found", "error": "", "files": [],
            "items": [
                ["key": "trees", "count": 3, "uses": 9, "automatic": false],
                ["key": "drapes", "count": 12, "uses": 40, "automatic": false],
                ["key": "flatten", "count": 1, "uses": 0, "automatic": true],
            ],
        ]
    }

    @Test func decodesEveryRow() throws {
        guard case .packAdjust(let a)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.packRoot == "/X/Custom Scenery/Some Pack" && a.lat == 29 && a.lon == -96)
        #expect(a.choices.map(\.key) == ["trees", "drapes"])
        #expect(a.automatic.map(\.key) == ["flatten"])
        #expect(a.asks)
        #expect(a.titleText == "Adjust “Some Pack”?")
        #expect(a.choices[1].detail == "12 photo images (40 polygons) laid over "
                + "the airport cover the tile’s imagery.")
    }

    @Test func flattenAloneAsksNothing() {
        var event = fullEvent
        event["items"] = [["key": "flatten", "count": 1, "automatic": true]]
        guard case .packAdjust(let a)? = O4Event.parse(object: event) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(!a.asks)
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .packAdjust(let a)? = O4Event.parse(object: ["event": "PackAdjust"]) else {
            Issue.record("PackAdjust did not decode")
            return
        }
        #expect(a.items.isEmpty && !a.asks && a.state == "found")
    }
}
