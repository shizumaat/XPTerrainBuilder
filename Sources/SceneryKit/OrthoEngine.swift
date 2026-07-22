import Foundation

/// A dropped-in Ortho4XP engine: any checkout/release of the engine repo,
/// identified by its root folder. The app never modifies the engine — all
/// coupling goes through the driver script (o4_driver.py) and the engine's
/// own config files, so replacing the folder with a newer engine version is
/// the whole upgrade story. (Automatic GitHub fetch can later produce these
/// folders; everything downstream only needs a valid root.)
public struct OrthoEngine: Sendable, Equatable {
    public let root: URL
    /// From src/O4_Version.py (checkout) or VERSION.txt (frozen).
    public let version: String
    /// A PyInstaller-frozen engine: self-contained executable with its own
    /// Python runtime in _internal/ — nothing for the user to install.
    public let isFrozen: Bool

    /// The frozen engine's executable name (PyInstaller onedir output).
    public static var frozenExecutableName: String {
        #if os(Windows)
        return "Ortho4XP.exe"
        #else
        return "Ortho4XP"
        #endif
    }

    /// Validates a folder as an Ortho4XP engine root and reads its version.
    /// Accepts either a source checkout (Ortho4XP.py + src/) or a frozen
    /// engine (the PyInstaller onedir layout the release build ships).
    /// Returns nil when the folder doesn't look like an engine.
    public static func locate(at root: URL) -> OrthoEngine? {
        let fm = FileManager.default
        if fm.fileExists(atPath: root.appendingPathComponent("Ortho4XP.py").path),
           fm.fileExists(atPath: root.appendingPathComponent("src").path) {
            return OrthoEngine(root: root, version: Self.readVersion(root: root) ?? "unknown",
                               isFrozen: false)
        }
        if fm.isExecutableFile(atPath: root.appendingPathComponent(frozenExecutableName).path),
           fm.fileExists(atPath: root.appendingPathComponent("_internal/Ortho4XP_Data").path) {
            return OrthoEngine(root: root, version: Self.readVersion(root: root) ?? "unknown",
                               isFrozen: true)
        }
        return nil
    }

    /// The engine copy shipped with the app — the default engine. On macOS
    /// it lives inside the bundle (Contents/Resources/Engine); on Windows
    /// and Linux, in an Engine folder next to the executable. Running from
    /// a source checkout (swift run, tests) falls back to the repo's
    /// vendored Ortho4XP/.
    public static func bundled() -> OrthoEngine? {
        var candidates: [URL] = []
        if let resources = Bundle.main.resourceURL {
            candidates.append(resources.appendingPathComponent("Engine", isDirectory: true))
        }
        if let executable = Bundle.main.executableURL?.resolvingSymlinksInPath() {
            candidates.append(executable.deletingLastPathComponent()
                .appendingPathComponent("Engine", isDirectory: true))
        }
        candidates.append(URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
            .appendingPathComponent("Ortho4XP", isDirectory: true))
        for candidate in candidates {
            if let engine = locate(at: candidate) { return engine }
        }
        return nil
    }

    static func readVersion(root: URL) -> String? {
        let url = root.appendingPathComponent("src/O4_Version.py")
        if let text = try? String(contentsOf: url, encoding: .utf8) {
            for line in text.components(separatedBy: .newlines) {
                guard let eq = line.firstIndex(of: "=") else { continue }
                guard line[..<eq].trimmingCharacters(in: .whitespaces) == "version" else { continue }
                let value = line[line.index(after: eq)...]
                    .trimmingCharacters(in: .whitespaces)
                    .trimmingCharacters(in: CharacterSet(charactersIn: "'\""))
                if !value.isEmpty { return value }
            }
        }
        // Frozen engines carry a VERSION.txt written by the freeze script.
        if let text = try? String(contentsOf: root.appendingPathComponent("VERSION.txt"),
                                  encoding: .utf8) {
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            if !trimmed.isEmpty { return trimmed }
        }
        return nil
    }

    /// The frozen engine's executable; nil for source checkouts, which
    /// launch through python.
    public var frozenExecutableURL: URL? {
        isFrozen ? root.appendingPathComponent(Self.frozenExecutableName) : nil
    }

    /// Read-only engine resources (Providers, Extents, Filters, …): the
    /// checkout root, or the PyInstaller data directory inside a frozen
    /// engine.
    public var resourcesRoot: URL {
        isFrozen ? root.appendingPathComponent("_internal/Ortho4XP_Data", isDirectory: true) : root
    }

    /// The python to run the engine with: its own venv when the install
    /// script created one, otherwise the system python3.
    public var pythonURL: URL {
        let venv = root.appendingPathComponent("venv/bin/python3")
        if FileManager.default.fileExists(atPath: venv.path) { return venv }
        return URL(fileURLWithPath: "/usr/bin/python3")
    }

    public var hasVenv: Bool {
        FileManager.default.fileExists(atPath: root.appendingPathComponent("venv/bin/python3").path)
    }

    /// Global config file (created by the engine on first import if absent).
    /// With a data root set, the engine reads and writes it there
    /// (ORTHO4XP_DATA_ROOT); otherwise it lives in the engine folder — the
    /// engine's own source-checkout behavior.
    public func globalConfigURL(dataRoot: URL?) -> URL {
        (dataRoot ?? root).appendingPathComponent("Ortho4XP.cfg")
    }

