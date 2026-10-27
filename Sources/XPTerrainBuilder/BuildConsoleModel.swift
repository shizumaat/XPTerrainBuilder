import Foundation
import SceneryKit

/// The build console: engine output (stderr under the protocol transport),
/// append-heavy; a ~10 Hz generation bump tells the NSTextView to pull.
///
/// Every line knows its tile (#1226): the engine prefixes a tile's lines
/// with `[+47-123] ` (`TileBuildLogs.tileOfLine`), and the app's own tile
/// lines pass the tile. With tiles selected the console shows only their
/// lines plus run-level lines, and a selected tile with no lines in this
/// session shows its newest saved log (`BuildModel.syncConsoleView`).
/// TWIN of the Qt drawer's `ConsoleLines` (`O4_Qt_Build_History.py`).
@MainActor
final class BuildConsoleModel: ObservableObject {
    struct Line {
        let tile: String?
        let text: String
    }

    @Published private(set) var generation = 0
    private(set) var totalAppended = 0
    private(set) var clearCount = 0
    private(set) var entries: [Line] = []
    private var liveCounts: [String: Int] = [:]
    private var flushScheduled = false

    /// The tiles the console is filtered to; empty shows every line.
    private(set) var filter: Set<String> = []
    /// Saved-log lines shown above the live ones while filtered.
    private(set) var savedLines: [String] = []
    /// False while one saved log is shown alone (the Saved logs menu).
    private(set) var showsLive = true
    /// Bumped whenever the shown text must be rebuilt, not appended to.
    private(set) var viewGeneration = 0

    /// The ✕ on the filter chip: everything is shown until the selection
    /// changes again.
    @Published var filterDismissed = false
    /// A saved log picked from the menu: (tile key, log file name).
    @Published var chosenLog: (tile: String, log: String)?
    /// The Build History list beside the console.
    @Published var showHistory = false

    static let maxLines = 5000
    static let trimTo = 4000

    func append(_ line: String, tile: String? = nil) {
        let key = tile ?? TileBuildLogs.tileOfLine(line).tile
        entries.append(Line(tile: key, text: line))
        if let key { liveCounts[key, default: 0] += 1 }
        totalAppended += 1
        if entries.count > Self.maxLines {
            let drop = entries.count - Self.trimTo
            for line in entries.prefix(drop) {
                if let key = line.tile { liveCounts[key, default: 1] -= 1 }
            }
            entries.removeFirst(drop)
        }
        scheduleFlush()
    }

    /// Whether `tile` wrote lines this session that are still held.
    func hasLiveLines(_ tile: String) -> Bool { (liveCounts[tile] ?? 0) > 0 }

    /// Whether a held line is shown under the current filter.
    func shows(_ line: Line) -> Bool {
        guard showsLive else { return false }
        guard let tile = line.tile, !filter.isEmpty else { return true }
        return filter.contains(tile)
    }

    /// The whole shown text, for a rebuild.
    var visibleLines: [String] {
        savedLines + entries.filter(shows).map(\.text)
    }

    func setView(filter: Set<String>, saved: [String], live: Bool) {
        guard filter != self.filter || saved != savedLines || live != showsLive else { return }
        self.filter = filter
        savedLines = saved
        showsLive = live
        viewGeneration += 1
        generation += 1
    }

    /// Clears the view only: saved logs on disk are untouched.
    func clear() {
        entries = []
        liveCounts = [:]
        savedLines = []
        clearCount += 1
        generation += 1
    }

    private func scheduleFlush() {
        guard !flushScheduled else { return }
        flushScheduled = true
        Task { @MainActor [weak self] in
            try? await Task.sleep(for: .milliseconds(100))
            guard let self else { return }
            self.flushScheduled = false
            self.generation += 1
        }
    }
}
