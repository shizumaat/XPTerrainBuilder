import Testing
@testable import XPTerrainBuilder
@testable import SceneryKit

/// #1985: the airport Detail choice. Its table is parity-tested against the
/// engine by Ortho4XP/tests/test_airport_detail.py; these check the Mac
/// side's use of it.
struct AirportDetailTests {
    @Test func icaoAndAllSetTheZooms() {
        for choice in AirportDetail.choices {
            let writes = AirportDetail.writes(choice).values
            for name in AirportDetail.scopeKeys {
                #expect(writes[name] == choice.scope[name])
            }
            if choice.key == "none" {
                #expect(writes[SettingsPresets.zoomKey] == nil)
                #expect(writes["cover_zl"] == nil)
            } else {
                #expect(writes[SettingsPresets.zoomKey] == "16")
                #expect(writes["cover_zl"] == "18")
            }
            // Recognised by its scope keys only: the zooms stay free.
            #expect(AirportDetail.recognisedBy(choice).values == choice.scope)
        }
    }

    @Test func everyScopeKeyFollowsTheSelection() {
        for name in AirportDetail.scopeKeys {
            #expect(BuildModel.tileScopeNames.contains(name))
        }
    }

    @Test func eachPresetCarriesItsDetail() {
        let expected = ["light_on_disk": "none", "balanced": "none",
                        "sharper_airports": "icao"]
        for preset in SettingsPresets.presets {
            let choice = AirportDetail.choices.first { $0.key == expected[preset.key] }
            #expect(choice != nil)
            for (name, value) in choice?.scope ?? [:] {
                #expect(preset.values[name] == value)
            }
        }
    }
}
