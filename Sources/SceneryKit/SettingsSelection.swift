import Foundation

/// One setting's value across the map selection (#1549): the value every
/// selected tile shares, or a conflict.
public enum SelectionValue<Value: Equatable>: Equatable {
    case uniform(Value)
    /// The selected tiles disagree: there is no one value to show.
    case conflicting

    public var value: Value? {
        if case .uniform(let value) = self { return value }
        return nil
    }

    public var isConflicting: Bool { self == .conflicting }
}

/// What the Settings window shows for the map selection (#1549, owner
/// RULINGS 2026-10-28i and 28j). The Qt window reads the same rule from
/// `Ortho4XP/src/O4_Settings_Selection.py`; `tests/test_settings_selection.py`
/// holds the two to the same words.
///
/// - No tile selected: the global defaults; an edit changes the defaults
///   for NEW tiles only (28j 3).
/// - One tile, or several that agree: their value; an edit applies to
///   every selected tile.
/// - Several tiles that disagree: the control shows `conflictText`, and
///   any per-tile change asks (`confirmMessage`) before it applies to all.
/// - A never-built tile counts as having the current global defaults
///   (28j 2): a tile without its own value inherits the global one.
/// - Only the per-tile build settings follow the selection; app-wide
///   settings stay global (28j 1, `editsTiles`).
public enum SettingsSelection {
    public static let conflictText = "Conflicting values"
    public static let confirmTitle = "Apply to all selected tiles?"
    public static let confirmButton = "Apply to All"
    /// The preset cards' note while tiles are selected.
    public static let tilesNote = "Applies to the selected tiles. With no tile selected it sets the defaults for new tiles."

    /// One value for the selection: the shared one, `.conflicting` when
    /// two differ, nil for an empty selection.
    public static func merge<Value: Equatable>(
        _ values: [Value], same: (Value, Value) -> Bool = { $0 == $1 }
    ) -> SelectionValue<Value>? {
        guard let first = values.first else { return nil }
        for value in values.dropFirst() where !same(first, value) {
            return .conflicting
        }
        return .uniform(first)
    }

    /// The selection's value of one tile setting. `tiles`: each selected
    /// tile's own saved values (a never-built tile has none); `inherited`:
    /// the global effective value.
    public static func tileValue<Value: Equatable>(
        _ tiles: [[String: Value]], name: String, inherited: Value?,
        same: (Value, Value) -> Bool = { $0 == $1 }
    ) -> SelectionValue<Value>? {
        let values = tiles.compactMap { $0[name] ?? inherited }
        guard values.count == tiles.count else {
            // A tile with no value and no default: nothing to compare.
            return values.isEmpty ? nil : .conflicting
        }
        return merge(values, same: same)
    }

    /// The selection's detail level: each tile's recorded zoom, a
    /// never-built tile (nil) the default; no selection, the default.
    public static func zoom(recorded: [Int?], default defaultZL: Int) -> SelectionValue<Int> {
        merge(recorded.map { $0 ?? defaultZL }) ?? .uniform(defaultZL)
    }

    /// Whether an edit of a tile-scope (`isTileScope`) or app-wide setting
    /// writes the selected tiles rather than the global layer.
    public static func editsTiles(isTileScope: Bool, tileCount: Int) -> Bool {
        isTileScope && tileCount > 0
    }

    /// What the window is editing: the defaults, a tile, or N tiles.
    public static func scopeText(tileNames: [String], conflicting: Bool) -> String {
        if tileNames.isEmpty { return "Editing the global defaults for new tiles" }
        var text = tileNames.count == 1
            ? "Editing tile \(tileNames[0])" : "Editing \(tileNames.count) tiles"
        if conflicting { text += " · " + conflictText.lowercased() }
        return text
    }

    /// The confirmation a change asks for while the tiles disagree.
    public static func confirmMessage(tileCount: Int) -> String {
        "The \(tileCount) selected tiles have different settings. Apply this change to all of them?"
    }
}
