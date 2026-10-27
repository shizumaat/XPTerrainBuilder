import Foundation
import SceneryKit

/// A per-tile Settings change waiting for the user's yes (#1549): the
/// selected tiles disagree, so it would overwrite their different values.
struct PendingSelectionEdit: Identifiable {
    let id = UUID()
    let tileCount: Int
    let apply: () -> Void
}

/// The Settings window follows the map selection (#1549, owner RULINGS
/// 2026-10-28i and 28j; the rule is `SceneryKit.SettingsSelection`, the
/// Qt window's `O4_Qt_Settings_Selection`). Each tile's own settings are
/// its tile cfg's overrides (read where `overrideState` reads them) and
/// its recorded zoom; a never-built tile has neither and counts as the
/// global defaults.
extension BuildModel {
    /// The settings the selection follows: the tile-scope rows. App-wide
    /// rows (data folders, accounts, appearance) stay global (28j 1).
    static let tileScopeNames: [String] = SettingsLayout.categories
        .flatMap(\.items).filter { $0.scope == .tile }.map(\.name)

    /// Each selected tile's own saved values (a never-built tile: none).
    func selectedTileValues() -> [[String: O4Value]] {
        selected.sorted().map { coord in
            guard let url = tileConfigURL(coord),
                  let file = try? OrthoConfigFile(contentsOf: url) else { return [:] }
            return file.values(schema: schema)
        }
    }

    /// The selection's value of one tile setting, or `.conflicting`.
    func selectionValue(for name: String,
                        in tiles: [[String: O4Value]]? = nil) -> SelectionValue<O4Value>? {
        SettingsSelection.tileValue(tiles ?? selectedTileValues(), name: name,
                                    inherited: configValue(for: name),
                                    same: SettingsPresets.same)
    }

    /// Whether this row's control shows "Conflicting values".
    func isConflicting(_ item: SettingItem) -> Bool {
        item.scope == .tile && selected.count > 1
            && selectionValue(for: item.name)?.isConflicting == true
    }

    /// A tile's recorded detail level (nil: never built). A detected
    /// source that did not answer the launch check is not adopted (#1345).
    func recordedZL(_ coord: TileCoord) -> Int? {
        guard let choice = built[coord].flatMap(TileImageryChoice.resolve) else { return nil }
        if choice.source == .detected, imageryStatus[choice.provider]?.status == "offline" {
            return nil
        }
        return choice.zl
    }

    /// The detail level Settings shows: the default with nothing selected,
    /// else a zoom chosen for this selection, else the selection's own.
    var selectionZoom: SelectionValue<Int> {
        if selected.isEmpty { return .uniform(defaultZL) }
        if let choice = zoom.selectionChoice { return .uniform(choice) }
        return SettingsSelection.zoom(recorded: selected.sorted().map(recordedZL),
                                      default: defaultZL)
    }

    /// Whether the selected tiles disagree on any per-tile setting.
    var selectionConflicts: Bool {
        guard selected.count > 1 else { return false }
        if selectionZoom.isConflicting { return true }
        let tiles = selectedTileValues()
        return Self.tileScopeNames.contains { name in
            schema.vars[name] != nil
                && selectionValue(for: name, in: tiles)?.isConflicting == true
        }
    }

    /// Runs a per-tile change now, or — while the selected tiles disagree —
    /// once the user confirms it (the Settings window's alert).
    func editSelection(_ apply: @escaping () -> Void) {
        if selectionConflicts {
            pendingSelectionEdit = PendingSelectionEdit(tileCount: selected.count, apply: apply)
        } else {
            apply()
        }
    }

    func confirmPendingSelectionEdit() {
        let pending = pendingSelectionEdit
        pendingSelectionEdit = nil
        pending?.apply()
    }

    /// Settings' Detail picker: the default for new tiles with nothing
    /// selected (28j 3), else the selected tiles' next build.
    func chooseZoom(_ zl: Int) {
        objectWillChange.send()
        if selected.isEmpty {
            buildZL = zl
        } else {
            zoom.chooseForSelection(zl)
        }
    }

    /// The Settings window's subtitle: what an edit changes.
    var settingsScopeText: String {
        SettingsSelection.scopeText(tileNames: selected.sorted().map(\.key),
                                    conflicting: selectionConflicts)
    }
}
