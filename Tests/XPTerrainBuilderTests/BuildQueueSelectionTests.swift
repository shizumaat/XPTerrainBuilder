import XCTest
@testable import XPTerrainBuilder

/// #2043 (1.0.509): under imagery on demand the hidden "Skip tiles
/// already built" acted as on, so a built tile picked during a run left
/// "＋ Queue" disabled, and an airport list whose second airport's tile
/// was built said "Build 1 tile". The Qt twins are in
/// `Ortho4XP/tests/test_qt_activity_queue.py`.
@MainActor
final class BuildQueueSelectionTests: XCTestCase {
    private typealias Tile = BuildModel.TileCoord
    private let running = Tile(lat: 39, lon: -105)   // the tile building now
    private let built = Tile(lat: 37, lon: -123)     // built before, its DSF in its folder
    private let fresh = Tile(lat: 40, lon: -106)

    func testOnDemandNeverSkipsATileTheUserSelected() {
        XCTAssertFalse(BuildModel.skipsBuiltTiles(onDemand: true, skipSwitch: true))
        XCTAssertFalse(BuildModel.skipsBuiltTiles(onDemand: true, skipSwitch: false))
        // Off on demand the visible switch still decides.
        XCTAssertTrue(BuildModel.skipsBuiltTiles(onDemand: false, skipSwitch: true))
        XCTAssertFalse(BuildModel.skipsBuiltTiles(onDemand: false, skipSwitch: false))
    }

    func testABuiltTilePickedDuringARunCanBeQueued() {
        // The run's tile and a built one selected: Queue offers the built one.
        let queue = BuildModel.buildable(selected: [running, built], inRun: [running],
                                         builtWithDSF: [])
        XCTAssertEqual(queue, [built])
        // Only the run's own tile selected: nothing to queue (no second copy).
        XCTAssertTrue(BuildModel.buildable(selected: [running], inRun: [running],
                                           builtWithDSF: []).isEmpty)
    }

    func testAnAirportListBuildsEveryTile() {
        let list: Set<Tile> = [running, built, fresh]
        XCTAssertEqual(BuildModel.buildable(selected: list, inRun: [], builtWithDSF: []),
                       [built, running, fresh].sorted())
        // The visible Skip switch (on demand off) still leaves built ones out.
        XCTAssertEqual(BuildModel.buildable(selected: list, inRun: [], builtWithDSF: [built]),
                       [running, fresh].sorted())
    }
}
