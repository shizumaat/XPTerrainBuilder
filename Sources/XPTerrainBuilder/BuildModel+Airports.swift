import Foundation
import SceneryKit

/// The Build pane's Airports card (#818): the per-build "Grade airports"
/// and "Fit custom airport buildings" switches, and the engine's answer
/// to what they will do for the selected tiles (`build_airports`). The Qt
/// window's twin is `O4_Qt_Build_Airports.py`.
extension BuildModel {
    /// Settings' `auto_patch` default: on unless its mode is "None".
    var gradeAirportsByDefault: Bool {
        guard let value = configValue(for: "auto_patch") else { return true }
        if let flag = value.boolValue { return flag }
        let literal = value.cfgLiteral
        return (O4LegacyModes.mappedLiteral(literal, forKey: "auto_patch") ?? literal) != "None"
    }

    /// What the next press grades: this build's switch, else Settings'.
    var gradeAirports: Bool { gradeAirportsThisBuild ?? gradeAirportsByDefault }

    /// What the next press fits: this build's switch, else Settings'.
    var fitBuildings: Bool { fitBuildingsThisBuild ?? modifyCustomAirports }

    /// A switch back at its Settings value is no override at all.
    func setGradeAirports(_ enabled: Bool) {
        gradeAirportsThisBuild = enabled == gradeAirportsByDefault ? nil : enabled
    }

    func setFitBuildings(_ enabled: Bool) {
        fitBuildingsThisBuild = enabled == modifyCustomAirports ? nil : enabled
    }

    /// The press's `overrides` (engine keys), and the switches reset to
    /// Settings: they change one build, never the next.
    func takeBuildOverrides() -> [String: Bool] {
        var overrides: [String: Bool] = [:]
        if let grade = gradeAirportsThisBuild { overrides["auto_patch"] = grade }
        if let fit = fitBuildingsThisBuild { overrides["modify_custom_airports"] = fit }
        gradeAirportsThisBuild = nil
        fitBuildingsThisBuild = nil
        return overrides
    }

    /// The engine's card for `tiles`; nil when the engine predates it.
    func buildAirportsCard(for tiles: [TileCoord]) async -> Result<O4BuildAirports, Error>? {
        guard !tiles.isEmpty, let client = buildAirportsClient() else { return nil }
        let refs = tiles.sorted().map { O4TileRef(lat: $0.lat, lon: $0.lon) }
        let folder = engineCustomBuildDir
        do {
            return .success(try await client.buildAirports(tiles: refs, customBuildDir: folder))
        } catch {
            return .failure(error)
        }
    }

    /// "about 2–5 min": whole minutes, at least one, never one number
    /// pretending to precision.
    nonisolated static func minutesText(_ seconds: ClosedRange<Double>) -> String {
        let low = max(1, Int((seconds.lowerBound / 60).rounded()))
        let high = max(low, Int((seconds.upperBound / 60).rounded()))
        return low == high ? "about \(low) min" : "about \(low)–\(high) min"
    }
}
