import XCTest
@testable import XPTerrainBuilder

/// #2168: a Modified airports row waits only while the run builds a tile
/// that writes its pack. Qt twin: `Ortho4XP/tests/test_qt_pack_forests.py`
/// (`test_a_run_on_other_tiles_never_holds_the_pack_row`).
@MainActor
final class PackRowButtonsTests: XCTestCase {
    func testARunOnOtherTilesNeverHoldsThePackRow() {
        let kase = BuildModel.TileCoord(lat: 39, lon: -107)
        let lfpg = BuildModel.TileCoord(lat: 48, lon: 2)
        let activity = BuildActivityModel()
        activity.queueRows([lfpg])
        activity.tiles[lfpg] = TileProgress(state: .active, label: "auto-patch", percent: 40)
        XCTAssertFalse(BuildModel.packRowBusy(tiles: ["+39-107"], active: kase,
                                              running: true, activity: activity))
        // a pack tile other than the active one, in the run
        XCTAssertTrue(BuildModel.packRowBusy(tiles: ["+48+002"], active: kase,
                                             running: true, activity: activity))
        XCTAssertTrue(BuildModel.packRowBusy(tiles: [], active: lfpg,
                                             running: true, activity: activity))
        XCTAssertFalse(BuildModel.packRowBusy(tiles: ["+48+002"], active: kase,
                                              running: false, activity: activity))
    }
}
