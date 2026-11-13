import Foundation

/// The map's ONE key in both views and both apps (owner
/// 2026-11-12T22:05Z, #2031): a pill at the map's bottom-right, under the
/// ZL pill, its items in a row — a swatch and a short word each, truncated
/// with "…" when the row runs out of room, the full sentence on hover. The
/// Build view and the Fly view say the same eight items in the same words
/// and colours, in this one order; each lists only the items it shows
/// now. `items` is the ONE place the key is defined. A built tile is drawn
/// by its World state; the route is the magenta line, with no item; the
/// live preview's sharp squares are its "Sharp photo" toggle. Python:
/// `O4_Map_Key_Text` (`tests/test_map_key.py` twins them).
public enum MapKeyText {
    /// (item, short word, the hover's sentence), in the key's order.
    public static let items: [(String, String, String)] = [
        ("full", "Full", O4WorldStateText.legendFull),
        ("mesh", "Mesh only", O4WorldStateText.legendMesh),
        ("drape", "Drape", O4WorldStateText.legendDrape),
        ("placeholder", "Placeholder", O4WorldStateText.legendPlaceholder),
        ("building", "Building", "Building: a mesh or a drape under way (pulsing)"),
        ("other_tool", "Other tool", O4WorldStateText.legendOtherTool),
        ("stale", "Pack changed", "Airport pack changed since the build (dashed)"),
        ("custom", "Patch", O4WorldStateText.legendCustomPatch),
    ]
    public static let short: [String: String] =
        Dictionary(uniqueKeysWithValues: items.map { ($0.0, $0.1) })
    public static let full: [String: String] =
        Dictionary(uniqueKeysWithValues: items.map { ($0.0, $0.2) })

    /// The Fly view's cell keys (`FlyText.legend`) -> their item.
    public static let flyKeyItems: [String: String] = [
        "draping": "building", "meshing": "building", "draped": "drape",
        "built": "full", "mesh": "mesh", "placeholder": "placeholder",
        "custom": "custom",
    ]
    /// The pill is at most this fraction of the map's width.
    public static let maxWidthFraction: Double = 0.7
    /// "Building" pulses (#2031): its band's opacity runs from
    /// `buildingLowAlpha` to 1 and back once in this many seconds.
    public static let buildingPulseS: Double = 1.2
    public static let buildingLowAlpha: Double = 0.3

    /// The "Building" band's opacity at `seconds` (any clock; Python:
    /// `building_alpha`).
    public static func buildingAlpha(_ seconds: Double) -> Double {
        let wave = 0.5 + 0.5 * cos(2 * Double.pi * seconds / buildingPulseS)
        return buildingLowAlpha + (1 - buildingLowAlpha) * wave
    }

    /// `wanted` once each, in the key's order.
    public static func ordered(_ wanted: Set<String>) -> [String] {
        items.map(\.0).filter { wanted.contains($0) }
    }
}
