import Testing
import Foundation
@testable import SceneryKit

/// Graded airports X-Plane flattens and Gateway packs with a newer version
/// (capability `gateway_airports`, issue #1989). The wire names are STRING
/// LITERALS matched against `Ortho4XP/src/o4_engine/events.py`; these
/// tests are the drift alarm.
struct GatewayAirportsTests {

    private var fullEvent: [String: Any] {
        [
            "event": "GatewayAirports",
            "lat": 44, "lon": -124, "state": "found", "error": "", "files": [],
            "items": [
                ["icao": "KEUG", "name": "Mahlon Sweet Fld", "reason": "flatten",
                 "installed_id": 0, "latest_id": 0, "pack": ""],
                ["icao": "KXXX", "name": "", "reason": "update",
                 "installed_id": 110181, "latest_id": 120000,
                 "pack": "KXXX Gateway Airport"],
            ],
        ]
    }

    @Test func decodesEveryRow() {
        guard case .gatewayAirports(let g)? = O4Event.parse(object: fullEvent) else {
            Issue.record("GatewayAirports did not decode")
            return
        }
        #expect(g.lat == 44 && g.lon == -124 && g.asks)
        #expect(g.offers.map(\.icao) == ["KEUG", "KXXX"])
        #expect(g.offers[0].title == "KEUG Mahlon Sweet Fld")
        #expect(g.offers[0].detail == "Install the latest Gateway version "
                + "without the flatten tag.")
        #expect(g.offers[1].title == "KXXX")
        #expect(g.offers[1].detail == "A newer Gateway version is available "
                + "(110181 → 120000); it installs without the flatten tag.")
    }

    @Test func anOutcomeAsksNothing() {
        var event = fullEvent
        event["state"] = "installed"
        event["items"] = [["icao": "KEUG", "reason": "installed"]]
        guard case .gatewayAirports(let g)? = O4Event.parse(object: event) else {
            Issue.record("GatewayAirports did not decode")
            return
        }
        #expect(!g.asks && g.offers.isEmpty)
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .gatewayAirports(let g)? = O4Event.parse(object: ["event": "GatewayAirports"]) else {
            Issue.record("GatewayAirports did not decode")
            return
        }
        #expect(g.items.isEmpty && !g.asks && g.state == "found")
    }
}
