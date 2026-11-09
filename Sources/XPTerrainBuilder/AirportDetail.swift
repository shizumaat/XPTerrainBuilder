import Foundation
import SceneryKit

/// The one Detail choice (issue #1985): where to add airport detail —
/// None, airports with ICAO codes (the default) or all airports. A choice
/// writes every per-airport key at once (sharper imagery, grading, the
/// best elevation, measured sea depth) and, for ICAO or All, ZL16 outside
/// the airports and ZL18 at them. Detail is not stored: Settings shows the
/// choice whose keys all hold, else Custom.
///
/// Mirror of the engine's `Ortho4XP/src/O4_Airport_Detail.py`, row for
/// row; `Ortho4XP/tests/test_airport_detail.py` parses this file and fails
/// when the two differ.
struct AirportDetailChoice: Identifiable, Equatable {
    let key: String
    let title: String
    /// The scope keys → cfg literal, in `AirportDetail.scopeKeys` order.
    let scope: [String: String]
    var id: String { key }

    init(_ key: String, _ title: String, scope: [String: String]) {
        self.key = key
        self.title = title
        self.scope = scope
    }
}

enum AirportDetail {
    static let title = "Detail"
    static let summary = "Where to add sharper imagery, graded runways and taxiways, the best elevation and measured sea depth."
    static let customTitle = "Custom"
    static let defaultKey = "icao"
    static let outsideZL = 16
    static let airportZL = 18

    static let scopeKeys = ["cover_airports_with_highres", "auto_patch", "airport_elevation_insets", "bathymetry_near_icao_airports", "bathymetry_near_other_airports"]

    static let choices: [AirportDetailChoice] = [
        AirportDetailChoice("none", "None",
                            scope: ["cover_airports_with_highres": "False", "auto_patch": "None", "airport_elevation_insets": "None", "bathymetry_near_icao_airports": "False", "bathymetry_near_other_airports": "False"]),
        AirportDetailChoice("icao", "ICAO airports",
                            scope: ["cover_airports_with_highres": "ICAO", "auto_patch": "ICAO", "airport_elevation_insets": "ICAO", "bathymetry_near_icao_airports": "True", "bathymetry_near_other_airports": "False"]),
        AirportDetailChoice("all", "All airports",
                            scope: ["cover_airports_with_highres": "True", "auto_patch": "All", "airport_elevation_insets": "All", "bathymetry_near_icao_airports": "True", "bathymetry_near_other_airports": "True"]),
    ]

    /// Everything a choice writes, as a preset (so it goes through the
    /// preset's write paths): its scope keys, and for ICAO or All the
    /// build zoom and the airport zoom.
    static func writes(_ choice: AirportDetailChoice) -> SettingsPreset {
        var values = choice.scope
        if choice.key != "none" {
            values[SettingsPresets.zoomKey] = String(outsideZL)
            values["cover_zl"] = String(airportZL)
        }
        return SettingsPreset("detail_" + choice.key, choice.title,
                              summary: "", cost: "", values: values)
    }

    /// What a choice is recognised by: its scope keys only (the zooms
    /// stay free to change in Imagery).
    static func recognisedBy(_ choice: AirportDetailChoice) -> SettingsPreset {
        SettingsPreset("detail_" + choice.key, choice.title,
                       summary: "", cost: "", values: choice.scope)
    }
}

extension BuildModel {
    /// The Detail choice that holds now (selection-aware like the preset
    /// cards, #1549), or nil: Custom.
    func currentAirportDetail(followsSelection: Bool = true) -> AirportDetailChoice? {
        AirportDetail.choices.first {
            presetMatches(AirportDetail.recognisedBy($0), followsSelection: followsSelection)
        }
    }

    /// Apply a Detail choice to the selected tiles, else to the defaults.
    func applyAirportDetail(_ choice: AirportDetailChoice, followsSelection: Bool = true) {
        applyPreset(AirportDetail.writes(choice), followsSelection: followsSelection)
    }
}
