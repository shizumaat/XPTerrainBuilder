import Foundation

/// First-visit guidance on the map and the empty states (issue #828): the
/// Swift half of ONE rule and one set of words whose Python half is
/// `Ortho4XP/src/O4_Map_Guidance.py`. Both read
/// `Ortho4XP/tests/fixtures/map_guidance_cases.json`.
///
/// The hint shows until DISMISSED, and stays dismissed across launches:
/// the first selection dismisses it, so does its close button, and
/// Help ▸ Show Tips brings it back (until the next selection or close).
public enum MapGuidance {
    public static let hintText = "Search your airport, or click its square on the map. Drag to move the map."
    public static let showTipsTitle = "Show Tips"
    public static let emptySelectionText =
        "Nothing is selected yet. A tile is one 1° × 1° square of the map. "
        + "Building it downloads imagery and elevation for that square and "
        + "fits the runways, taxiways and aprons of every airport in it to "
        + "the terrain."
    public static let nothingBuiltText =
        "No tiles built yet. Search your airport or click its square, then press Build."
    /// The UserDefaults key (the Qt prefs key is the same string).
    public static let hintDismissedKey = "map_hint_dismissed"

    public enum Event: String, Sendable {
        case selected, deselected, closed
        case showTips = "show_tips"
    }

    /// The hint's dismissed state after `event`.
    public static func dismissed(after event: Event, from dismissed: Bool) -> Bool {
        switch event {
        case .selected, .closed: return true
        case .showTips: return false
        case .deselected: return dismissed
        }
    }
}
