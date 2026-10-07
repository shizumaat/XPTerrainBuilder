import Foundation

/// A scenery pack X-Plane will NOT load (engine `PackMissingArt`, protocol
/// 1.9; owner RULINGS 2026-10-06c, issue #433): its DSF declares
/// definitions whose files are not installed, and X-Plane skips a whole
/// pack when one is missing.
///
/// `state`: "found" — show the warning (the primary button only when
/// `canOmit`); "omitted" / "failed" / "none" — the completion of an
/// `omit_missing_art` command (the engine log line already says what
/// happened). A missing TERRAIN definition cannot be omitted: `canOmit` is
/// false and the warning has no primary button.
public struct O4PackMissingArt: Sendable, Equatable, Identifiable {
    public let pack: String
    public let packRoot: String
    public let lat: Int
    public let lon: Int
    public let total: Int
    /// "object" | "polygon" | "network" | "terrain" → definitions missing.
    public let kinds: [String: Int]
    public let uses: Int
    public let firstPaths: [String]
    public let canOmit: Bool
    public let state: String
    public let error: String

    /// One warning per pack, tile and missing set: every airport of a pack
    /// runs the check, and the second airport's event is the same news.
    public var id: String {
        "\(packRoot)|\(lat)|\(lon)|\(total)|\(firstPaths.joined(separator: "|"))"
    }

    public init(pack: String, packRoot: String, lat: Int, lon: Int,
                total: Int, kinds: [String: Int], uses: Int,
                firstPaths: [String], canOmit: Bool, state: String,
                error: String) {
        self.pack = pack
        self.packRoot = packRoot
        self.lat = lat
        self.lon = lon
        self.total = total
        self.kinds = kinds
        self.uses = uses
        self.firstPaths = firstPaths
        self.canOmit = canOmit
        self.state = state
        self.error = error
    }

    /// The warning's title (owner-fixed copy).
    public var titleText: String { O4PackMissingArtCopy.title(pack: pack) }
    /// The warning's body (owner-fixed copy).
    public var bodyText: String {
        O4PackMissingArtCopy.body(count: total, firstPath: firstPaths.first ?? "")
    }
}

/// The owner-fixed copy (RULINGS 2026-10-06c), VERBATIM and identical to
/// the Qt warning (`Ortho4XP/src/O4_Qt_Pack_Art.py`, whose twin
/// `tests/test_qt_pack_art.py` reads this file to pin the parity).
public enum O4PackMissingArtCopy {
    public static func title(pack: String) -> String {
        "X-Plane will not load “\(pack)”"
    }

    public static func body(count: Int, firstPath: String) -> String {
        "Its scenery file refers to \(count) file(s) that are not installed "
            + "(first: \(firstPath)). X-Plane skips a scenery pack entirely when any "
            + "file it refers to is missing, so this airport’s buildings "
            + "and ground would not appear in the simulator."
    }

    public static let primaryButton = "Build without the missing items"
    public static let secondaryButton = "Leave the pack as it is"
    public static let detail = "The original scenery file is kept as a backup and can be restored."
}
