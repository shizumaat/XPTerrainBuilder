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

    public var id: String { code + "|" + what }

    public init(code: String, what: String, why: String, remedy: String,
                airports: [String] = [], detail: String = "", logPath: String = "") {
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
                logPath: entry["log_path"] as? String ?? "")
        }
    }

    /// The three sentences, one per line.
    public var message: String { [what, why, remedy].joined(separator: "\n") }

    /// The console block: the three sentences, then the technical detail.
    public func consoleLines(isWarning: Bool) -> [String] {
        var lines = [(isWarning ? "Warning: " : "*** ") + what, "    " + why, "    " + remedy]
        for line in detail.split(separator: "\n") {
            lines.append("      detail: " + line)
        }
        return lines
    }
}

/// One tile's messages at the end of its build.
public struct O4TileIssues: Sendable, Equatable {
    public let tileKey: String
    public let built: Bool
    public let failures: [O4TileFailure]
    public let warnings: [O4TileFailure]

    public init(tileKey: String, built: Bool,
                failures: [O4TileFailure], warnings: [O4TileFailure]) {
        self.tileKey = tileKey
        self.built = built
        self.failures = failures
        self.warnings = warnings
    }

    public var entries: [O4TileFailure] { failures + warnings }
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

/// App-side copy around the engine's messages (identical to the Qt
/// window's `O4_Qt_Tile_Failures.AIRPORT_FAILED_LINE`).
public enum O4TileFailureCopy {
    public static func airportFailedLine(tile: String, airport: String) -> String {
        "*** Tile \(tile): airport \(airport) could not be patched — "
            + "the tile's report will say why."
    }

    public static let builtWithWarnings = "built with warnings"
}
