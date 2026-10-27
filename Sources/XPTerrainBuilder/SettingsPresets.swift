import SwiftUI
import SceneryKit

/// The settings presets (issue #822), mirroring the Qt app's table
/// (O4_Settings_Presets.PRESETS) row for row —
/// `Ortho4XP/tests/test_settings_presets.py` parses this file and fails
/// when the two differ. Every preset writes the SAME keys: the build zoom
/// (`zl`, kept here as `@AppStorage("OrthoZoomLevel")`) and three engine
/// config keys, written to the global config (the defaults for new tiles).
/// The figures in `cost` are derived, never measured: see docs/presets.md.
struct SettingsPreset: Identifiable, Equatable {
    let key: String
    let title: String
    let summary: String
    let cost: String
    /// Preset key → cfg literal (as the engine writes it).
    let values: [String: String]
    var id: String { key }

    init(_ key: String, _ title: String, summary: String, cost: String,
         values: [String: String]) {
        self.key = key
        self.title = title
        self.summary = summary
        self.cost = cost
        self.values = values
    }
}

enum SettingsPresets {
    /// The build-zoom key (Qt prefs["zl"]); the Mac app stores it as
    /// `BuildModel.defaultZL` (the next build reads `buildZL`, #1539).
    static let zoomKey = "zl"
    static let sectionTitle = "Start from"
    static let sectionNote = "Sets the defaults for new tiles. Settings you change afterwards show as Custom."
    static let customTitle = "Custom"

    static let presets: [SettingsPreset] = [
        SettingsPreset("light_on_disk", "Light on disk",
                       summary: "ZL15 everywhere: coarser imagery, smaller downloads.",
                       cost: "About 0.4–0.8 GB of imagery per tile, a quarter of Balanced.",
                       values: ["zl": "15", "cover_airports_with_highres": "False", "cover_zl": "18", "cover_extent": "1.0"]),
        SettingsPreset("balanced", "Balanced",
                       summary: "The standard settings: ZL16 everywhere.",
                       cost: "About 1.6–3.1 GB of imagery per tile.",
                       values: ["zl": "16", "cover_airports_with_highres": "False", "cover_zl": "18", "cover_extent": "1.0"]),
        SettingsPreset("sharper_airports", "Sharper airports",
                       summary: "ZL16, and ZL18 imagery on and around airports with ICAO codes.",
                       cost: "About 1.6–3.1 GB per tile, plus the sharper airports.",
                       values: ["zl": "16", "cover_airports_with_highres": "ICAO", "cover_zl": "18", "cover_extent": "1.0"]),
    ]

    /// The preset a new user starts from (#937; Qt DEFAULT_PRESET).
    static let defaultKey = "sharper_airports"

    static var defaultPreset: SettingsPreset? {
        presets.first { $0.key == defaultKey }
    }

    /// Numbers compare by value (`1` and `1.0` are one cover_extent).
    static func same(_ first: O4Value, _ second: O4Value) -> Bool {
        if let a = number(first), let b = number(second) { return a == b }
        return first == second
    }

    private static func number(_ value: O4Value) -> Double? {
        switch value {
        case .int(let i): return Double(i)
        case .double(let d): return d
        default: return nil
        }
    }
}

extension BuildModel {
    /// Whether every key of `preset` holds its value now: the selected
    /// tiles' values when `followsSelection` and tiles are selected
    /// (#1549; a conflicting key matches nothing), else the global config
    /// and the build zoom. A key this engine's schema does not know
    /// cannot differ.
    func presetMatches(_ preset: SettingsPreset, followsSelection: Bool = true) -> Bool {
        let tiles = followsSelection && !selected.isEmpty ? selectedTileValues() : nil
        return preset.values.allSatisfy { name, raw in
            if name == SettingsPresets.zoomKey {
                let zl = tiles == nil ? (followsSelection ? buildZL : defaultZL)
                                      : selectionZoom.value
                return Int(raw) == zl
            }
            guard let variable = schema.vars[name],
                  let wanted = O4Value.parse(raw, typeName: variable.type) else { return true }
            let current: O4Value?
            if let tiles {
                guard let merged = selectionValue(for: name, in: tiles) else { return true }
                guard let value = merged.value else { return false }
                current = value
            } else {
                current = configValue(for: name)
            }
            guard let current else { return true }
            return SettingsPresets.same(current, wanted)
        }
    }

