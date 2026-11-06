import Foundation

/// One adjustment of an airport pack (engine `PackAdjust.items`, issue
/// #1916): `trees` (point old flat forests at the X-Plane 12 3D trees),
/// `drapes` (hide the package's draped photos over the airport) — each a
/// checkbox — or `flatten` (the apt.dat's `1302 flatten 1`, removed with
/// no question: `automatic`).
public struct O4PackAdjustItem: Sendable, Equatable, Identifiable {
    public let key: String
    /// Definitions (`trees`, `drapes`).
    public let count: Int
    /// Polygons drawing them.
    public let uses: Int
    public let automatic: Bool
    public var id: String { key }

    public init(key: String, count: Int, uses: Int, automatic: Bool) {
        self.key = key
        self.count = count
        self.uses = uses
        self.automatic = automatic
    }

    /// The row's title.
    public var title: String { O4PackAdjustCopy.itemTitles[key] ?? key }
    /// The row's one-line explanation.
    public var detail: String {
        (O4PackAdjustCopy.itemDetails[key] ?? "")
            .replacingOccurrences(of: "{n}", with: "\(count)")
            .replacingOccurrences(of: "{uses}", with: "\(uses)")
    }
}

/// An airport pack's adjustments as ONE question (engine `PackAdjust`,
/// capability `pack_adjust`, issue #1916). `state` "found" (a build) or
/// "ask" (the report): Apply sends `pack_adjust` "update" with the checked
/// rows and every row shown, Never for this pack "never", Not now
/// nothing. The other states are a command's outcome.
public struct O4PackAdjust: Sendable, Equatable, Identifiable {
    public let pack: String
    public let packRoot: String
    public let lat: Int
    public let lon: Int
    public let items: [O4PackAdjustItem]
    public let files: [String]
    public let state: String
    public let error: String

    /// One question per pack, tile and row set.
    public var id: String {
        "\(packRoot)|\(lat)|\(lon)|" + items.map(\.key).joined(separator: ",")
    }

    public init(pack: String, packRoot: String, lat: Int, lon: Int,
                items: [O4PackAdjustItem], files: [String], state: String,
                error: String) {
        self.pack = pack
        self.packRoot = packRoot
        self.lat = lat
        self.lon = lon
        self.items = items
        self.files = files
        self.state = state
        self.error = error
    }

    /// The rows the user chooses (each checked when the question opens).
    public var choices: [O4PackAdjustItem] { items.filter { !$0.automatic } }
    /// The rows the app applies with no question.
    public var automatic: [O4PackAdjustItem] { items.filter(\.automatic) }
    /// A question to ask: a build's or the report's, with a choice in it.
    public var asks: Bool { (state == "found" || state == "ask") && !choices.isEmpty }
    public var titleText: String { O4PackAdjustCopy.title(pack: pack) }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Pack_Adjust.py`, whose twin
/// `tests/test_qt_pack_adjust.py` reads this file to pin the parity).
public enum O4PackAdjustCopy {
    public static func title(pack: String) -> String {
        "Adjust “\(pack)”?"
    }

    public static let body = "The app is modifying this airport package. "
        + "These changes help it fit your scenery. Choose what to apply:"

    /// Per row: its checkbox (or, automatic, its label).
    public static let itemTitles: [String: String] = [
        "trees": "Update trees",
        "drapes": "Hide draped orthophotos included with the package",
        "flatten": "Remove the airport’s flatten flag (always)",
    ]

    /// Per row: its explanation.
    public static let itemDetails: [String: String] = [
        "trees": "{n} old flat (X-Plane 11) tree resources become X-Plane 12 "
            + "3D trees.",
        "drapes": "{n} photo images ({uses} polygons) laid over the airport "
            + "cover the tile’s imagery.",
        "flatten": "The apt.dat asks X-Plane to flatten the airport, which "
            + "does not work with this app’s terrain mesh.",
    ]

    public static let detail = "The original files are kept as backups. Undo "
        + "is Restore originals on the pack’s row under Modified airports."

    public static let applyButton = "Apply"
    public static let notNowButton = "Not now"
    public static let neverButton = "Never for this pack"
}
