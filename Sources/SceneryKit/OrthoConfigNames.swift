import Foundation

/// This app's own config file names (#1229, owner RULINGS 2026-10-26c).
/// The engine twin is `Ortho4XP/src/O4_Config_Names.py`: the app reads and
/// writes `XPTerrainBuilder.cfg` (global, in the data root) and
/// `XPTerrainBuilder_±xx±yyy.cfg` (per tile, in the build folder), and
/// leaves Ortho4XP's `Ortho4XP.cfg` / `Ortho4XP_±xx±yyy.cfg` untouched.
public enum OrthoConfigNames {
    public static let globalFileName = "XPTerrainBuilder.cfg"
    public static let ortho4xpGlobalFileName = "Ortho4XP.cfg"

    /// `XPTerrainBuilder_+47+011.cfg`.
    public static func tileFileName(lat: Int, lon: Int) -> String {
        "XPTerrainBuilder_" + TileMath.key(lat: lat, lon: lon) + ".cfg"
    }

    /// Whether `root` is an Ortho4XP installation: Ortho4XP's launcher
    /// (`Ortho4XP*.py`) without this engine's `src/O4_Config_Names.py`
    /// beside it (`O4_Config_Names.is_ortho4xp_install`).
    public static func isOrtho4XPInstall(_ root: URL) -> Bool {
        let fm = FileManager.default
        let names = (try? fm.contentsOfDirectory(atPath: root.path)) ?? []
        guard names.contains(where: { $0.hasPrefix("Ortho4XP") && $0.hasSuffix(".py") })
        else { return false }
        let ours = root.appendingPathComponent("src/O4_Config_Names.py")
        return !fm.fileExists(atPath: ours.path)
    }

    /// The global one-time hand-over (`O4_Config_Names.adopt_global_cfg`):
    /// with no `XPTerrainBuilder.cfg` in `root`, COPY this app's earlier
    /// `Ortho4XP.cfg` to it, unless `root` is an Ortho4XP installation
    /// (whose config is ignored). Never overwrites; the original stays.
    /// Run before the first read, because the app reads the global before
    /// the engine has started. Returns true when it copied.
    @discardableResult
    public static func adoptGlobalConfig(in root: URL) -> Bool {
        let fm = FileManager.default
        let ours = root.appendingPathComponent(globalFileName)
        let theirs = root.appendingPathComponent(ortho4xpGlobalFileName)
        guard !fm.fileExists(atPath: ours.path),
              fm.fileExists(atPath: theirs.path),
              !isOrtho4XPInstall(root)
        else { return false }
        // copyItem refuses an existing destination: never an overwrite.
        return (try? fm.copyItem(at: theirs, to: ours)) != nil
    }
}