    func currentPreset(followsSelection: Bool = true) -> SettingsPreset? {
        SettingsPresets.presets.first { presetMatches($0, followsSelection: followsSelection) }
    }

    /// First run (#937): when the global config sets none of the preset
    /// keys yet, start from the default preset (Qt parity:
    /// O4_Settings_Presets.unset_in). The engine's own defaults stay
    /// Balanced, so builds outside the app are unchanged.
    func applyDefaultPresetIfUnset() {
        guard engine != nil, let preset = SettingsPresets.defaultPreset,
              !preset.values.keys.contains(where: { globalConfigValues[$0] != nil })
        else { return }
        applyPresetToDefaults(preset)
    }

    /// A card's Use: with tiles selected (and `followsSelection`), to every
    /// selected tile — its config keys as their values, its zoom as theirs
    /// — after the user's yes while they disagree (#1549); else to the
    /// defaults for new tiles.
    func applyPreset(_ preset: SettingsPreset, followsSelection: Bool = true) {
        guard followsSelection, !selected.isEmpty else {
            applyPresetToDefaults(preset)
            return
        }
        editSelection { [weak self] in
            guard let self else { return }
            for (name, raw) in preset.values.sorted(by: { $0.key < $1.key }) {
                if name == SettingsPresets.zoomKey {
                    if let zoom = Int(raw) { self.chooseZoom(zoom) }
                } else if let variable = self.schema.vars[name],
                          let value = O4Value.parse(raw, typeName: variable.type) {
                    self.writeThroughToSelectedTiles(name, value)
                }
            }
        }
    }

    /// The defaults for new tiles: the zoom to the default detail level,
    /// the rest to the global config.
    func applyPresetToDefaults(_ preset: SettingsPreset) {
        for (name, raw) in preset.values.sorted(by: { $0.key < $1.key }) {
            if name == SettingsPresets.zoomKey {
                if let zoom = Int(raw) {
                    objectWillChange.send()
                    buildZL = zoom
                }
            } else if let variable = schema.vars[name],
                      let value = O4Value.parse(raw, typeName: variable.type) {
                setConfigValue(name, to: value)
            }
        }
    }
}

/// The three preset cards with a "Current: …" line, in Settings ▸ General
/// (following the map selection, #1549) and on the first-run screen (the
/// defaults for new tiles: `followsSelection: false`).
struct PresetCardsView: View {
    @EnvironmentObject var buildModel: BuildModel
    var followsSelection = true

    private var appliesToTiles: Bool { followsSelection && !buildModel.selected.isEmpty }

    var body: some View {
        let _ = buildModel.tileConfigGeneration
        let current = buildModel.currentPreset(followsSelection: followsSelection)
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(SettingsPresets.sectionTitle).font(.headline)
                Spacer()
                Text("Current: \(current?.title ?? SettingsPresets.customTitle)")
                    .foregroundStyle(.secondary)
            }
            HStack(alignment: .top, spacing: 10) {
                ForEach(SettingsPresets.presets) { preset in
                    card(preset, isCurrent: preset.key == current?.key)
                }
            }
            Text(appliesToTiles ? SettingsSelection.tilesNote : SettingsPresets.sectionNote)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }

    private func card(_ preset: SettingsPreset, isCurrent: Bool) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(preset.title).font(.body.weight(.semibold))
            Text(preset.summary)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
            Text(preset.cost)
                .font(.caption)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 4)
            Button("Use") { buildModel.applyPreset(preset, followsSelection: followsSelection) }
                .disabled(isCurrent)
                .help("Use the \(preset.title) settings")
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .topLeading)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .strokeBorder(isCurrent ? Color.accentColor : Color.secondary.opacity(0.4),
                              lineWidth: isCurrent ? 2 : 1)
        )
    }
}
