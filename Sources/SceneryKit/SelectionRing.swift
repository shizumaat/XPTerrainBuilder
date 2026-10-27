import Foundation

/// Which Activity rows draw the map's selection ring (issue #1537).
///
/// A row rings when its tile is in the map selection, so the list shows
/// which of its tiles the selection holds. When the selection holds every
/// row's tile (or none of them) nothing rings: a list lit up wholesale
/// tells the user nothing. The active tile's row takes the map's solid
/// ring, every other ringed row the map's dashed one.
///
/// Twin: `Ortho4XP/src/O4_Qt_Selection_Ring.py` (`ringed_rows`); both
/// read `Ortho4XP/tests/fixtures/selection_ring_cases.json`.
public enum SelectionRing {
    /// The map's two ring styles: solid with a glow, and dashed.
    public enum Mode: String, Sendable {
        case active, other
    }

    /// The ring each row draws, keyed by the rows that draw one.
    public static func rings<Key: Hashable>(
        rows: [Key], selected: Set<Key>, active: Key?
    ) -> [Key: Mode] {
        let all = Set(rows)
        let hit = all.intersection(selected)
        guard !hit.isEmpty, hit != all else { return [:] }
        var out: [Key: Mode] = [:]
        for key in hit {
            out[key] = key == active ? .active : .other
        }
        return out
    }
}
