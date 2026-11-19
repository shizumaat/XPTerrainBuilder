import Foundation

/// One pair of packs that draw the same large structures near an airport
/// (engine `PackOverlaps.items`, issue #2145). `defaultWinner` is the
/// airport pack (the picker's pre-selection), `winner` the remembered
/// answer ("" none, "both" keep both).
///
/// `kind` "duplicate" (RULINGS 17s, owner 2026-11-17T23:37Z): the two
/// packs define the same airport, `packs` upper first by scenery_packs.ini;
/// the picker offers to disable `lower` ("disable") or keep both enabled
/// ("keep"); `lower` empty is a report (a pack the ini does not list): no
/// picker, nothing sent.
///
/// `kind` "drapes" (RULINGS 2026-11-19h): `lower` drapes ground polygons
/// inside the custom airport of `defaultWinner`; the picker offers to hide
/// them (winner = the airport pack) or keep both.
public struct O4PackOverlap: Sendable, Equatable, Identifiable {
    public let key: String
    public let packs: [String]
    public let airport: String
    public let defaultWinner: String
    public let winner: String
    public let count: Int
    public let rows: [Int]
    public let summary: String
    public let kind: String
    public let lower: String
    public var id: String { key }

    public init(key: String, packs: [String], airport: String, defaultWinner: String,
                winner: String, count: Int, rows: [Int], summary: String,
                kind: String = "", lower: String = "") {
        self.key = key
        self.packs = packs
        self.airport = airport
        self.defaultWinner = defaultWinner
        self.winner = winner
        self.count = count
        self.rows = rows
        self.summary = summary
        self.kind = kind
        self.lower = lower
    }

    /// Two packs defining the same airport (not a structure pair).
    public var sameAirport: Bool { kind == O4PackOverlapsCopy.duplicateKind }

    /// A lower pack's draped polygons inside a custom airport.
    public var drapes: Bool { kind == O4PackOverlapsCopy.drapesKind }

    /// The picker's `(label, winner)` entries: each pack, then both; for a
    /// same-airport pair, disable the lower pack or keep both enabled (none
    /// for a report).
    public var choices: [(label: String, winner: String)] {
        if sameAirport {
            return lower.isEmpty ? [] : [
                (O4PackOverlapsCopy.disablePrefix + lower, O4PackOverlapsCopy.disable),
                (O4PackOverlapsCopy.keepEnabled, O4PackOverlapsCopy.keep),
            ]
        }
        if drapes {
            return [
                (O4PackOverlapsCopy.hidePrefix + lower + O4PackOverlapsCopy.hideSuffix,
                 defaultWinner),
                (O4PackOverlapsCopy.keepBoth, O4PackOverlapsCopy.both),
            ]
        }
        return packs.map { (O4PackOverlapsCopy.keepPrefix + $0, $0) }
            + [(O4PackOverlapsCopy.keepBoth, O4PackOverlapsCopy.both)]
    }

    /// The remembered answer, else the airport pack.
    public var preselected: String {
        !winner.isEmpty ? winner : (!defaultWinner.isEmpty ? defaultWinner : (packs.first ?? ""))
    }
}

/// The tile's overlapping packs as ONE question (engine `PackOverlaps`,
/// capability `pack_overlaps`, issue #2145). `state` "found" (a build) or
/// "ask" (the report): Apply sends `pack_overlaps` "choose" with every
/// pair's pick, Not now nothing. The other states are a command's outcome.
public struct O4PackOverlaps: Sendable, Equatable, Identifiable {
    public let lat: Int
    public let lon: Int
    public let items: [O4PackOverlap]
    public let files: [String]
    public let state: String
    public let error: String

    /// One question per tile and pair set.
    public var id: String {
        "\(lat)|\(lon)|" + offers.map(\.key).joined(separator: ",")
    }

    public init(lat: Int, lon: Int, items: [O4PackOverlap],
                files: [String], state: String, error: String) {
        self.lat = lat
        self.lon = lon
        self.items = items
        self.files = files
        self.state = state
        self.error = error
    }

    /// The pairs to offer: two packs each.
    public var offers: [O4PackOverlap] { items.filter { $0.packs.count == 2 && !$0.key.isEmpty } }
    /// A question to ask: a build's or the report's, with a pair in it.
    public var asks: Bool { (state == "found" || state == "ask") && !offers.isEmpty }
    /// The report of a tile with no pair: shown as "no pairs" (#2180).
    public var reportsNone: Bool { state == "ask" && offers.isEmpty }
    /// The pairs Apply answers (a report row has no picker).
    public var answerable: [O4PackOverlap] { offers.filter { !$0.choices.isEmpty } }
    /// A same-airport pair is shown (its words and the restart note).
    public var hasSameAirport: Bool { offers.contains { $0.sameAirport } }
    /// A drape pair is shown (its words).
    public var hasDrapes: Bool { offers.contains { $0.drapes } }
}

/// The copy, VERBATIM and identical to the Qt question
/// (`Ortho4XP/src/O4_Qt_Pack_Overlaps.py`, whose twin
/// `tests/test_qt_pack_overlaps.py` reads this file to pin the parity).
public enum O4PackOverlapsCopy {
    public static let title = "Two packs draw the same structures"

    public static let body = "These packs both draw large structures in the same place near the "
        + "airport. Choose the pack to keep for each pair; the other pack's "
        + "copies are hidden, and the one you keep is fitted to the terrain."

    public static let keepBoth = "Keep both"
    public static let keepPrefix = "Keep "

    public static let detail = "Only this app's rewrite of the pack's tile changes; Restore "
        + "originals on the pack puts everything back."

    public static let applyButton = "Apply"
    public static let notNowButton = "Not now"
    /// The `winner` that keeps both packs' structures.
    public static let both = "both"

    // Two packs defining the same airport (RULINGS 17s, 23:37Z).
    public static let sameAirport = "Some packs define the same airport. X-Plane uses the "
        + "layout of the pack higher in scenery_packs.ini; the lower pack's "
        + "scenery may still overlap it."
    public static let disablePrefix = "Disable "
    public static let keepEnabled = "Keep both enabled"
    public static let restartNote = "Disabling a pack changes only its line in "
        + "scenery_packs.ini; its files stay. Restart X-Plane to use the change."
    /// The row `kind` and the `winner`s of a same-airport pair.
    public static let duplicateKind = "duplicate"
    public static let disable = "disable"
    public static let keep = "keep"

    // A lower pack's draped polygons inside a custom airport (RULINGS 19h).
    public static let drapesNote = "Some packs lower in scenery_packs.ini drape their own "
        + "ground polygons inside a custom airport, under the airport's layout. "
        + "Hiding them leaves them out of that pack's tile; no file is deleted."
    public static let hidePrefix = "Hide "
    public static let hideSuffix = "'s polygons inside the airport"
    /// The row `kind` of a drape pair.
    public static let drapesKind = "drapes"

    // Reviewing a tile's answers later (#2180): the tile pane's button
    // sends `pack_overlaps` "ask" and opens this question on every pair.
    public static let reviewButton = "Pack choices…"
    public static let reviewHelp = "Review and change this tile's answers about packs "
        + "that draw the same structures."
    public static let noPairs = "No two packs draw the same structures on this tile."
    public static let okButton = "OK"
}
