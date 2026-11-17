import XCTest
import SwiftUI
import SceneryKit
@testable import XPTerrainBuilder

/// Owner 2026-11-17T16:04Z: a selected Activity row is filled with the
/// accent colour and its progress bar (accent fill) vanished. On an
/// emphasized row (`backgroundProminence == .increased`) the bar, the
/// status and the running step draw white; elsewhere they keep their
/// colours.
final class SelectedRowStyleTests: XCTestCase {
    func testEmphasizedRowDrawsColouredContentWhite() {
        XCTAssertEqual(SelectedRowStyle.tint(.accentColor, .increased), .white)
        XCTAssertEqual(SelectedRowStyle.tint(.red, .increased), .white)
        XCTAssertEqual(SelectedRowStyle.tint(.accentColor, .standard), .accentColor)
        XCTAssertEqual(SelectedRowStyle.tint(.green, .standard), .green)
    }

    func testRunningStepIsNotAccentOnASelectedRow() {
        XCTAssertEqual(TileStepStrip.color(.running), .accentColor)
        XCTAssertEqual(TileStepStrip.emphasizedColor(.running), .white)
        XCTAssertEqual(TileStepStrip.emphasizedColor(.done), .white)
        XCTAssertEqual(TileStepStrip.emphasizedColor(.waiting), .secondary)
    }

    func testRowsGetTheMediumSidebarSpacing() {
        XCTAssertEqual(SelectedRowStyle.rowVerticalPadding, 2)
    }
}
