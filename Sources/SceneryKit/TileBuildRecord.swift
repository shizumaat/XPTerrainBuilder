import Foundation

/// PER-TILE BUILD LOGS AND THE BUILD RECORD (#1226, owner Q139).
///
/// The engine writes, inside each tile's build folder,
/// `build_logs/<UTC stamp>_<tile>.log` (the tile's newest 3 builds) and
/// `build_logs/build_record.json` (one row per kept build). The app reads
/// them to show a selected tile's saved log, the Build History list and
/// the "Built by" line.
///
/// TWIN of the engine's `O4_Tile_Build_Log` (`Ortho4XP/src/
/// O4_Tile_Build_Log.py`): the same record schema (the shared fixture
/// `Ortho4XP/tests/fixtures/build_record_v1.json`), the same console
/// prefix rule (`tileOfLine`), the same date ranges (`BuildDateRange`)
/// and the same "Built by" wording. A change to one is a change to both.
public struct TileBuildRecord: Codable, Sendable, Equatable, Hashable {
    /// Who built the tile (owner Q95): tool and both versions.
    public struct Builder: Codable, Sendable, Equatable, Hashable {
        public let tool: String
        public let appVersion: String
        public let engineVersion: String

        enum CodingKeys: String, CodingKey {
            case tool
            case appVersion = "app_version"
            case engineVersion = "engine_version"
        }
    }

    /// `+47-123`.
    public let tile: String
    /// Epoch seconds.
    public let start: Double
    public let end: Double
    public let duration: Double
    /// `ok` / `warnings` / `failed` / `stopped`.
    public let outcome: String
    public let warnings: Int
    /// The log's file name inside `build_logs/`.
    public let log: String
    public let builder: Builder?

    /// The record row as it arrives in a scan's `last_build`.
    public init?(json: O4JSON?) {
        guard let object = json?.objectValue,
              let tile = object["tile"]?.stringValue,
              let start = object["start"]?.doubleValue else { return nil }
        self.tile = tile
        self.start = start
        end = object["end"]?.doubleValue ?? start
        duration = object["duration"]?.doubleValue ?? 0
        outcome = object["outcome"]?.stringValue ?? ""
        warnings = object["warnings"]?.intValue ?? 0
        log = object["log"]?.stringValue ?? ""
        if let who = object["builder"]?.objectValue, let tool = who["tool"]?.stringValue {
            builder = Builder(tool: tool,
                              appVersion: who["app_version"]?.stringValue ?? "",
                              engineVersion: who["engine_version"]?.stringValue ?? "")
        } else {
            builder = nil
        }
    }

    /// The tile info's "Built by" line for this build.
    public var builtBy: String { TileBuildLogs.builtByText(record: self, agent: nil) }

    /// The outcome as the user reads it.
    public var outcomeText: String {
        switch outcome {
        case "ok": return "Built"
        case "warnings": return "Built with warnings"
        case "failed": return "Failed"
        case "stopped": return "Stopped"
        default: return outcome
        }
    }
}

/// Reading the saved logs and records (the engine writes them).
public enum TileBuildLogs {
    public static let directoryName = "build_logs"
    public static let recordName = "build_record.json"

    private struct File: Decodable {
        let schema: Int
        let builds: [TileBuildRecord]
    }

    /// The log folder of a tile build folder.
    public static func directory(buildDir: String) -> URL {
        URL(fileURLWithPath: buildDir, isDirectory: true)
            .appendingPathComponent(directoryName, isDirectory: true)
    }

    /// The tile's kept builds, newest first; empty for a tile built
    /// before logging (or a record that cannot be read).
    public static func records(buildDir: String, tile: String) -> [TileBuildRecord] {
        let url = directory(buildDir: buildDir).appendingPathComponent(recordName)
        guard let data = try? Data(contentsOf: url),
              let file = try? JSONDecoder().decode(File.self, from: data) else { return [] }
        return file.builds.filter { $0.tile == tile }.sorted { $0.start > $1.start }
    }

    /// One saved log's text; "" when it is gone.
    public static func logText(buildDir: String, name: String) -> String {
        guard !name.isEmpty, !name.contains("/") else { return "" }
        let url = directory(buildDir: buildDir).appendingPathComponent(name)
        guard let data = try? Data(contentsOf: url) else { return "" }
        return String(decoding: data, as: UTF8.self)
    }

    /// `(tile key, text)` of a console line: the key of its `[+47-123] `
    /// prefix and the text after it; `(nil, line)` for a run-level line.
    public static func tileOfLine(_ line: String) -> (tile: String?, text: String) {
        // "[" + sign + 2 digits + sign + 3 digits + "] " = 11 characters.
        let chars = Array(line.utf8.prefix(11))
        guard chars.count == 11, chars[0] == UInt8(ascii: "["),
              chars[9] == UInt8(ascii: "]"), chars[10] == UInt8(ascii: " ") else {
            return (nil, line)
        }
        func sign(_ c: UInt8) -> Bool { c == UInt8(ascii: "+") || c == UInt8(ascii: "-") }
        func digit(_ c: UInt8) -> Bool { c >= UInt8(ascii: "0") && c <= UInt8(ascii: "9") }
        guard sign(chars[1]), digit(chars[2]), digit(chars[3]), sign(chars[4]),
              digit(chars[5]), digit(chars[6]), digit(chars[7]) else { return (nil, line) }
        let key = String(decoding: chars[1...8], as: UTF8.self)
        return (key, String(line.dropFirst(11)))
    }

    /// The "Built by" line: from the record's builder; else from the
    /// DSF's `sim/creation_agent` — a bare `Ortho4XP` is an older Ortho4XP
    /// build, anything else is shown as it is. "" when neither is known.
    public static func builtByText(record: TileBuildRecord?, agent: String?) -> String {
        if let who = record?.builder, !who.tool.isEmpty {
            var text = "\(who.tool) \(who.appVersion)".trimmingCharacters(in: .whitespaces)
            if !who.engineVersion.isEmpty { text += ", engine \(who.engineVersion)" }
            return text
        }
        let agent = (agent ?? "").trimmingCharacters(in: .whitespaces)
        return agent == "Ortho4XP" ? "Ortho4XP (older build, version unknown)" : agent
    }
}

/// The one date filter of the Build History list and the map (owner
/// Q139); `all` is the default.
public enum BuildDateRange: String, CaseIterable, Identifiable, Sendable {
    case today
    case last48Hours = "48h"
    case last7Days = "7d"
    case last30Days = "30d"
    case all

    public var id: String { rawValue }

    public var label: String {
        switch self {
        case .today: return "Today"
        case .last48Hours: return "Last 48 hours"
        case .last7Days: return "Last 7 days"
        case .last30Days: return "Last 30 days"
        case .all: return "All"
        }
    }

    /// Whether a build that ended at epoch `ts` falls in the range.
    /// "Today" is since local midnight; an unknown time is only in All.
    public func contains(_ ts: Double?, now: Date = Date(),
                         calendar: Calendar = .current) -> Bool {
        if self == .all { return true }
        guard let ts else { return false }
        let now = now.timeIntervalSince1970
        switch self {
        case .today:
            return ts >= calendar.startOfDay(for: Date(timeIntervalSince1970: now))
                .timeIntervalSince1970
        case .last48Hours: return ts >= now - 48 * 3600
        case .last7Days: return ts >= now - 7 * 86400
        case .last30Days: return ts >= now - 30 * 86400
        case .all: return true
        }
    }
}
