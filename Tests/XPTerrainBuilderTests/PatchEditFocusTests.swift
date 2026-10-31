import XCTest
import AppKit
@testable import XPTerrainBuilder

/// A selection in Edit mode takes keyboard focus from the search field so
/// Delete reaches it (#1693; the Qt twin is
/// `test_selecting_moves_focus_from_the_search_field_to_the_map`).
final class PatchEditFocusTests: XCTestCase {
    func testAnEditModeSelectionTakesFocus() {
        XCTAssertTrue(PatchEditModel.selectionTakesFocus(editing: true, showing: true, selected: true))
    }

    func testNoSelectionOrViewModeLeavesFocusAlone() {
        XCTAssertFalse(PatchEditModel.selectionTakesFocus(editing: true, showing: true, selected: false))
        XCTAssertFalse(PatchEditModel.selectionTakesFocus(editing: false, showing: true, selected: true))
        XCTAssertFalse(PatchEditModel.selectionTakesFocus(editing: true, showing: false, selected: true))
    }
}

/// ⌘S saves the edited patch (#1694; the Qt twin is
/// `test_ctrl_s_saves_the_patch_through_the_save_button_action`).
final class PatchSaveShortcutTests: XCTestCase {
    func testCommandSIsTheSaveShortcut() {
        XCTAssertTrue(PatchEditModel.isSaveShortcut("s", flags: .command))
        XCTAssertTrue(PatchEditModel.isSaveShortcut("S", flags: [.command, .capsLock]))
    }

    func testOtherChordsAreNot() {
        XCTAssertFalse(PatchEditModel.isSaveShortcut("s", flags: []))
        XCTAssertFalse(PatchEditModel.isSaveShortcut("s", flags: [.command, .shift]))
        XCTAssertFalse(PatchEditModel.isSaveShortcut("d", flags: .command))
    }
}
