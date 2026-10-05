import Foundation

/// THE ENGINE'S STDERR, PERSISTED — one file per build run.
///
/// The console pane was the only place a Python `RuntimeWarning` (shapely,
/// numpy) ever appeared, so a warning the owner saw in the app could not be
/// read back afterwards (2026-09-09).  Every stderr line also lands in
/// `~/Library/Logs/XPTerrainBuilder/engine-stderr.log`.
///
/// TWIN of the Qt app's `EngineStderrLog`
/// (`Ortho4XP/src/O4_Engine_Stderr_Log.py`, which writes
/// `<data root>/logs/engine-stderr.log`).  The two follow the same rules,
/// and a change to one is a change to both:
///
/// * `engine-stderr.log` holds the CURRENT build run only.  `startRun` —
///   called where the UI sends the build request that opens a run — shifts
///   the file to `engine-stderr.1.log` and starts a fresh one.  (2026-10-05:
///   the file used to append across app sessions for weeks, and errors from
///   an old build were read as current.)
/// * The previous runs are kept as `engine-stderr.1.log` (most recent) …
///   `engine-stderr.5.log`; each new run shifts them and drops the oldest.
/// * The fresh file opens with a run header: time, app version, engine
///   version and the tiles requested (`runHeader`).
/// * Lines written between runs (start-up, idle warnings) land in the
///   current file under a `=== engine session <time> ===` header — nothing
///   is lost.
/// * Inside a run the file is capped at 20 MB: past it, the files shift the
///   same way and the run continues in a fresh file under a continuation
///   header, so one runaway run cannot fill the disk.
/// * Nothing here throws or blocks the UI: a file that cannot be shifted or
///   opened disables persistence until the next run; the console still gets
///   every line.
public final class EngineStderrLog: @unchecked Sendable {
    public static let shared = EngineStderrLog(
        directory: FileManager.default.urls(for: .libraryDirectory, in: .userDomainMask)[0]
            .appendingPathComponent("Logs/XPTerrainBuilder", isDirectory: true))

    static let maxBytes = 20 * 1024 * 1024
    static let keptRuns = 5

    private let lock = NSLock()
    private var handle: FileHandle?
    private var failed = false
    private var pendingHeader: String?
    private let directory: URL
    private let url: URL
    private let maxBytes: Int
    private let keptRuns: Int

    init(directory: URL, maxBytes: Int = EngineStderrLog.maxBytes,
         keptRuns: Int = EngineStderrLog.keptRuns) {
        self.directory = directory
        self.url = directory.appendingPathComponent("engine-stderr.log")
        self.maxBytes = maxBytes
        self.keptRuns = keptRuns
    }

    // MARK: - The run boundary

    /// Shift the previous runs and open a fresh file for this one.
    public func startRun(appVersion: String, engineVersion: String, tiles: [String]) {
        let header = Self.runHeader(appVersion: appVersion, engineVersion: engineVersion,
                                    tiles: tiles)
        lock.lock(); defer { lock.unlock() }
        close()
        failed = !shift()
        pendingHeader = header
        open()
    }

    /// One line of engine stderr (or a note of the app's own).
    public func append(_ line: String) {
        lock.lock(); defer { lock.unlock() }
        open()
        guard let h = handle, let data = (line + "\n").data(using: .utf8) else { return }
        do {
            try h.write(contentsOf: data)
            guard try h.offset() > UInt64(maxBytes) else { return }
        } catch {
            close(); failed = true
            return
        }
        close()
        failed = !shift()
        pendingHeader = "=== engine run continued \(Self.stamp()) === the "
            + "\(maxBytes / (1024 * 1024)) MB size guard moved the earlier part to "
            + numbered(1).lastPathComponent
    }

    /// The first line of a run's file (same text as the Qt app's).
    static func runHeader(appVersion: String, engineVersion: String, tiles: [String],
                          stamp: String? = nil) -> String {
        "=== engine run \(stamp ?? Self.stamp()) === app \(appVersion.isEmpty ? "unknown" : appVersion)"
            + " | engine \(engineVersion.isEmpty ? "unknown" : engineVersion)"
            + " | \(tilesText(tiles))"
    }

    /// Tiles added to the run in progress: a line, not a new file.
    public static func queuedLine(tiles: [String], stamp: String? = nil) -> String {
        "=== queued into this run \(stamp ?? Self.stamp()) === \(tilesText(tiles))"
    }

    private static func tilesText(_ tiles: [String]) -> String {
        "\(tiles.count) tile\(tiles.count == 1 ? "" : "s"): \(tiles.joined(separator: " "))"
    }

    private static func stamp() -> String {
        ISO8601DateFormatter().string(from: Date())
    }

    // MARK: - File plumbing (never throws)

    private func numbered(_ index: Int) -> URL {
        directory.appendingPathComponent("engine-stderr.\(index).log")
    }

    /// live → .1, .1 → .2 …, the oldest dropped.  False on failure.
    private func shift() -> Bool {
        let fm = FileManager.default
        guard fm.fileExists(atPath: url.path) else { return true }
        do {
            if fm.fileExists(atPath: numbered(keptRuns).path) {
                try fm.removeItem(at: numbered(keptRuns))
            }
            for index in stride(from: keptRuns - 1, through: 1, by: -1)
            where fm.fileExists(atPath: numbered(index).path) {
                try fm.moveItem(at: numbered(index), to: numbered(index + 1))
            }
            try fm.moveItem(at: url, to: numbered(1))
            return true
        } catch {
            return false
        }
    }

    private func close() {
        try? handle?.close()
        handle = nil
    }

    private func open() {
        guard handle == nil, !failed else { return }
        let fm = FileManager.default
        do {
            try fm.createDirectory(at: directory, withIntermediateDirectories: true)
            if !fm.fileExists(atPath: url.path) {
                fm.createFile(atPath: url.path, contents: nil)
            }
            let h = try FileHandle(forWritingTo: url)
            try h.seekToEnd()
            let header = pendingHeader ?? "=== engine session \(Self.stamp()) ==="
            pendingHeader = nil
            try h.write(contentsOf: Data((header + "\n").utf8))
            handle = h
        } catch {
            close(); failed = true
        }
    }
}
