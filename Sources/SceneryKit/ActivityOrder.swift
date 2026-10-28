import Foundation

/// The Activity list's row order and status tone (issue #1341), which
/// section a row sits in (#1556), and how the list's native selection and
/// the map's tile selection stay one selection (#1537).
///
/// Finished rows (done, built with warnings, failed, stopped) stay in the
/// list until the app quits. Live rows (queued, running) sit on top in the
/// order they were queued (#1605): the first tile queued at the top, later
/// tiles added below, a running tile staying where it is; finished rows
/// follow in the order they finished, the first finished directly under
/// the live block (newest at the bottom).
///
/// Each row carries a `Stamp`: the counter value of the batch that queued
/// it, and of the moment it finished (nil while it is live). `restamp`
/// advances the stamps from the rows' current states; `order` reads the
/// order off them. A finished row queued again is live once more and gets
/// a fresh queued stamp, so it joins the bottom of the live block.
///
/// Twin: `Ortho4XP/src/O4_Activity_Order.py`; both read
/// `Ortho4XP/tests/fixtures/activity_order_cases.json`.
public enum ActivityOrder {
    public struct Stamp: Sendable, Equatable {
        public var queued: Int
        public var finished: Int?

        public init(queued: Int, finished: Int? = nil) {
            self.queued = queued
            self.finished = finished
        }
    }

    /// The status text's colour role.
    public enum Tone: String, Sendable {
        case live, done, warning, failed, stopped
    }

    /// A row whose tile has left the run: done, failed, stopped here, or
    /// drained by the engine (state `queued`, label `stopped`).
    public static func isFinished(state: String, label: String) -> Bool {
        ["done", "error", "stopped"].contains(state) || label == "stopped"
    }

    /// The pane section a row sits in (#1556): a built tile (`done`, with
    /// or without warnings) leaves Activity for Completed, where its row
    /// is compact (#1542) — title, then status and elapsed time, no bar,
    /// no steps. Failed, stopped and live rows stay in Activity; a
    /// completed tile queued again is live, so it moves back.
    public enum Section: String, Sendable {
        case activity, completed
    }

    public static func section(state: String) -> Section {
        state == "done" ? .completed : .activity
    }

    /// The rows the list shows selected (#1537, RULINGS 2026-10-28n):
    /// every row whose tile is in the map selection. `rows` is every row
    /// of both sections.
    public static func shownSelected<Key: Hashable>(rows: [Key], selected: Set<Key>) -> Set<Key> {
        Set(rows).intersection(selected)
    }

    /// The map selection after the user changed the list's own selection
    /// (#1537). `new` is the list's selection now, `shown` what it showed
    /// before. The list's selection becomes the map selection; the one row
    /// the edit added becomes the active tile, else the active tile stays
    /// if it is still selected, else the first. `frame`: the edit left one
    /// row selected — a click on a row — which frames its tile (#816).
    public static func listEdit<Key: Hashable & Comparable>(
        new: Set<Key>, shown: Set<Key>, active: Key?
    ) -> (selected: Set<Key>, active: Key?, frame: Bool) {
        let added = new.subtracting(shown)
        var active = active
        if added.count == 1 {
            active = added.first
        } else if let current = active, new.contains(current) {
            active = current
        } else {
            active = new.min()
        }
        return (new, active, new.count == 1)
    }

    public static func tone(state: String, label: String, hasIssues: Bool) -> Tone {
        switch state {
        case "error": return .failed
        case "done": return hasIssues ? .warning : .done
        case "stopped": return .stopped
        default: return label == "stopped" ? .stopped : .live
        }
    }

    /// The stamps after the rows' current states. `rows` are in the order
    /// the rows were made; a key absent from them loses its stamp. Every
    /// row new to the stamps, or live again after finishing, takes ONE
    /// shared queued value (a batch keeps its own order); each row that
    /// has just finished takes its own finished value, in `rows` order.
    public static func restamp<Key: Hashable>(
        _ rows: [(key: Key, finished: Bool)], stamps: [Key: Stamp], counter: Int
    ) -> (stamps: [Key: Stamp], counter: Int) {
        var out: [Key: Stamp] = [:]
        var counter = counter
        var batch: Int?
        for (key, finished) in rows {
            var stamp: Stamp
            if let old = stamps[key], !(old.finished != nil && !finished) {
                stamp = old
            } else {
                if batch == nil {
                    counter += 1
                    batch = counter
                }
                stamp = Stamp(queued: batch ?? counter)
            }
            if finished && stamp.finished == nil {
                counter += 1
                stamp.finished = counter
            }
            out[key] = stamp
        }
        return (out, counter)
    }

    /// `keys` (in the order the rows were made) as the list shows them:
    /// live rows first-queued batch first, then finished rows in finish order.
    public static func order<Key: Hashable>(_ keys: [Key], stamps: [Key: Stamp]) -> [Key] {
        let indexed = Array(keys.enumerated())
        let live = indexed.filter { stamps[$0.element]?.finished == nil }
            .sorted {
                let (a, b) = (stamps[$0.element]?.queued ?? 0, stamps[$1.element]?.queued ?? 0)
                return a != b ? a < b : $0.offset < $1.offset
            }
        let done = indexed.filter { stamps[$0.element]?.finished != nil }
            .sorted {
                let (a, b) = (stamps[$0.element]?.finished ?? 0, stamps[$1.element]?.finished ?? 0)
                return a != b ? a < b : $0.offset < $1.offset
            }
        return (live + done).map(\.element)
    }
}
