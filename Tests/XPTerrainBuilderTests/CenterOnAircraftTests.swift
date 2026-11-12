import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// The map's "Center on aircraft" button (#2016): current only while a
/// position is younger than `FlyText.aircraftFreshS`; centering pans and
/// keeps the zoom. Qt twin: `tests/test_qt_map_controls.py`.
final class CenterOnAircraftTests: XCTestCase {
    func testCurrentOnlyWhileFresh() {
        let now = Date()
        XCTAssertFalse(FlyText.aircraftIsCurrent(seenAt: nil, now: now))
        XCTAssertTrue(FlyText.aircraftIsCurrent(seenAt: now.addingTimeInterval(-1), now: now))
        XCTAssertFalse(FlyText.aircraftIsCurrent(
            seenAt: now.addingTimeInterval(-FlyText.aircraftFreshS), now: now))
    }

    func testCenteringPansAndKeepsTheZoom() {
        let size = CGSize(width: 800, height: 600)
        var cam = MapCamera()
        cam.scale = 2000
        let moved = CenterOnAircraftButton.centered(cam, lat: 30.1, lon: 31.4, in: size)
        XCTAssertEqual(moved.centerLat, 30.1, accuracy: 1e-9)
        XCTAssertEqual(moved.centerLon, 31.4, accuracy: 1e-9)
        XCTAssertEqual(moved.scale, 2000)
    }
}
