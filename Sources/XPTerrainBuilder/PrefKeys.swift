import Foundation

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
}
