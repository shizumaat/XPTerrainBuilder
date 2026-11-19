import Foundation

/// An airport pack whose folders are read-only as it was downloaded, so the
/// build cannot adjust it (engine `PackReadOnly`, capability
/// `pack_readonly`, issue #2174, RULINGS 2026-11-19d).
///
/// `state`: "found" (a build's: its writes of the pack wait for the answer)
/// asks once per pack; "ask" (the row's Ask again) asks every time. Make
/// writable sends `pack_readonly` with action "writable", Not now with
/// "not_now" — both are answers the waiting build reads. "writable" /
/// "not_now" / "none" / "failed" are outcomes; "writable" with `rebuild`
/// means no build was waiting: the app rebuilds tile lat/lon.
public struct O4PackReadOnly: Sendable, Equatable, Identifiable {
    public let pack: String
    public let packRoot: String
    public let lat: Int
    public let lon: Int
    /// The read-only folders, inside the pack (named first), at most eight.
    public let folders: [String]
    public let changed: Int
    public let rebuild: Bool
    public let state: String
    public let error: String

    /// One question per pack: every tile and airport of it waits on the
    /// same answer.
    public var id: String { packRoot }

    /// The event asks the user.
    public var asks: Bool { state == "found" || state == "ask" }

    public init(pack: String, packRoot: String, lat: Int, lon: Int,
                folders: [String], changed: Int = 0, rebuild: Bool = false,
                state: String, error: String = "") {
        self.pack = pack
        self.packRoot = packRoot
        self.lat = lat
        self.lon = lon
        self.folders = folders
        self.changed = changed
        self.rebuild = rebuild
        self.state = state
        self.error = error
    }

    static func parse(_ object: [String: Any]) -> O4PackReadOnly {
        func int(_ key: String) -> Int { (object[key] as? NSNumber)?.intValue ?? 0 }
        return O4PackReadOnly(
            pack: object["pack"] as? String ?? "",
            packRoot: object["pack_root"] as? String ?? "",
            lat: int("lat"), lon: int("lon"),
            folders: (object["folders"] as? [Any])?.compactMap { $0 as? String } ?? [],
            changed: int("changed"),
            rebuild: (object["rebuild"] as? NSNumber)?.boolValue ?? false,
            state: object["state"] as? String ?? "found",
            error: object["error"] as? String ?? "")
    }

    /// The question's title.
    public var titleText: String { O4PackReadOnlyCopy.title(pack: pack) }
    /// The question and the folders it is about.
    public var bodyText: String {
        var text = O4PackReadOnlyCopy.body(pack: pack) + "\n\n" + O4PackReadOnlyCopy.detail
        if !folders.isEmpty {
            text += "\n\n" + O4PackReadOnlyCopy.foldersLine(folders)
        }
        return text
    }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Pack_ReadOnly.py`, whose twin
/// `tests/test_qt_pack_readonly.py` reads this file to pin the parity). The
/// question is the owner's (RULINGS 2026-11-19d).
public enum O4PackReadOnlyCopy {
    public static func title(pack: String) -> String {
        "“\(pack)” is read-only"
    }

    public static func body(pack: String) -> String {
        "\(pack) is read-only (as it was downloaded), so XPTerrainBuilder "
            + "can't adjust it. Make it writable?"
    }

    public static let detail = "Make writable adds your write permission to "
        + "this package's folders and files only; its originals are kept as "
        + "backups when it is adjusted."

    public static func foldersLine(_ folders: [String]) -> String {
        "Read-only: " + folders.joined(separator: ", ")
    }

    public static let writableButton = "Make writable"
    public static let notNowButton = "Not now"
    /// The tile row's words under Modified airports, and its button.
    public static let rowStatus = "read-only — not adjusted"
    public static let askAgainButton = "Ask again"
    public static let askAgainHelp = "This package is read-only, so it was "
        + "not adjusted. Ask again to make it writable."

    public static let runBusy = "a run is building; rebuild it when the run finishes"

    public static func rebuildLater(tile: String, pack: String, reason: String) -> String {
        "Rebuild tile \(tile) to adjust \(pack) now that it is writable: \(reason)"
    }
}

extension OrthoEngineClient {
    /// The user's answer about a read-only pack (#2174): action
    /// "writable", "not_now" or "ask" (the row's Ask again). The engine
    /// replies `{"status": "started"}` at once and completes with a
    /// `packReadOnly` event.
    public func packReadOnly(packRoot: String, action: String,
                             lat: Int? = nil, lon: Int? = nil) {
        var arguments: [String: Any] = ["pack_root": packRoot, "action": action]
        if let lat, let lon {
            arguments["lat"] = lat
            arguments["lon"] = lon
        }
        send(command: "pack_readonly", arguments: arguments)
    }
}
