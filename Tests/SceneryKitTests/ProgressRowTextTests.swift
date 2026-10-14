import Testing
import Foundation
@testable import SceneryKit

/// Issue #694: a progress row is THREE texts — the title (coordinate plus
/// the #667 search tag) alone on line one, the status and the time on
/// line two. The Qt twin is
/// `test_progress_row_title_owns_its_line_status_and_clock_share_the_next`.
@Suite struct ProgressRowTextTests {
    private func clock(_ elapsed: Double, _ remaining: Double?, finished: Bool = false) -> O4TileClock {
        O4TileClock(lat: -13, lon: -78, elapsedSeconds: elapsed,
                    remainingSeconds: remaining, finished: finished)
    }

    @Test func titleCarriesTheSearchTagStatusAndTimeAreSeparate() {
        let row = ProgressRowText(tileKey: "-13-078", tag: TileSearchTags.suffix(["SPJC"]),
                                  status: "mesh · 42%", clock: clock(83, 296))
        #expect(row.title == "-13-078 (SPJC)")
        #expect(row.status == "mesh · 42%")
        #expect(row.time == "1:23 · ~4:56")
    }

    @Test func handPickedTileHasABareTitle() {
        let row = ProgressRowText(tileKey: "+10+010", tag: "", status: "queued", clock: nil)
        #expect(row.title == "+10+010")
        #expect(row.time == nil)
    }

    @Test func clockTextCoversEveryRowState() {
        #expect(ProgressRowText.tileClockText(clock(3725, nil, finished: true)) == "1:02:05")
        #expect(ProgressRowText.tileClockText(clock(10, nil)) == "0:10 · —")
        #expect(ProgressRowText.tileClockText(clock(0, 754)) == "~12:34")
        #expect(ProgressRowText.tileClockText(clock(0, nil)) == nil)
    }
}
