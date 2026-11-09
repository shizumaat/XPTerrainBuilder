import Testing
@testable import XPTerrainBuilder
@testable import SceneryKit

/// #1985: the airport Detail choice. Its table is parity-tested against the
/// engine by Ortho4XP/tests/test_airport_detail.py; these check the Mac
/// side's use of it.
struct AirportDetailTests {
    @Test func fromNoneOrCustomEverythingTurnsOnWithTheZooms() {
        for choice in AirportDetail.choices {
            for current in [nil, "none"] as [String?] {
                let writes = AirportDetail.writes(choice, from: current, states: []).values
                for name in AirportDetail.scopeKeys {
                    #expect(writes[name] == choice.scope[name])
                }
                let zooms = choice.key == "none" ? nil : "16"
                #expect(writes[SettingsPresets.zoomKey] == zooms)
                #expect(writes["cover_zl"] == (choice.key == "none" ? nil : "18"))
            }
        }
    }

    @Test func switchingScopeKeepsOffFeaturesOff() {
        // Balanced (owner 2026-11-09T17:01Z): ICAO with the imagery off.
        let states: [String?] = ["none", "icao", "icao", "icao"]
        #expect(AirportDetail.fromStates(states) == "icao")
        let all = AirportDetail.choices[2]
        let writes = AirportDetail.writes(all, from: "icao", states: states).values
        #expect(writes["cover_airports_with_highres"] == nil)
        #expect(writes["auto_patch"] == "All")
        #expect(writes["bathymetry_near_other_airports"] == "True")
        #expect(writes[SettingsPresets.zoomKey] == nil)
        #expect(AirportDetail.fromStates(["icao", "all", "icao", "icao"]) == nil)
        #expect(AirportDetail.fromStates(["none", "none", "none", "none"]) == "none")
        #expect(AirportDetail.fromStates(["icao", nil, "icao", "icao"]) == nil)
    }

    @Test func everyScopeKeyFollowsTheSelection() {
        for name in AirportDetail.scopeKeys {
            #expect(BuildModel.tileScopeNames.contains(name))
        }
    }

    @Test func everyPresetIsDetailICAO() {
        let icao = AirportDetail.choices[1]
        for preset in SettingsPresets.presets {
            let states: [String?] = AirportDetail.features.map { keys in
                AirportDetail.choices.first { choice in
                    keys.allSatisfy { preset.values[$0] == choice.scope[$0] }
                }?.key
            }
            #expect(AirportDetail.fromStates(states) == icao.key)
        }
    }
}
