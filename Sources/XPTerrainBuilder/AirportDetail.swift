import Foundation
import SceneryKit

/// The one Detail choice (issue #1985): where to add airport detail —
/// None, airports with ICAO codes (the default) or all airports. A choice
/// writes every per-airport key at once (sharper imagery, grading, the
/// best elevation, measured sea depth) and, for ICAO or All, ZL16 outside
/// the airports and ZL18 at them. Detail is not stored: Settings reads the
/// four airport features, each off or on for one choice, and shows the one
/// choice every feature that is on agrees on (None when all are off), else
/// Custom. Switching between ICAO and All re-scopes the features that are
/// on; choosing ICAO or All from None or Custom turns them all on.
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

    /// The airport features, each by its keys: sharper imagery, grading,
    /// high-resolution elevation, measured depth.
    static let features = [["cover_airports_with_highres"], ["auto_patch"], ["airport_elevation_insets"], ["bathymetry_near_icao_airports", "bathymetry_near_other_airports"]]

    static let choices: [AirportDetailChoice] = [
        AirportDetailChoice("none", "None",
                            scope: ["cover_airports_with_highres": "False", "auto_patch": "None", "airport_elevation_insets": "None", "bathymetry_near_icao_airports": "False", "bathymetry_near_other_airports": "False"]),
        AirportDetailChoice("icao", "ICAO airports",
                            scope: ["cover_airports_with_highres": "ICAO", "auto_patch": "ICAO", "airport_elevation_insets": "ICAO", "bathymetry_near_icao_airports": "True", "bathymetry_near_other_airports": "False"]),
        AirportDetailChoice("all", "All airports",
                            scope: ["cover_airports_with_highres": "True", "auto_patch": "All", "airport_elevation_insets": "All", "bathymetry_near_icao_airports": "True", "bathymetry_near_other_airports": "True"]),
    ]

    /// The Detail that feature `states` show (each a choice key, "none"
    /// for off, nil for neither), or nil: Custom (Qt: `from_states`).
    static func fromStates(_ states: [String?]) -> String? {
        if states.contains(where: { $0 == nil }) { return nil }
        let on = Set(states.compactMap { $0 }.filter { $0 != "none" })
        if on.isEmpty { return "none" }
        return on.count == 1 ? on.first : nil
    }

    /// Everything choosing `choice` writes, as a preset (so it goes
    /// through the preset's write paths), coming from the shown choice
    /// `current` (nil: Custom) with feature `states`. From None or Custom
    /// to ICAO or All: every scope key, the build zoom and the airport
    /// zoom. From ICAO or All: the keys of the features that are on,
    /// re-scoped (to None: every key off). Qt: `values` and `zoom`.
    static func writes(_ choice: AirportDetailChoice, from current: String?,
                       states: [String?]) -> SettingsPreset {
        var values = choice.scope
        if choice.key != "none", current != "icao", current != "all" {
            values[SettingsPresets.zoomKey] = String(outsideZL)
            values["cover_zl"] = String(airportZL)
        } else if choice.key != "none" {
            values = [:]
            for (keys, state) in zip(features, states) where state != nil && state != "none" {
                for name in keys { values[name] = choice.scope[name] }
            }
        }
        return SettingsPreset("detail_" + choice.key, choice.title,
                              summary: "", cost: "", values: values)
    }

    /// One feature in one choice's state, as a preset to match.
    static func feature(_ keys: [String], of choice: AirportDetailChoice) -> SettingsPreset {
        SettingsPreset("detail_" + choice.key, choice.title, summary: "", cost: "",
                       values: choice.scope.filter { keys.contains($0.key) })
    }
}

extension BuildModel {
    /// Each airport feature's state now (selection-aware like the preset
    /// cards, #1549): the choice its keys equal, "none" for off, or nil.
    func airportFeatureStates(followsSelection: Bool = true) -> [String?] {
        AirportDetail.features.map { keys in
            AirportDetail.choices.first {
                presetMatches(AirportDetail.feature(keys, of: $0),
                              followsSelection: followsSelection)
            }?.key
        }
    }

    /// The Detail choice shown now, or nil: Custom.
    func currentAirportDetail(followsSelection: Bool = true) -> AirportDetailChoice? {
        let key = AirportDetail.fromStates(airportFeatureStates(followsSelection: followsSelection))
        return AirportDetail.choices.first { $0.key == key }
    }

    /// Apply a Detail choice to the selected tiles, else to the defaults.
    func applyAirportDetail(_ choice: AirportDetailChoice, followsSelection: Bool = true) {
        let states = airportFeatureStates(followsSelection: followsSelection)
        let preset = AirportDetail.writes(choice, from: AirportDetail.fromStates(states),
                                          states: states)
        applyPreset(preset, followsSelection: followsSelection)
    }
}
