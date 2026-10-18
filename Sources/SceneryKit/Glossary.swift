import Foundation

/// The plain-language words the apps show a user (issue #831).
///
/// Mirror of the Qt app's `Ortho4XP/src/O4_Glossary.py` and of the user
/// docs' `docs/glossary.md`; `Ortho4XP/tests/test_glossary_parity.py`
/// parses this file and fails when the tables differ. Only DISPLAY text
/// lives here: wire values (`StepProgress.step_key`, its `label`) and the
/// engine's internal names stay as they are, and are mapped to these words
/// where they are shown (`stepDisplay`).
public enum O4Glossary {
    /// key -> the plain wording a primary label uses (owner's wording, #831).
    public static let terms: [String: String] = [
        "detail": "Detail",
        "scenery_file": "Scenery file",
        "imagery_and_scenery_file": "Imagery and scenery file",
        "shape_ground": "Shape the ground",
        "blend_water": "Blend coastlines and water",
        "map_data": "Download map data (roads, water, airports)",
        "grade_airports": "Grade airports to official standards (FAA / ICAO / EASA)",
        "fit_buildings": "Fit custom airport buildings to the new ground",
        "ground_shape": "Airport ground shape",
        "save_edits": "Save my edits",
        "undo_edits": "Undo my edits",
        "runway_data": "X-Plane's runway data",
        "xplane_objects": "Roads, forests and buildings from X-Plane",
        "airport_elevation": "High-resolution airport elevation",
        "elevation_source": "Elevation source",
        "bathymetry": "Underwater depth near the shore",
        "map_data_server": "Map data server",
        "surface_check": "Airport surface check: {n} spots outside the rules",
        "grading_airports": "Grading airports",
        "terrain_steps": "Map data, ground shape and water",
    ]

    /// Engine step key (wire `step_key`, legacy driver step) -> plain name.
    public static let stepNames: [String: String] = [
        "vector": "Download map data (roads, water, airports)",
        "mesh": "Shape the ground",
        "masks": "Blend coastlines and water",
        "imagery": "Imagery and scenery file",
        "dsf": "Imagery and scenery file",
        "overlays": "Roads, forests and buildings from X-Plane",
        "overlay": "Roads, forests and buildings from X-Plane",
    ]

    /// Imagery zoom level -> detail name.
    public static let detailNames: [Int: String] = [
        12: "Very coarse",
        13: "Coarse",
        14: "Low",
        15: "Light",
        16: "Standard",
        17: "Sharp",
        18: "Very sharp",
        19: "Ultra sharp",
        20: "Extreme",
        21: "Maximum",
    ]

    /// Imagery zoom level -> ground size of one pixel (equator, rounded).
    public static let detailPixelSizes: [Int: String] = [
        12: "~40 m",
        13: "~20 m",
        14: "~10 m",
        15: "~5 m",
        16: "~2 m",
        17: "~1 m",
        18: "~0.6 m",
        19: "~0.3 m",
        20: "~0.15 m",
        21: "~0.07 m",
    ]

    /// The plain wording for `key` (the key itself when unknown).
    public static func term(_ key: String) -> String {
        terms[key] ?? key
    }

    /// "Standard (~2 m per pixel)" for ZL16; "ZL<n>" off the table.
    public static func detailLabel(_ zl: Int) -> String {
        guard let name = detailNames[zl], let size = detailPixelSizes[zl] else {
            return "ZL\(zl)"
        }
        return "\(name) (\(size) per pixel)"
    }

    /// A detail menu item: the plain label, ZL as secondary text.
    public static func detailChoice(_ zl: Int) -> String {
        "\(detailLabel(zl)) · ZL\(zl)"
    }

    /// The progress text shown for an engine `StepProgress`: the engine's
    /// `<step label>[ · <detail>]` with the step's name replaced by its
    /// plain name, and `auto-patch i/n[ · ICAO]` as "Grading airports".
    /// An unknown step key passes the label through.
    public static func stepDisplay(key: String, label: String) -> String {
        let autoPatch = "auto-patch"
        if label == autoPatch || label.hasPrefix(autoPatch + " ") {
            return term("grading_airports") + String(label.dropFirst(autoPatch.count))
        }
        guard let name = stepNames[key] else { return label }
        guard let range = label.range(of: " · ") else { return name }
        return name + String(label[range.lowerBound...])
    }

    /// The one-line airport surface summary, when one is shown.
    public static func surfaceCheck(_ n: Int) -> String {
        term("surface_check").replacingOccurrences(of: "{n}", with: "\(n)")
    }
}
