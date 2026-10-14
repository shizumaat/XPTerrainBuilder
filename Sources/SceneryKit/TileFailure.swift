import Foundation

/// Why a tile was not built — or was built without one of its airport
/// patches — in the user's words (engine `BuildDone.failures` /
/// `BuildDone.warnings`, protocol 1.10; issue #562, owner RULINGS
/// 2026-10-12a / #564).
///
/// The TEXT is the engine's (`Ortho4XP/src/O4_Tile_Failures.py`): `what`
/// failed, `why`, and the `remedy`. This type only carries and lays it
/// out; the Qt window does the same in `O4_Qt_Tile_Failures.py`. `code` is
/// the stable failure class and `detail` the technical text (the original
/// exception or console line) — shown behind a disclosure, never as the
/// headline, and kept structured so a "report it" action can be added.
public struct O4TileFailure: Sendable, Equatable, Identifiable {
    public let code: String
    public let what: String
    public let why: String
    public let remedy: String
    /// The airports this one cause covers (identical causes are folded).
    public let airports: [String]
    public let detail: String
    /// The engine's own log file, named by a "report it" remedy.
    public let logPath: String
    /// The unreachable Custom Scenery link a tile's output sits behind
    /// (protocol 1.11, #668): non-empty only for `output_link_unmounted`,
    /// where the app offers to remove it.
    public let link: String

    public var id: String { code + "|" + what }

    public init(code: String, what: String, why: String, remedy: String,
                airports: [String] = [], detail: String = "", logPath: String = "",
                link: String = "") {
        self.link = link
        self.code = code
        self.what = what
        self.why = why
        self.remedy = remedy
        self.airports = airports
        self.detail = detail
        self.logPath = logPath
    }

    /// Decode a `failures` / `warnings` array. The JSON keys are STRING
    /// LITERALS matched against `O4_Tile_Failures._describe`; a missing
    /// array (an engine older than 1.10) and malformed entries decode to
    /// nothing.
    public static func parseList(_ value: Any?) -> [O4TileFailure] {
        (value as? [[String: Any]] ?? []).compactMap { entry in
            guard let what = entry["what"] as? String, !what.isEmpty else { return nil }
            return O4TileFailure(
                code: entry["code"] as? String ?? "",
                what: what,
                why: entry["why"] as? String ?? "",
                remedy: entry["remedy"] as? String ?? "",
                airports: (entry["airports"] as? [Any])?.compactMap { $0 as? String } ?? [],
                detail: entry["detail"] as? String ?? "",
                logPath: entry["log_path"] as? String ?? "",
                link: entry["link"] as? String ?? "")
        }
    }

    /// The entry as the engine sent it, to hand back to the
    /// `failure_report` command unchanged (#565).
    public var wireObject: [String: Any] {
        ["code": code, "what": what, "why": why, "remedy": remedy,
         "airports": airports, "detail": detail]
    }

    /// Whether the app may offer "Remove the link…" for this entry (#668).
    public var offersLinkRemoval: Bool {
        code == "output_link_unmounted" && !link.isEmpty
    }

    /// The three sentences, one per line.
    public var message: String { [what, why, remedy].joined(separator: "\n") }

    /// The console block: the three sentences, then the technical detail.
    public func consoleLines(isWarning: Bool, isNote: Bool = false) -> [String] {
        let lead = isNote ? "Note: " : (isWarning ? "Warning: " : "*** ")
        var lines = [lead + what, "    " + why, "    " + remedy]
        for line in detail.split(separator: "\n") {
            lines.append("      detail: " + line)
        }
        return lines
    }
}

/// One tile's messages at the end of its build.
public struct O4TileIssues: Sendable, Equatable {
    public let tileKey: String
    public let lat: Int
    public let lon: Int
    public let built: Bool
    public let failures: [O4TileFailure]
    public let warnings: [O4TileFailure]
    /// Info-level entries (stand-in elevation), shown under the warnings.
    public let notes: [O4TileFailure]

    public init(tileKey: String, lat: Int = 0, lon: Int = 0, built: Bool,
                failures: [O4TileFailure], warnings: [O4TileFailure],
                notes: [O4TileFailure] = []) {
        self.notes = notes
        self.tileKey = tileKey
        self.lat = lat
        self.lon = lon
        self.built = built
        self.failures = failures
        self.warnings = warnings
    }

    public var entries: [O4TileFailure] { failures + warnings + notes }

