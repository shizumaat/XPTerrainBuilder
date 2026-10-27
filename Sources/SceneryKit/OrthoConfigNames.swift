import Foundation

/// This app's own config file names (#1229, owner RULINGS 2026-10-26c).
/// The engine twin is `Ortho4XP/src/O4_Config_Names.py`: the app reads and
/// writes `XPTerrainBuilder.cfg` (global, in the data root) and
/// `XPTerrainBuilder_±xx±yyy.cfg` (per tile, in the build folder), and
/// leaves Ortho4XP's `Ortho4XP.cfg` / `Ortho4XP_±xx±yyy.cfg` untouched:
/// the global is never copied over (owner Q176 "B"), so a data root
/// without `XPTerrainBuilder.cfg` starts from defaults.
public enum OrthoConfigNames {
    public static let globalFileName = "XPTerrainBuilder.cfg"

    /// `XPTerrainBuilder_+47+011.cfg`.
    public static func tileFileName(lat: Int, lon: Int) -> String {
        "XPTerrainBuilder_" + TileMath.key(lat: lat, lon: lon) + ".cfg"
    }
}
