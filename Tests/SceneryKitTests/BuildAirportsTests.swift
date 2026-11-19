import Testing
import Foundation
@testable import SceneryKit

/// The Build pane's Airports card (protocol 1.17, #818).
///
/// The wire names here are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` (`class BuildAirportsReady`) and its
/// field names; they never appear in Python source, so these tests are the
/// drift alarm.
struct BuildAirportsTests {

    @Test func decodesTheCard() throws {
        let event = O4JSON.from([
            "event": "BuildAirportsReady",
            "request": 4,
            "airports": [
                ["icao": "KSEA", "name": "Seattle-Tacoma Intl", "ruleset": "FAA",
                 "tile": [47, -123], "estimate_s": [120.0, 300.0]],
                ["icao": "CYVR", "name": "", "ruleset": "ICAO",
                 "tile": [49, -124], "estimate_s": [60, 90]],
            ],
            "packs": [
                ["name": "KSEA Demo", "path": "/CS/KSEA Demo",
                 "airports": ["KSEA"], "objects": 1204],
            ],
            "total_s": [180.0, 390.0],
            "error": "",
        ] as [String: Any])
        let card = try O4BuildAirports.decode(event).get()
        #expect(card.airports.map(\.icao) == ["KSEA", "CYVR"])
        #expect(card.airports[0].ruleset == "FAA")
        #expect(card.airports[0].tile == O4TileRef(lat: 47, lon: -123))
        #expect(card.airports[1].estimateSeconds == 60...90)
        #expect(card.packs.first?.objects == 1204)
        #expect(card.totalSeconds == 180...390)
    }

    /// RULINGS 2026-11-18l (#2172): the custom patches, the fit default
    /// and the engine's question; an older engine's card has none.
    @Test func decodesTheCustomPatchQuestion() throws {
        let event = O4JSON.from([
            "event": "BuildAirportsReady", "airports": [], "packs": [],
            "total_s": [0, 0], "custom_patches": ["KASE"],
            "fit_buildings": false,
            "fit_confirm": "Custom patches are installed for KASE. Continue?",
        ] as [String: Any])
        let card = try O4BuildAirports.decode(event).get()
        #expect(card.customPatches == ["KASE"])
        #expect(card.fitBuildings == false)
        #expect(card.fitConfirm.hasPrefix("Custom patches are installed for KASE"))
        let old = try O4BuildAirports.decode(O4JSON.from(
            ["event": "BuildAirportsReady"] as [String: Any])).get()
        #expect(old.fitBuildings == nil && old.fitConfirm.isEmpty)
    }

    @Test func anErrorIsAFailure() {
        let event = O4JSON.from(["event": "BuildAirportsReady", "error": "no CIFP"] as [String: Any])
        guard case .failure(let error) = O4BuildAirports.decode(event) else {
            Issue.record("expected a failure")
            return
        }
        #expect((error as? O4CommandError)?.message == "no CIFP")
    }

    @Test func protocolGate() {
        #expect(O4ProtocolVersion.supportsBuildAirports("1.18"))
        #expect(!O4ProtocolVersion.supportsBuildAirports("1.17"))
    }
}
