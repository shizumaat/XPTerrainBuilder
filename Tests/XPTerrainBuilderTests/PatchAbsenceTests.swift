import XCTest
@testable import XPTerrainBuilder

/// "Build this tile first" only when the tile scan has finished and the
/// tile is not in it (1.0.433: a built SPJC read "not built" mid-scan).
final class PatchAbsenceTests: XCTestCase {
    func testAScanStillRunningSaysChecking() {
        XCTAssertEqual(PatchEditModel.absence(icao: "SPJC", built: false, scanning: true),
                       .checking(icao: "SPJC"))
    }

    func testAFinishedScanSaysBuildFirst() {
        XCTAssertEqual(PatchEditModel.absence(icao: "SPJC", built: false, scanning: false),
                       .noPatch(icao: "SPJC", tileBuilt: false))
    }

    func testABuiltTileIsBuiltWhileScanning() {
        XCTAssertEqual(PatchEditModel.absence(icao: "SPJC", built: true, scanning: true),
                       .noPatch(icao: "SPJC", tileBuilt: true))
    }
}
