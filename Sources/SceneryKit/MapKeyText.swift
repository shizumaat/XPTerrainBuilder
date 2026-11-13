import Foundation

/// The map's ONE key in both views and both apps (owner
/// 2026-11-12T22:05Z): a pill at the map's bottom-right, under the ZL
/// pill, its items in a row — a swatch and a short word each, truncated
/// with "…" when the row runs out of room, the full sentence on hover. The
/// Build view lists the kinds on the map now, the Fly view its corridor's
/// keys; both in this one order, each item in one colour wherever it
/// shows. Python: `O4_Map_Key_Text` (`tests/test_map_key.py` twins them).
public enum MapKeyText {
    /// (item, short word, the hover's sentence), in the key's order.
    public static let items: [(String, String, String)] = [
        ("full", "Full", O4WorldStateText.legendFull),
        ("mesh", "Mesh", O4WorldStateText.legendMesh),
        ("drape", "Drape", O4WorldStateText.legendDrape),
        ("placeholder", "Placeholder", O4WorldStateText.legendPlaceholder),
        ("other_tool", "Other tool", O4WorldStateText.legendOtherTool),
        ("meshing", "Meshing", "Mesh being built"),
        ("draping", "Draping", "Photo being draped (dashed)"),
        ("route", "On route", "On the route, not built yet"),
        ("built", "Built here", "A tile XPTerrainBuilder built"),
        ("other", "Other ortho", "Ortho another tool built"),
        ("stale", "Pack changed", "Airport pack changed since the build (dashed)"),
        ("external", "Other drive", "Built on another drive"),
        ("custom", "Patch", O4WorldStateText.legendCustomPatch),
        ("sharp", "Full detail", "Full-detail photo (live flight preview)"),
    ]
    public static let short: [String: String] =
        Dictionary(uniqueKeysWithValues: items.map { ($0.0, $0.1) })
    public static let full: [String: String] =
        Dictionary(uniqueKeysWithValues: items.map { ($0.0, $0.2) })

    /// The Fly view's cell keys (`FlyText.legend`) -> their item.
    public static let flyKeyItems: [String: String] = [
        "draping": "draping", "meshing": "meshing", "draped": "drape",
        "built": "full", "mesh": "mesh", "placeholder": "placeholder",
        "own": "route", "custom": "custom", "sharp": "sharp",
    ]
    /// The pill is at most this fraction of the map's width.
    public static let maxWidthFraction: Double = 0.7

    /// `wanted` once each, in the key's order.
    public static func ordered(_ wanted: Set<String>) -> [String] {
        items.map(\.0).filter { wanted.contains($0) }
    }
}
