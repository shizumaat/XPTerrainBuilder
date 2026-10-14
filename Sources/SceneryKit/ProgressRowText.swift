import Foundation

/// The three texts of one build-progress row (issue #694): the TITLE owns
/// the whole first line (tile coordinate plus the #667 search tag), the
/// gray STATUS sits left on the second line and the TIME right on it.
/// The Qt half is `MainWindow._add_progress_rows` in `O4_Qt_GUI.py`.
public struct ProgressRowText: Sendable, Equatable {
    public let title: String
    public let status: String
    /// Nil: nothing to show (a queued tile with no estimate yet).
    public let time: String?

    public init(tileKey: String, tag: String, status: String, clock: O4TileClock?) {
        self.title = tileKey + tag
        self.status = status
        self.time = Self.tileClockText(clock)
    }

    /// `m:ss`, or `h:mm:ss` from an hour on.
    public static func clock(_ seconds: Double) -> String {
        let total = Int(seconds.rounded())
        if total >= 3600 {
            return String(format: "%d:%02d:%02d", total / 3600, (total % 3600) / 60, total % 60)
        }
        return String(format: "%d:%02d", total / 60, total % 60)
    }

    /// One row's clock text from its TileClocks entry (protocol 1.3).
    /// Finished: the frozen final elapsed alone.  Active: "elapsed · ~remaining"
    /// (the estimate is the tile's OWN outstanding work; a dash without a
    /// basis).  Queued: the bare "~estimate", or nothing at all — a row of
    /// dashes before anything starts is noise.
    public static func tileClockText(_ entry: O4TileClock?) -> String? {
        guard let entry else { return nil }
        if entry.finished { return clock(entry.elapsedSeconds) }
        if entry.elapsedSeconds > 0 {
            let remaining = entry.remainingSeconds.map { "~" + clock($0) } ?? "—"
            return "\(clock(entry.elapsedSeconds)) · \(remaining)"
        }
        if let remaining = entry.remainingSeconds { return "~" + clock(remaining) }
        return nil
    }
}
