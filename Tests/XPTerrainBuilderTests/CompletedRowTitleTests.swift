import AppKit
import SwiftUI
import XCTest
@testable import XPTerrainBuilder

/// A built tile's Activity title (#1542): the dimmed colour 50 % of the
/// way to white. The Qt twin is `Ortho4XP/tests/test_qt_activity_keep.py`
/// (`test_a_done_row_is_compact`).
final class CompletedRowTitleTests: XCTestCase {
    func testHalfwayToWhite() {
        let gray = NSColor(srgbRed: 0.5, green: 0.2, blue: 0.0, alpha: 0.8)
        let out = TileProgressRowLines<EmptyView, EmptyView>.halfwayToWhite(gray)
        XCTAssertEqual(out.redComponent, 0.75, accuracy: 1e-6)
        XCTAssertEqual(out.greenComponent, 0.6, accuracy: 1e-6)
        XCTAssertEqual(out.blueComponent, 0.5, accuracy: 1e-6)
        XCTAssertEqual(out.alphaComponent, 0.8, accuracy: 1e-6)
    }
}