    /// The link to offer to remove — the tile was not built because its
    /// Custom Scenery folder is a link to a drive that is not mounted
    /// (#668) — or nil.
    public var removableLink: String? {
        built ? nil : failures.first(where: \.offersLinkRemoval)?.link
    }
}

/// The run's ONE report (a batch of twenty tiles must not raise twenty
/// sheets): every tile that was not built or was built with warnings.
public struct O4RunIssues: Sendable, Equatable, Identifiable {
    public let id: Int
    public let tiles: [O4TileIssues]

    public init?(id: Int, tiles: [O4TileIssues]) {
        let withIssues = tiles.filter { !$0.entries.isEmpty }
        guard !withIssues.isEmpty else { return nil }
        self.id = id
        self.tiles = withIssues
    }

    /// "1 tile was not built, 1 built with warnings" — the Qt box's title.
    public var title: String {
        let failed = tiles.filter { !$0.built }.count
        let warned = tiles.filter { $0.built }.count
        var parts: [String] = []
        if failed > 0 {
            parts.append("\(failed) tile\(failed == 1 ? " was" : "s were") not built")
        }
        if warned > 0 { parts.append("\(warned) built with warnings") }
        let text = parts.joined(separator: ", ")
        return text.prefix(1).uppercased() + text.dropFirst()
    }

    public var entries: [O4TileFailure] { tiles.flatMap(\.entries) }

    /// The technical detail of every message, for the disclosure and the
    /// pasteboard.
    public var detail: String {
        entries.filter { !$0.detail.isEmpty }
            .map { $0.what + "\n" + $0.detail }
            .joined(separator: "\n\n")
    }
}

/// The tiles of ONE run, collected as their `BuildDone` events arrive.
/// `begin()` at the run's start as well as `finish()` at its end: a run
/// that ends by engine death never reaches `RunDone`, and its entries
/// must not appear in the next run's report.
public struct O4RunIssueLog: Sendable, Equatable {
    public private(set) var tiles: [O4TileIssues] = []
    private var reports = 0

    public init() {}

    public mutating func begin() { tiles = [] }

    public mutating func add(_ tile: O4TileIssues) { tiles.append(tile) }

    /// Tiles built with warnings so far in this run.
    public var warnedCount: Int {
        tiles.filter { $0.built && !$0.entries.isEmpty }.count
    }

    /// The run's report (nil when there is nothing to say); the log is
    /// empty afterwards.
    public mutating func finish() -> O4RunIssues? {
        reports += 1
        defer { tiles = [] }
        return O4RunIssues(id: reports, tiles: tiles)
    }
}

/// App-side copy around the engine's messages (identical to the Qt
/// window's `O4_Qt_Tile_Failures.AIRPORT_FAILED_LINE`).
public enum O4TileFailureCopy {
    public static func airportFailedLine(tile: String, airport: String) -> String {
        "*** Tile \(tile): airport \(airport) could not be patched — "
            + "the tile's report will say why."
    }

    public static let builtWithWarnings = "built with warnings"

    // The report buttons (#565), identical to the Qt window's.
    public static let reportButton = "Report this problem"
    public static let saveReportButton = "Save report file"
    public static let reportPreviewTitle = "This is what the report says"
    public static let reportPreviewNote =
        "Nothing has been sent. Pressing the button below copies this text and "
        + "opens a new GitHub issue in your browser, where you can read it again "
        + "before posting."
    public static let openIssueButton = "Copy and Open GitHub"

    // An output folder behind a link to an unmounted drive (#668).
    public static let removeLinkButton = "Remove the link and build on this Mac's drive"
    public static let removeLinkCancel = "Cancel"
    public static func removeLinkFailed(_ reason: String) -> String {
        "The link was not removed. " + reason
    }
}

/// The engine's redacted report of one tile (`failure_report` command,
/// protocol 1.10, issue #565).
public struct O4FailureReport: Sendable, Equatable {
    public let title: String
    public let report: String
    public let issueURL: String
    public let fileName: String
    public let savedPath: String

    /// The command exists from protocol 1.10: an older engine answers
    /// "unknown command", so the buttons are not offered to it.
    public static func supported(protocolVersion: String) -> Bool {
        let parts = protocolVersion.split(separator: ".").map { Int($0) ?? 0 }
        guard parts.count >= 2 else { return false }
        return (parts[0], parts[1]) >= (1, 10)
    }
}
