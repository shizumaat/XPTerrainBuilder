import XCTest
@testable import XPTerrainBuilder

/// An airport whose patch spans several tiles shows every tile's patch
/// (#1646; the Qt twin is `Ortho4XP/tests/test_qt_patch_multi_tile.py`).
final class PatchSiblingTests: XCTestCase {
    func testOtherTilesOfTheShownAirportAreSiblings() {
        let candidates = [("+33-112", "KPHX"), ("+33-113", "KPHX"), ("+33-113", "KXYZ")]
        XCTAssertEqual(PatchEditModel.siblingIndices(candidates, tile: "+33-112", icao: "KPHX"), [1])
    }

    func testASingleTileAirportHasNoSiblings() {
        XCTAssertEqual(PatchEditModel.siblingIndices([("+33-112", "KPHX")], tile: "+33-112", icao: "KPHX"), [])
    }
}
