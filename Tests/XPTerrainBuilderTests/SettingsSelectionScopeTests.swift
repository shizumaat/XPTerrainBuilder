import Testing
@testable import XPTerrainBuilder
@testable import SceneryKit

/// #1549 (RULINGS 2026-10-28j (1)): only the per-tile build settings follow
/// the map selection; app-wide ones (folders, accounts, appearance) stay
/// global. Qt twin: tests/test_qt_settings_selection.py.
struct SettingsSelectionScopeTests {
    @Test func theSelectionFollowsTileSettingsOnly() {
        let names = Set(BuildModel.tileScopeNames)
        for name in ["cover_airports_with_highres", "cover_zl", "cover_extent"] {
            #expect(names.contains(name))
        }
        for name in ["custom_scenery_dir", "cifp_data_path", "max_build_slots"] {
            #expect(!names.contains(name))
        }
    }

    @Test func presetKeysAreTileSettingsOrTheZoom() {
        for preset in SettingsPresets.presets {
            for name in preset.values.keys where name != SettingsPresets.zoomKey {
                #expect(BuildModel.tileScopeNames.contains(name))
            }
        }
    }
}
