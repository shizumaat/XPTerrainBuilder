import XCTest
@testable import XPTerrainBuilder

/// #1922: "Use auto patch" waits only for its own tile. Qt twin:
/// `Ortho4XP/tests/test_qt_custom_patch.py`.
@MainActor
final class UseAutoPatchButtonTests: XCTestCase {
    func testOnlyTheTileInTheRunIsHeld() {
        let building = BuildModel.TileCoord(lat: 46, lon: 6)
        let queued = BuildModel.TileCoord(lat: 47, lon: 6)
        let idle = BuildModel.TileCoord(lat: 45, lon: 5)
        let activity = BuildActivityModel()
        activity.queueRows([building, queued])
        activity.tiles[building] = TileProgress(state: .active, label: "building", percent: 10)
        XCTAssertFalse(BuildModel.tileInRun(idle, running: true, activity: activity))
        XCTAssertTrue(BuildModel.tileInRun(building, running: true, activity: activity))
        XCTAssertTrue(BuildModel.tileInRun(queued, running: true, activity: activity))
        XCTAssertFalse(BuildModel.tileInRun(building, running: false, activity: activity))
    }
}
