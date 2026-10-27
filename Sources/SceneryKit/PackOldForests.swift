import Foundation

/// An airport pack whose DSF draws old flat (X-Plane 11) forests that have
/// X-Plane 12 3D equivalents (engine `PackOldForests`, protocol 1.17,
/// issue #1360).
///
/// `state`: "found" — ask (only when `canUpdate`): Update sends
/// `pack_forests` with action "update", Never for this pack with "never",
/// Not now sends nothing. "upgraded" / "undone" / "never" / "failed" /
/// "none" — a build's or a `pack_forests` command's outcome (the engine log
/// line already says what happened; `files` lists what was rewritten).
public struct O4PackOldForests: Sendable, Equatable, Identifiable {
    public let pack: String
    public let packRoot: String
    public let lat: Int
    public let lon: Int
    /// Flat forest definitions the DSF declares.
    public let total: Int
    /// Those with an X-Plane 12 3D equivalent, and their polygons.
    public let mapped: Int
    public let uses: Int
    public let firstPaths: [String]
    /// Those without one: they stay as they are.
    public let unmapped: Int
    public let firstUnmapped: [String]
    public let canUpdate: Bool
    public let files: [String]
    public let state: String
    public let error: String

    /// One question per pack, tile and set: every airport of a pack runs
    /// the check, and the second airport's event is the same news.
    public var id: String {
        "\(packRoot)|\(lat)|\(lon)|\(mapped)|\(firstPaths.joined(separator: "|"))"
    }

    public init(pack: String, packRoot: String, lat: Int, lon: Int,
                total: Int, mapped: Int, uses: Int, firstPaths: [String],
                unmapped: Int, firstUnmapped: [String], canUpdate: Bool,
                files: [String], state: String, error: String) {
        self.pack = pack
        self.packRoot = packRoot
        self.lat = lat
        self.lon = lon
        self.total = total
        self.mapped = mapped
        self.uses = uses
        self.firstPaths = firstPaths
        self.unmapped = unmapped
        self.firstUnmapped = firstUnmapped
        self.canUpdate = canUpdate
        self.files = files
        self.state = state
        self.error = error
    }

    /// The question's title.
    public var titleText: String { O4PackOldForestsCopy.title(pack: pack) }
    /// The question, the backup line and, when some have no 3D
    /// equivalent, the line that names them.
    public var bodyText: String {
        var text = O4PackOldForestsCopy.body(count: mapped)
            + "\n\n" + O4PackOldForestsCopy.detail
        if unmapped > 0 {
            text += "\n\n" + O4PackOldForestsCopy.unmappedLine(
                count: unmapped, firstPath: firstUnmapped.first ?? "")
        }
        return text
    }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Pack_Forests.py`, whose twin
/// `tests/test_qt_pack_forests.py` reads this file to pin the parity). The
/// question is the owner's (issue #1360).
public enum O4PackOldForestsCopy {
    public static func title(pack: String) -> String {
        "3D trees for “\(pack)”"
    }

    public static func body(count: Int) -> String {
        "This airport’s scenery uses \(count) old flat (X-Plane 11) tree "
            + "resources. Switch them to the X-Plane 12 3D trees?"
    }

    public static let detail = "The original scenery file is kept as a backup. "
        + "Undo is on the pack’s row under Modified airports."

    public static func unmappedLine(count: Int, firstPath: String) -> String {
        "\(count) other flat tree resource(s) have no X-Plane 12 3D "
            + "equivalent and stay as they are (first: \(firstPath))."
    }

    public static let updateButton = "Update"
    public static let notNowButton = "Not now"
    public static let neverButton = "Never for this pack"
    /// The pack row's Undo button (tooltip).
    public static let undoHelp = "Undo 3D trees: put back this package’s "
        + "original flat (X-Plane 11) tree resources."
}
