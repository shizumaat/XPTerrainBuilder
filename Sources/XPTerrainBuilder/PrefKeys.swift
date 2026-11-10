import Foundation
import SceneryKit

/// UserDefaults keys for the app's own preferences. They live in the
/// standard preferences plist
/// (~/Library/Preferences/com.novemberlima.XPTerrainBuilder.plist when run
/// from the bundle).
enum PrefKeys {
    /// The X-Plane root path.
    static let xplanePath = "XPlanePath"
    /// Where downloads, caches and built tiles live (ORTHO4XP_DATA_ROOT).
    /// Empty until the first-run prompt has been answered.
    static let dataRoot = "DataRootPath"
    /// The build map's selected set, as canonical tile keys
    /// (`TileMath.key`, e.g. "+35-081"), sorted by (lat, lon).
    static let selectedTiles = "SelectedTiles"
    /// The build map's active tile, one canonical tile key.
    /// Absent or empty = no active tile.
    static let activeTile = "ActiveTileKey"
    /// The map's first-visit hint was dismissed (#828) — the Qt prefs
    /// key's string (`MapGuidance.hintDismissedKey`).
    static let mapHintDismissed = MapGuidance.hintDismissedKey
    /// The last app mode, Build · Fly · Library (RULINGS 2026-11-10j);
    /// the Qt prefs key is `app_mode` (`O4_App_Modes.PREF_KEY`).
    static let appMode = "AppMode"
}
