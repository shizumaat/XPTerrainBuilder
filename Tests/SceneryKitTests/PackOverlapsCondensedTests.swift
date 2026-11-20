import Testing
import Foundation
@testable import SceneryKit

/// #2190: what the condensed answer gives each pair (twin of
/// `Ortho4XP/tests/test_qt_pack_overlaps.py`'s condensed tests).
struct PackOverlapsCondensedTests {
    private func pair(_ key: String, prefer: String, keep: String,
                      kind: String = "", lower: String = "") -> O4PackOverlap {
        O4PackOverlap(key: key, packs: ["City", "Field"], airport: "Field",
                      defaultWinner: "Field", winner: "", count: 1, rows: [1, 1],
                      summary: "", kind: kind, lower: lower, prefer: prefer, keep: keep)
    }

    @Test func eachModeReadsItsField() {
        let p = pair("a", prefer: "Field", keep: "both")
        #expect(p.winner(for: O4PackOverlapsCondensedCopy.prefer) == "Field")
        #expect(p.winner(for: O4PackOverlapsCondensedCopy.keepAll) == "both")
        #expect(p.winner(for: "") == "")
        #expect(pair("b", prefer: "", keep: "both")
            .winner(for: O4PackOverlapsCondensedCopy.prefer) == "")
    }

    @Test func aReportRowIsNeverDecided() {
        let report = pair("c", prefer: "x", keep: "x", kind: "duplicate", lower: "")
        #expect(report.winner(for: O4PackOverlapsCondensedCopy.keepAll) == "")
    }

    @Test func theQuestionOpensOnTheStoredDefaultElsePrefer() {
        let none = O4PackOverlaps(lat: 1, lon: 2, items: [], files: [], state: "found", error: "")
        #expect(none.initialMode == O4PackOverlapsCondensedCopy.prefer)
        let keep = O4PackOverlaps(lat: 1, lon: 2, items: [], files: [], state: "found",
                                  error: "", defaultMode: O4PackOverlapsCondensedCopy.keepAll)
        #expect(keep.initialMode == O4PackOverlapsCondensedCopy.keepAll)
    }
}
