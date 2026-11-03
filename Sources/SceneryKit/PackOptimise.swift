import Foundation

/// An airport pack "Optimise pack" can lighten (engine `PackOptimise`,
/// protocol 1.31, issue #1707; `swapped` since 1.33).
///
/// `state`: "found" — ask (only when `canOptimise`): Optimise sends
/// `pack_optimise` with action "update", Never for this pack with "never",
/// Not now sends nothing. "optimised" / "undone" / "never" / "failed" /
/// "none" — a build's or a `pack_optimise` command's outcome (the engine
/// log line already says what happened; `files` lists what was rewritten).
public struct O4PackOptimise: Sendable, Equatable, Identifiable {
    public let pack: String
    public let packRoot: String
    public let lat: Int
    public let lon: Int
    /// Duplicate placements the recipe drops.
    public let dedupe: Int
    /// Placements it swaps for X-Plane's lighter library vehicles and
    /// ground equipment (0 from an engine before protocol 1.33).
    public let swapped: Int
    /// Triangles the pack's own objects draw on the tile, without and
    /// with the recipe.
    public let estTrisBefore: Int
    public let estTrisAfter: Int
    public let canOptimise: Bool
    public let files: [String]
    public let state: String
    public let error: String

    /// One question per pack, tile and count: every airport of a pack
    /// runs the check, and the second airport's event is the same news.
    public var id: String { "\(packRoot)|\(lat)|\(lon)|\(dedupe)|\(swapped)" }

    public init(pack: String, packRoot: String, lat: Int, lon: Int,
                dedupe: Int, swapped: Int = 0, estTrisBefore: Int,
                estTrisAfter: Int, canOptimise: Bool, files: [String],
                state: String, error: String) {
        self.pack = pack
        self.packRoot = packRoot
        self.lat = lat
        self.lon = lon
        self.dedupe = dedupe
        self.swapped = swapped
        self.estTrisBefore = estTrisBefore
        self.estTrisAfter = estTrisAfter
        self.canOptimise = canOptimise
        self.files = files
        self.state = state
        self.error = error
    }

    /// The question's title.
    public var titleText: String { O4PackOptimiseCopy.title(pack: pack) }
    /// The question and the line that says how it is kept and undone.
    public var bodyText: String {
        O4PackOptimiseCopy.body(before: estTrisBefore, count: dedupe,
                                after: estTrisAfter, swapped: swapped)
            + "\n\n" + O4PackOptimiseCopy.detail
    }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Pack_Optimise.py`, whose twin
/// `tests/test_qt_pack_optimise.py` reads this file to pin the parity).
public enum O4PackOptimiseCopy {
    /// Triangles in millions, one decimal ("275.5").
    public static func millions(_ count: Int) -> String {
        String(format: "%.1f", Double(count) / 1e6)
    }

    public static func title(pack: String) -> String {
        "Optimise “\(pack)”?"
    }

    /// The question: the repeats alone, or the repeats and the swaps.
    public static func body(before: Int, count: Int, after: Int,
                            swapped: Int = 0) -> String {
        swapped > 0
            ? bodySwapped(before: before, count: count, swapped: swapped, after: after)
            : bodyRepeats(before: before, count: count, after: after)
    }

    public static func bodyRepeats(before: Int, count: Int, after: Int) -> String {
        "This airport’s objects draw \(millions(before)) million triangles "
            + "on this tile, enough to cost frame rate. \(count) of its object "
            + "placements repeat another on the same spot. Optimise removes "
            + "them (\(millions(after)) million triangles)."
    }

    public static func bodySwapped(before: Int, count: Int, swapped: Int,
                                   after: Int) -> String {
        "This airport’s objects draw \(millions(before)) million triangles "
            + "on this tile, enough to cost frame rate. Optimise removes the "
            + "\(count) object placements that repeat another on the same spot "
            + "and swaps \(swapped) heavy vehicles and ground equipment for "
            + "X-Plane’s lighter library ones (\(millions(after)) million "
            + "triangles)."
    }

    public static let detail = "The original scenery file is kept as a backup, "
        + "and the optimisation is applied again whenever the app rewrites "
        + "this pack. Undo is on the pack’s row under Modified airports."

    public static let optimiseButton = "Optimise"
    public static let notNowButton = "Not now"
    public static let neverButton = "Never for this pack"
    /// The pack row's Optimise button (tooltip).
    public static let optimiseHelp = "Optimise pack: remove object "
        + "placements that repeat another on the same spot, and swap heavy "
        + "vehicles for X-Plane’s lighter library ones."
    /// The pack row's Undo optimise button (tooltip).
    public static let undoHelp = "Undo optimise: put back this package’s "
        + "original object placements."
}
