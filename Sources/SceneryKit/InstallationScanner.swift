import Foundation

/// Walks an X-Plane root folder and builds the in-memory model every
/// analyzer works from: the list of scenery packs (with their airports,
/// enabled state and load order) plus the merged library export index.
public struct InstallationScanner {
    let root: URL
    let fm = FileManager.default

    public init(root: URL) {
        self.root = root
    }

    /// `progress` reports (packs probed, total packs) — often enough for a
    /// smooth determinate bar.
    public func scan(progress: ((Int, Int) -> Void)? = nil) -> Installation {
        let customScenery = root.appendingPathComponent("Custom Scenery")
        let disabledFolder = root.appendingPathComponent("Custom Scenery (Disabled)")
        let iniOrder = parseSceneryPacksIni(customScenery.appendingPathComponent("scenery_packs.ini"))

        func packDirectories(in dir: URL) -> [URL] {
            let contents = (try? fm.contentsOfDirectory(
                at: dir,
                includingPropertiesForKeys: [.isDirectoryKey],
                options: [.skipsHiddenFiles]
            )) ?? []
            return contents
                .filter { url in
                    // Follow symlinks: packs are commonly linked in from
                    // other volumes (isDirectoryKey is false for the link
                    // itself; fileExists resolves it).
                    if (try? url.resourceValues(forKeys: [.isDirectoryKey]))?.isDirectory == true {
                        return true
                    }
                    var isDir: ObjCBool = false
                    return fm.fileExists(atPath: url.path, isDirectory: &isDir) && isDir.boolValue
                }
                .sorted { $0.lastPathComponent < $1.lastPathComponent }
        }

        let entries: [(url: URL, installed: Bool)] =
            packDirectories(in: customScenery).map { ($0, true) }
            + packDirectories(in: disabledFolder).map { ($0, false) }

        // The per-pack work (apt.dat parse, DSF probe) is I/O bound and packs
        // are independent, so fan out; installs with thousands of packs exist.
        struct PackProbe {
            let isLibrary: Bool
            let airports: [String: AirportInfo]
            let tiles: Set<String>
            let isOverlay: Bool?
        }
        var probes = [PackProbe?](repeating: nil, count: entries.count)
        let lock = NSLock()
        var completed = 0
        probes.withUnsafeMutableBufferPointer { buffer in
            let buf = UnsafeSendableBuffer(buffer)
            DispatchQueue.concurrentPerform(iterations: entries.count) { i in
                let url = entries[i].url
                // The pool bounds file descriptors: abandoned directory
                // enumerators are autoreleased, and a GUI app only gets 256
                // fds — thousands of packs without draining exhausts them.
                let probe = autoreleasepool { () -> PackProbe in
                    let (tiles, sampleDSF) = collectDSFTiles(url)
                    var isOverlay: Bool? = nil
                    if let sampleDSF, case .ok(let defs) = DSFReader.readDefinitions(url: sampleDSF) {
                        isOverlay = defs.isOverlay
                    }
                    return PackProbe(
                        isLibrary: fm.fileExists(atPath: url.appendingPathComponent("library.txt").path),
                        airports: parseAirports(inPack: url),
                        tiles: tiles,
                        isOverlay: isOverlay
                    )
                }
                lock.lock()
                buf.buffer[i] = probe
                completed += 1
                let done = completed
                lock.unlock()
                if done % 50 == 0 || done == entries.count { progress?(done, entries.count) }
            }
        }

        // Library indexing mutates shared state; do it serially (few packs
        // are libraries, and library.txt files are small).
        var packs: [SceneryPack] = []
        var libraryIndex = LibraryIndex()
        for (entry, probe) in zip(entries, probes) {
            guard let probe else { continue }
            let name = entry.url.lastPathComponent
            let status: PackStatus
            if !entry.installed {
                status = .uninstalled
            } else {
                if probe.isLibrary {
                    libraryIndex.indexLibrary(at: entry.url, packName: name)
                }
                let iniEntry = iniOrder["Custom Scenery/\(name)/"] ?? iniOrder["Custom Scenery/\(name)"]
                // Not listed yet = X-Plane will add it enabled on next launch.
                status = (iniEntry?.enabled ?? true) ? .enabled : .disabled
            }
            let iniEntry = iniOrder["Custom Scenery/\(name)/"] ?? iniOrder["Custom Scenery/\(name)"]
            packs.append(SceneryPack(
                name: name,
                url: entry.url,
                status: status,
                iniIndex: entry.installed ? iniEntry?.index : nil,
                isLibrary: probe.isLibrary,
                airports: probe.airports,
                tiles: probe.tiles,
                isOverlay: probe.isOverlay,
                isLaminar: Self.laminarPackNames.contains(name)
            ))
        }

        // X-Plane's own libraries: needed to audit lib/… references.
        var defaultIndex = LibraryIndex()
        let defaultScenery = root.appendingPathComponent("Resources/default scenery")
        for url in packDirectories(in: defaultScenery) {
            defaultIndex.indexLibrary(at: url, packName: url.lastPathComponent)
        }

        return Installation(root: root, packs: packs,
                            libraryIndex: libraryIndex, defaultLibraryIndex: defaultIndex)
    }