    public var globalConfigURL: URL {
        globalConfigURL(dataRoot: nil)
    }

    /// Default tile output folder when no custom build dir is configured.
    public var tilesDirectory: URL {
        root.appendingPathComponent("Tiles")
    }

    public var installScriptURL: URL {
        root.appendingPathComponent("install_mac.sh")
    }

    // MARK: - Providers

    /// An imagery source the engine can download from: a single provider
    /// (Providers/<Region>/<CODE>.lay) or a combined one (Providers/<CODE>.comb).
    public struct Provider: Sendable, Equatable, Identifiable {
        public let code: String
        /// Region folder for single providers; nil for combined.
        public let region: String?
        public let isCombined: Bool
        public var id: String { code }

        public init(code: String, region: String?, isCombined: Bool) {
            self.code = code
            self.region = region
            self.isCombined = isCombined
        }
    }

    /// Enumerates providers the same way the engine's GUI dropdown does —
    /// every .lay not flagged in_GUI=False plus every .comb, minus the
    /// internal OSM/SEA layers — but from the filesystem, so no python is
    /// needed just to fill a picker.
    public func providers() -> [Provider] {
        Self.providers(inProvidersDirectory: resourcesRoot.appendingPathComponent("Providers"))
    }

    public static func providers(inProvidersDirectory dir: URL) -> [Provider] {
        let fm = FileManager.default
        var found: [Provider] = []
        let entries = (try? fm.contentsOfDirectory(at: dir, includingPropertiesForKeys: [.isDirectoryKey])) ?? []
        for entry in entries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            if entry.pathExtension == "comb" {
                found.append(Provider(code: entry.deletingPathExtension().lastPathComponent,
                                      region: nil, isCombined: true))
                continue
            }
            guard (try? entry.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true
            else { continue }
            let region = entry.lastPathComponent
            let lays = (try? fm.contentsOfDirectory(at: entry, includingPropertiesForKeys: nil)) ?? []
            for lay in lays.sorted(by: { $0.lastPathComponent < $1.lastPathComponent })
            where lay.pathExtension == "lay" {
                let code = lay.deletingPathExtension().lastPathComponent
                if let text = try? String(contentsOf: lay, encoding: .utf8),
                   text.components(separatedBy: .newlines).contains(where: {
                       $0.replacingOccurrences(of: " ", with: "").hasPrefix("in_GUI=False")
                   }) {
                    continue
                }
                found.append(Provider(code: code, region: region, isCombined: false))
            }
        }
        return found
            .filter { $0.code != "OSM" && $0.code != "SEA" }
            .sorted { $0.code.lowercased() < $1.code.lowercased() }
    }

    // MARK: - Tile output state

    /// What exists on disk for one tile the engine has (at least partially)
    /// built: its zOrtho4XP_ folder, whether a per-tile config and a final
    /// DSF are present.
    public struct TileState: Sendable, Equatable {
        public let lat: Int
        public let lon: Int
        public let buildDir: URL
        public let hasConfig: Bool
        public let hasDSF: Bool

        public var key: String { TileMath.key(lat: lat, lon: lon) }
    }

    /// Scans a tile base folder (the engine's Tiles/ or a custom build dir)
    /// for zOrtho4XP_±xx±yyy folders and their build state.
    public static func tileStates(inBaseFolder base: URL) -> [TileState] {
        let fm = FileManager.default
        let entries = (try? fm.contentsOfDirectory(at: base, includingPropertiesForKeys: [.isDirectoryKey])) ?? []
        var states: [TileState] = []
        for entry in entries {
            let name = entry.lastPathComponent
            guard name.hasPrefix("zOrtho4XP_"),
                  let tile = TileMath.parse(String(name.dropFirst("zOrtho4XP_".count)))
            else { continue }
            let cfg = entry.appendingPathComponent(
                "Ortho4XP_" + TileMath.key(lat: tile.lat, lon: tile.lon) + ".cfg")
            states.append(TileState(
                lat: tile.lat, lon: tile.lon, buildDir: entry,
                hasConfig: fm.fileExists(atPath: cfg.path),
                hasDSF: hasDSF(inBuildDir: entry, lat: tile.lat, lon: tile.lon)))
        }
        return states
    }

    /// A finished tile carries Earth nav data/<+40-080 rounded>/<+47+011>.dsf.
    static func hasDSF(inBuildDir dir: URL, lat: Int, lon: Int) -> Bool {
        let roundKey = TileMath.key(lat: Int(floor(Double(lat) / 10) * 10),
                                    lon: Int(floor(Double(lon) / 10) * 10))
        let dsf = dir.appendingPathComponent("Earth nav data")
            .appendingPathComponent(roundKey)
            .appendingPathComponent(TileMath.key(lat: lat, lon: lon) + ".dsf")
        return FileManager.default.fileExists(atPath: dsf.path)
    }

    /// The engine's per-tile folder name for a tile.
    public static func tileFolderName(lat: Int, lon: Int) -> String {
        "zOrtho4XP_" + TileMath.key(lat: lat, lon: lon)
    }
}
