import AppKit
import XCTest
@testable import XPTerrainBuilder

/// The toolbar search field scrolls long text instead of clipping it (#1224).
@MainActor
final class ToolbarSearchFieldTests: XCTestCase {
    func testLongTextScrollsInsteadOfClipping() throws {
        let field = ToolbarSearchField.makeField(placeholder: "Search")
        let cell = try XCTUnwrap(field.cell)
        XCTAssertTrue(cell.isScrollable)
        XCTAssertFalse(cell.wraps)
        XCTAssertTrue(field.usesSingleLineMode)
        XCTAssertEqual(field.placeholderString, "Search")
    }
}