    static let laminarPackNames: Set<String> = [
        "Global Airports",
        "X-Plane Landmarks - Chicago",
        "X-Plane Landmarks - Dubai",
        "X-Plane Landmarks - Las Vegas",
        "X-Plane Landmarks - London",
        "X-Plane Landmarks - New York",
        "X-Plane Landmarks - Rio de Janeiro",
        "X-Plane Landmarks - Sydney",
        "X-Plane Landmarks - Washington DC",
        "Aerosoft - EDDF Frankfurt", // XP11 bundled demo areas are left alone too
    ]

    struct IniEntry {
        let index: Int
        let enabled: Bool
    }

    /// scenery_packs.ini: one `SCENERY_PACK <path>/` or `SCENERY_PACK_DISABLED <path>/`
    /// per line, in load-priority order (first wins).
    func parseSceneryPacksIni(_ url: URL) -> [String: IniEntry] {
        guard let text = TextFile.contents(of: url) else { return [:] }
        var result: [String: IniEntry] = [:]
        var index = 0
        for rawLine in TextFile.lines(text) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            let enabled: Bool
            let path: String
            if line.hasPrefix("SCENERY_PACK_DISABLED ") {
                enabled = false
                path = String(line.dropFirst("SCENERY_PACK_DISABLED ".count))
            } else if line.hasPrefix("SCENERY_PACK ") {
                enabled = true
                path = String(line.dropFirst("SCENERY_PACK ".count))
            } else {
                continue
            }
            result[path.trimmingCharacters(in: .whitespaces)] = IniEntry(index: index, enabled: enabled)
            index += 1
        }
        return result
    }

    /// Parse the pack's apt.dat (if any) and return ICAO -> airport name.
    /// Airport headers are row codes 1 (land), 16 (seaplane), 17 (heliport):
    ///   `1 433 0 0 KSEA Seattle Tacoma Intl`
    /// XP11+ adds `1302 icao_code KSEA` metadata which takes precedence.
    func parseAirports(inPack packURL: URL) -> [String: AirportInfo] {
        let candidates = [
            packURL.appendingPathComponent("Earth nav data/apt.dat"),
            packURL.appendingPathComponent("Earth Nav Data/apt.dat"),
        ]
        guard let aptURL = candidates.first(where: { fm.fileExists(atPath: $0.path) }) else {
            return [:]
        }
        // Custom-pack apt.dats are small; the size cap just guards against a
        // stray Global Airports-sized file (450+ MB) stalling the scan.
        guard let text = TextFile.contents(of: aptURL, maxBytes: 64 * 1024 * 1024) else { return [:] }

        var airports: [String: AirportInfo] = [:]
        var currentID: String?
        var currentName: String?
        var currentICAOOverride: String?
        var currentLat: Double?
        var currentLon: Double?

        func flush() {
            if let id = currentICAOOverride ?? currentID {
                airports[id] = AirportInfo(
                    name: currentName ?? id,
                    latitude: currentLat ?? 0,
                    longitude: currentLon ?? 0
                )
            }
            currentID = nil
            currentName = nil
            currentICAOOverride = nil
            currentLat = nil
            currentLon = nil
        }

        func capture(lat: Substring, lon: Substring) {
            guard currentLat == nil, let la = Double(lat), let lo = Double(lon),
                  abs(la) <= 90, abs(lo) <= 180, la != 0 || lo != 0 else { return }
            currentLat = la
            currentLon = lo
        }

        for rawLine in TextFile.lines(text) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)
            let parts = line.split(omittingEmptySubsequences: true,
                                   whereSeparator: { $0 == " " || $0 == "\t" })
            guard let code = parts.first else { continue }
            switch code {
            case "1", "16", "17":
                flush()
                if parts.count >= 5 {
                    currentID = String(parts[4])
                    currentName = parts[5...].joined(separator: " ")
                }
            case "1302":
                if parts.count >= 3 {
                    if parts[1] == "icao_code" { currentICAOOverride = String(parts[2]) }
                    if parts[1] == "datum_lat", let la = Double(parts[2]) { currentLat = currentLat ?? la }
                    if parts[1] == "datum_lon", let lo = Double(parts[2]) { currentLon = currentLon ?? lo }
                }
            case "100": // land runway: lat/lon of end 1 at fields 9,10
                if parts.count >= 11 { capture(lat: parts[9], lon: parts[10]) }
            case "101": // water runway: lat/lon at fields 4,5
                if parts.count >= 6 { capture(lat: parts[4], lon: parts[5]) }
            case "102": // helipad: lat/lon at fields 2,3
                if parts.count >= 4 { capture(lat: parts[2], lon: parts[3]) }
            case "99":
                flush()
            default:
                break
            }
        }
        flush()
        return airports
    }

    /// Tile names (e.g. "+41-073") of every DSF in the pack — cheap, from
    /// filenames only — plus one sample DSF URL for property probing
    /// (sim/overlay determines mesh vs overlay scenery).
    func collectDSFTiles(_ packURL: URL) -> (tiles: Set<String>, sample: URL?) {
        let earthNav = packURL.appendingPathComponent("Earth nav data")
        guard let enumerator = fm.enumerator(
            at: earthNav,
            includingPropertiesForKeys: nil,
            options: [.skipsHiddenFiles]
        ) else { return ([], nil) }
        var tiles = Set<String>()
        var sample: URL? = nil
        for case let file as URL in enumerator where file.pathExtension.lowercased() == "dsf" {
            tiles.insert(file.deletingPathExtension().lastPathComponent)
            if sample == nil { sample = file }
        }
        return (tiles, sample)
    }
}
