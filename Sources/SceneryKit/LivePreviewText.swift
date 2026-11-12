import Foundation

/// The live flight preview's own words and mark colors (#2001 follow-up,
/// owner 2026-11-12T19:28Z: the map shows exactly what X-Plane shows).
/// Mirror of the Qt app's `Ortho4XP/src/O4_Live_Preview_Text.py`;
/// `Ortho4XP/tests/test_live_preview.py` parses this file and fails when
/// the two differ.
///
/// Keys: `reload` — X-Plane still shows what was there before the file
/// changed (drawn hatched); `own` — X-Plane draws its own scenery, the
/// map's base imagery shows, marked (the Fly legend's `own`).
public enum LivePreviewText {
    /// Drawn on a stale square or tile large enough to hold it.
    public static let reloadLabel = "Reload scenery to see"
    /// Drawn on a tile where X-Plane draws its own scenery.
    public static var ownLabel: String { O4Glossary.term("xplane_own_scenery") }
    /// (key, words) for a legend row.
    public static var legend: [(String, String)] {
        [("reload", "X-Plane shows the earlier imagery until you reload scenery"),
         ("own", ownLabel)]
    }
    /// The marks' colors, RGB 0–255.
    public static let markColors: [String: (Int, Int, Int)] = [
        "reload": (255, 69, 58),
        "own": (140, 140, 140),
    ]
}
