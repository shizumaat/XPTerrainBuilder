import XCTest
@testable import XPTerrainBuilder

/// #2214: a click on the map jumped back to the airport looked at before.
/// A drag SwiftUI cancels never reaches `onEnded`, so the pan anchor it
/// left (the old airport's view) was resumed by the next gesture. Both
/// map pans — the base map's and the patch Edit layer's — now take a
/// gesture's anchor only from that gesture. (Qt pans by the last move's
/// delta and resets on every press, so it never carried an anchor.)
@MainActor
final class MapPanAnchorTests: XCTestCase {
    private func camera(lat: Double, lon: Double) -> MapCamera {
        var cam = MapCamera()
        cam.centerLat = lat
        cam.centerLon = lon
        cam.scale = 40_000
        return cam
    }

    func testANewDragAnchorsOnTheViewNowNotTheLeftOverOne() {
        let before = camera(lat: 35.87, lon: -82.35)   // the airport inspected first
        let now = camera(lat: 35.88, lon: -78.79)      // the airport zoomed into since
        let leftOver = MapPanAnchor(start: CGPoint(x: 200, y: 300), camera: before)
        let next = MapPanAnchor.current(leftOver, start: CGPoint(x: 410, y: 120), camera: now)
        XCTAssertEqual(next.camera, now)
        XCTAssertEqual(next.start, CGPoint(x: 410, y: 120))
    }

    func testTheSameDragKeepsItsAnchorAsTheCameraMoves() {
        let start = CGPoint(x: 200, y: 300)
        let anchor = MapPanAnchor(start: start, camera: camera(lat: 1, lon: 2))
        let moved = camera(lat: 1.01, lon: 2.02)
        XCTAssertEqual(MapPanAnchor.current(anchor, start: start, camera: moved), anchor)
        XCTAssertEqual(MapPanAnchor.current(nil, start: start, camera: moved).camera, moved)
    }

    func testTheEditLayerDoesNotResumeADroppedPan() {
        let drag = PatchDragState()
        XCTAssertFalse(drag.isLeftOver(gestureStart: CGPoint(x: 5, y: 5)))   // idle
        drag.start = CGPoint(x: 200, y: 300)
        drag.kind = .pan(anchor: camera(lat: 35.87, lon: -82.35))
        XCTAssertFalse(drag.isLeftOver(gestureStart: CGPoint(x: 200, y: 300)))  // its own gesture
        XCTAssertTrue(drag.isLeftOver(gestureStart: CGPoint(x: 410, y: 120)))   // a later click
    }
}
