import Testing
@testable import SceneryKit

/// #1549 (RULINGS 2026-10-28i/j): what the Settings window shows for the
/// map selection. Qt twins: tests/test_settings_selection.py (the rule and
/// its words) and tests/test_qt_settings_selection.py (the window).
struct SettingsSelectionTests {
    private let inherited: O4Value = .int(3)

    @Test func noSelectionIsTheDefaults() {
        #expect(SettingsSelection.tileValue([], name: "road_level", inherited: inherited) == nil)
        #expect(SettingsSelection.zoom(recorded: [], default: 16) == .uniform(16))
        #expect(!SettingsSelection.editsTiles(isTileScope: true, tileCount: 0))
        #expect(SettingsSelection.scopeText(tileNames: [], conflicting: false)
                == "Editing the global defaults for new tiles")
    }

    @Test func oneTileShowsItsOwnValue() {
        let tiles: [[String: O4Value]] = [["road_level": .int(5)]]
        #expect(SettingsSelection.tileValue(tiles, name: "road_level", inherited: inherited)
                == .uniform(.int(5)))
        #expect(SettingsSelection.zoom(recorded: [17], default: 16) == .uniform(17))
        #expect(SettingsSelection.editsTiles(isTileScope: true, tileCount: 1))
        #expect(SettingsSelection.scopeText(tileNames: ["+48-006"], conflicting: false)
                == "Editing tile +48-006")
    }

    @Test func matchingTilesLookLikeOne() {
        let tiles: [[String: O4Value]] = [["road_level": .int(5)], ["road_level": .int(5)]]
        #expect(SettingsSelection.tileValue(tiles, name: "road_level", inherited: inherited)
                == .uniform(.int(5)))
        #expect(SettingsSelection.zoom(recorded: [17, 17], default: 16) == .uniform(17))
        #expect(SettingsSelection.scopeText(tileNames: ["+48-006", "+49-006"], conflicting: false)
                == "Editing 2 tiles")
    }

    @Test func conflictingTilesConflictAndAsk() {
        let tiles: [[String: O4Value]] = [["road_level": .int(5)], [:]]
        let value = SettingsSelection.tileValue(tiles, name: "road_level", inherited: inherited)
        #expect(value == .conflicting)
        #expect(value?.isConflicting == true && value?.value == nil)
        #expect(SettingsSelection.zoom(recorded: [16, 17], default: 16) == .conflicting)
        #expect(SettingsSelection.scopeText(tileNames: ["+48-006", "+49-006"], conflicting: true)
                == "Editing 2 tiles · conflicting values")
        #expect(SettingsSelection.confirmMessage(tileCount: 2)
                == "The 2 selected tiles have different settings. Apply this change to all of them?")
    }

    @Test func numbersCompareByValueWhenAsked() {
        let tiles: [[String: O4Value]] = [["cover_extent": .int(1)], ["cover_extent": .double(1.0)]]
        let same: (O4Value, O4Value) -> Bool = { first, second in
            if case .int(let a) = first, case .double(let b) = second { return Double(a) == b }
            return first == second
        }
        #expect(SettingsSelection.tileValue(tiles, name: "cover_extent", inherited: nil, same: same)
                == .uniform(.int(1)))
    }

    @Test func aNeverBuiltTileCountsAsTheDefaults() {
        let agree: [[String: O4Value]] = [["road_level": .int(3)], [:]]
        #expect(SettingsSelection.tileValue(agree, name: "road_level", inherited: inherited)
                == .uniform(.int(3)))
        let differ: [[String: O4Value]] = [["road_level": .int(4)], [:]]
        #expect(SettingsSelection.tileValue(differ, name: "road_level", inherited: inherited)
                == .conflicting)
        #expect(SettingsSelection.zoom(recorded: [16, nil], default: 16) == .uniform(16))
        #expect(SettingsSelection.zoom(recorded: [17, nil], default: 16) == .conflicting)
    }

    @Test func appWideSettingsStayGlobal() {
        #expect(!SettingsSelection.editsTiles(isTileScope: false, tileCount: 3))
    }
}
