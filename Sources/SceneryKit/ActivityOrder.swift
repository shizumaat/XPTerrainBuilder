import Foundation

/// The Activity list's row order and status tone (issue #1341).
///
/// Finished rows (done, built with warnings, failed, stopped) stay in the
/// list until the app quits. Live rows (queued, running) sit on top, the
/// newest queued batch first; finished rows follow in the order they
/// finished, the first finished directly under the live block.
///
/// Each row carries a `Stamp`: the counter value of the batch that queued
/// it, and of the moment it finished (nil while it is live). `restamp`
/// advances the stamps from the rows' current states; `order` reads the
/// order off them. A finished row queued again is live once more and gets
/// a fresh queued stamp, so it returns to the top.
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
    /// live rows newest batch first, then finished rows in finish order.
    public static func order<Key: Hashable>(_ keys: [Key], stamps: [Key: Stamp]) -> [Key] {
        let indexed = Array(keys.enumerated())
        let live = indexed.filter { stamps[$0.element]?.finished == nil }
            .sorted {
                let (a, b) = (stamps[$0.element]?.queued ?? 0, stamps[$1.element]?.queued ?? 0)
                return a != b ? a > b : $0.offset < $1.offset
            }
        let done = indexed.filter { stamps[$0.element]?.finished != nil }
            .sorted {
                let (a, b) = (stamps[$0.element]?.finished ?? 0, stamps[$1.element]?.finished ?? 0)
                return a != b ? a < b : $0.offset < $1.offset
            }
        return (live + done).map(\.element)
    }
}
