import Foundation

/// One pair of packs that draw the same large structures near an airport
/// (engine `PackOverlaps.items`, issue #2145). `defaultWinner` is the
/// airport pack (the picker's pre-selection), `winner` the remembered
/// answer ("" none, "both" keep both).
public struct O4PackOverlap: Sendable, Equatable, Identifiable {
    public let key: String
    public let packs: [String]
    public let airport: String
    public let defaultWinner: String
    public let winner: String
    public let count: Int
    public let rows: [Int]
    public let summary: String
    public var id: String { key }

    public init(key: String, packs: [String], airport: String, defaultWinner: String,
                winner: String, count: Int, rows: [Int], summary: String) {
        self.key = key
        self.packs = packs
        self.airport = airport
        self.defaultWinner = defaultWinner
        self.winner = winner
        self.count = count
        self.rows = rows
        self.summary = summary
    }

    /// The picker's `(label, winner)` entries: each pack, then both.
    public var choices: [(label: String, winner: String)] {
        packs.map { (O4PackOverlapsCopy.keepPrefix + $0, $0) }
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
}
