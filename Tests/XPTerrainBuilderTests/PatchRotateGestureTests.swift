import XCTest
import AppKit
@testable import XPTerrainBuilder

/// ⌥-drag's angle (#1746; the Qt twin is `PatchGestures.rotation`, run by
/// `test_alt_drag_on_a_node_rotates_its_shape_in_one_undo_step`): screen y
/// points down, so a visually counter-clockwise drag is a positive angle.
final class PatchRotateGestureTests: XCTestCase {
    func testAVisuallyCounterClockwiseQuarterIsPlusNinety() {
        let pivot = CGPoint(x: 100, y: 100)
        let east = CGPoint(x: 150, y: 100), north = CGPoint(x: 100, y: 50)
        XCTAssertEqual(PatchDragState.rotation(from: east, to: north, about: pivot), 90, accuracy: 1e-9)
        XCTAssertEqual(PatchDragState.rotation(from: north, to: east, about: pivot), -90, accuracy: 1e-9)
    }

    func testTheAngleWrapsToAHalfTurn() {
        let pivot = CGPoint.zero
        let a = CGPoint(x: -10, y: 1), b = CGPoint(x: -10, y: -1)  // across the ±180° seam
        XCTAssertLessThan(abs(PatchDragState.rotation(from: a, to: b, about: pivot)), 20)
    }

    func testTheRotateCursorIsDrawn() {
        XCTAssertEqual(NSCursor.patchRotate.hotSpot, NSPoint(x: 12, y: 12))
        XCTAssertEqual(NSCursor.patchRotate.image.size, NSSize(width: 24, height: 24))
    }
}
