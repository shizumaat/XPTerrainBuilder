import Testing
import Foundation
@testable import SceneryKit

/// Two installed packs drawing the same large structures (capability
/// `pack_overlaps`, issue #2145). The wire names are STRING LITERALS matched
/// against `Ortho4XP/src/o4_engine/events.py`; these tests are the drift
/// alarm.
struct PackOverlapsTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackOverlaps",
            "lat": 25, "lon": 55, "state": "found", "error": "", "files": [],
            "items": [
                ["key": "/CS/Autogen | Airport", "packs": ["Autogen", "Airport"],
                 "airport": "Airport", "default": "Airport", "winner": "",
                 "count": 7, "rows": [5, 3], "summary": "Autogen and Airport both draw 7"],
            ],
        ]
    }

    @Test func decodesAPairAndPreselectsTheAirportPack() {
        guard case .packOverlaps(let o)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackOverlaps did not decode")
            return
        }
        #expect(o.lat == 25 && o.lon == 55 && o.asks)
        let pair = o.offers[0]
        #expect(pair.packs == ["Autogen", "Airport"] && pair.count == 7 && pair.rows == [5, 3])
        #expect(pair.preselected == "Airport")
        #expect(pair.choices.map(\.label) == ["Keep Autogen", "Keep Airport", "Keep both"])
        #expect(pair.choices.map(\.winner) == ["Autogen", "Airport", "both"])
    }

    /// RULINGS 17o: between two non-airport packs the engine's default is the
    /// one higher in scenery_packs.ini, not the first alphabetically.
    @Test func preselectsTheEnginesIniOrderDefault() {
        var event = fullEvent
        var row = (event["items"] as! [[String: Any]])[0]
        row["packs"] = ["Alpha City", "Zeta City"]
        row["default"] = "Zeta City"
        event["items"] = [row]
        guard case .packOverlaps(let o)? = O4Event.parse(object: event) else {
            Issue.record("PackOverlaps did not decode")
            return
        }
        #expect(o.offers[0].preselected == "Zeta City")
    }

    @Test func aRememberedAnswerWins() {
        var event = fullEvent
        var row = (event["items"] as! [[String: Any]])[0]
        row["winner"] = "both"
        event["items"] = [row]
        guard case .packOverlaps(let o)? = O4Event.parse(object: event) else {
            Issue.record("PackOverlaps did not decode")
            return
        }
        #expect(o.offers[0].preselected == "both")
    }

    @Test func anOutcomeAsksNothing() {
        var event = fullEvent
        event["state"] = "chosen"
        guard case .packOverlaps(let o)? = O4Event.parse(object: event) else {
            Issue.record("PackOverlaps did not decode")
            return
        }
        #expect(!o.asks)
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .packOverlaps(let o)? = O4Event.parse(object: ["event": "PackOverlaps"]) else {
            Issue.record("PackOverlaps did not decode")
            return
        }
        #expect(o.items.isEmpty && !o.asks && o.state == "found")
    }
}
