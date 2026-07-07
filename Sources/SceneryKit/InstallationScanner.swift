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
    /// smooth determinate bar. `onPartial` (called from worker threads,
    /// throttled to ~2 Hz) streams growing snapshots of the pack list so a
    /// map can populate live while the scan runs; the returned Installation
    /// remains the complete, authoritative result.
    public func scan(progress: ((Int, Int) -> Void)? = nil,
                     onPartial: (([SceneryPack]) -> Void)? = nil) -> Installation {
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
            let hasTerrain: Bool
            let isPhotoTextured: Bool
            let signature: String
            let sizeBytes: Int64
            let modifiedDate: Date?
        }
        func makePack(url: URL, installed: Bool, probe: PackProbe) -> SceneryPack {
            // lastPathComponent yields FOREIGN (NSPathStore2-backed) Swift
            // strings; every hash/compare of one takes the slow Unicode
            // normalization path through objc_msgSend. Pack names are hashed
            // constantly (filters, sets, sorting) — profiled at ~45% of the
            // main thread. Make them native once, here.
            var name = url.lastPathComponent
            name.makeContiguousUTF8()
            let resolved = Self.resolvedPackRoot(url)
            let iniEntry = iniOrder["Custom Scenery/\(name)/"] ?? iniOrder["Custom Scenery/\(name)"]
            let status: PackStatus = !installed
                ? .uninstalled
                // Not listed yet = X-Plane will add it enabled on next launch.
                : (iniEntry?.enabled ?? true) ? .enabled : .disabled
            return SceneryPack(
                name: name,
                url: url,
                status: status,
                iniIndex: installed ? iniEntry?.index : nil,
                isLibrary: probe.isLibrary,
                airports: probe.airports,
                tiles: probe.tiles,
                isOverlay: probe.isOverlay,
                isLaminar: Self.laminarPackNames.contains(name),
                signature: probe.signature,
                hasTerrain: probe.hasTerrain,
                isPhotoTextured: probe.isPhotoTextured,
                sizeBytes: probe.sizeBytes,
                modifiedDate: probe.modifiedDate,
                resolvedURL: resolved
            )
        }

        var probes = [PackProbe?](repeating: nil, count: entries.count)
        let lock = NSLock()
        var completed = 0
        var streamed: [SceneryPack] = []
        var lastPartial = Date.distantPast
        probes.withUnsafeMutableBufferPointer { buffer in
            let buf = UnsafeSendableBuffer(buffer)
            DispatchQueue.concurrentPerform(iterations: entries.count) { i in
                let url = entries[i].url
                // PROBE through the resolved root: enumerator and
                // contentsOfDirectory do not resolve a symlinked ROOT, so
                // probing the symlink itself sees an empty folder — 2,508
                // packs (11.5 TB) on the reference install scanned blind.
                // Only the pack folder's OWN link is resolved (not
                // resolvingSymlinksInPath, whose /var→/private/var rewrites
                // would fork path spellings for every non-linked pack).
                let contentURL = Self.resolvedPackRoot(url) ?? url
                // The pool bounds file descriptors: abandoned directory
                // enumerators are autoreleased, and a GUI app only gets 256
                // fds — thousands of packs without draining exhausts them.
                let probe = autoreleasepool { () -> PackProbe in
                    var hash = FNV1a()
                    var stats = ProbeStats()
                    let (tiles, sampleDSF) = collectDSFTiles(contentURL, into: &hash, stats: &stats)
                    var isOverlay: Bool? = nil
                    if let sampleDSF, case .ok(let defs) = DSFReader.readDefinitions(url: sampleDSF) {
                        isOverlay = defs.isOverlay
                    }
                    let content = terrainAndTextureProbe(contentURL)
                    let signature = packSignature(contentURL, hash: &hash, stats: &stats)
                    return PackProbe(
                        isLibrary: fm.fileExists(atPath: url.appendingPathComponent("library.txt").path),
                        airports: parseAirports(inPack: contentURL),
                        tiles: tiles,
                        isOverlay: isOverlay,
                        hasTerrain: content.hasTerrain,
                        isPhotoTextured: content.isPhotoTextured,
                        signature: signature,
                        sizeBytes: stats.sizeBytes,
                        modifiedDate: stats.latestModified
                    )
                }
                lock.lock()
                buf.buffer[i] = probe
                completed += 1
                let done = completed
                var partial: [SceneryPack]? = nil
                if onPartial != nil {
                    streamed.append(makePack(url: url, installed: entries[i].installed, probe: probe))
                    if Date().timeIntervalSince(lastPartial) > 0.5 {
                        lastPartial = Date()
                        partial = streamed
                    }
                }
                lock.unlock()
                if done % 50 == 0 || done == entries.count { progress?(done, entries.count) }
                if let partial { onPartial?(partial) }
            }
        }

        // Library indexing mutates shared state; do it serially (few packs
        // are libraries, and library.txt files are small).
        var packs: [SceneryPack] = []
        var libraryIndex = LibraryIndex()
        for (entry, probe) in zip(entries, probes) {
            guard let probe else { continue }
            let pack = makePack(url: entry.url, installed: entry.installed, probe: probe)
            if entry.installed, probe.isLibrary {
                libraryIndex.indexLibrary(at: entry.url, packName: pack.name)
            }
            packs.append(pack)
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
        var currentCity: String?
        var currentCountry: String?

        func flush() {
            if let id = currentICAOOverride ?? currentID {
                airports[id] = AirportInfo(
                    name: currentName ?? id,
                    latitude: currentLat ?? 0,
                    longitude: currentLon ?? 0,
                    city: currentCity,
                    country: currentCountry
                )
            }
            currentID = nil
            currentName = nil
            currentICAOOverride = nil
            currentLat = nil
            currentLon = nil
            currentCity = nil
            currentCountry = nil
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
                    if parts[1] == "city" { currentCity = parts[2...].joined(separator: " ") }
                    if parts[1] == "country" { currentCountry = parts[2...].joined(separator: " ") }
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
    /// (sim/overlay determines mesh vs overlay scenery), plus every DSF's
    /// mtime folded into the change-detection hash (a replaced tile must
    /// invalidate the analysis cache even though its folder mtime doesn't
    /// move).
    /// Size / freshness accumulated from the stats the signature walk was
    /// already reading — no extra I/O. Sizes cover files to depth 3 plus
    /// every DSF; deeper trees under-count slightly.
    struct ProbeStats {
        var sizeBytes: Int64 = 0
        var latestModified: Date?

        mutating func record(size: Int?, modified: Date?) {
            sizeBytes += Int64(size ?? 0)
            if let modified, modified > (latestModified ?? .distantPast) {
                latestModified = modified
            }
        }
    }

    func collectDSFTiles(_ packURL: URL, into hash: inout FNV1a,
                         stats: inout ProbeStats) -> (tiles: Set<String>, sample: URL?) {
        let earthNav = packURL.appendingPathComponent("Earth nav data")
        guard let enumerator = fm.enumerator(
            at: earthNav,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey],
            options: [.skipsHiddenFiles]
        ) else { return ([], nil) }
        var tiles = Set<String>()
        var sample: URL? = nil
        for case let file as URL in enumerator where file.pathExtension.lowercased() == "dsf" {
            tiles.insert(file.deletingPathExtension().lastPathComponent)
            if sample == nil { sample = file }
            let values = try? file.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
            hash.combine(file.lastPathComponent)
            hash.combine(values?.contentModificationDate?.timeIntervalSinceReferenceDate ?? 0)
            hash.combine(Double(values?.fileSize ?? 0))
            stats.record(size: values?.fileSize, modified: values?.contentModificationDate)
        }
        return (tiles, sample)
    }

    /// Cheap content probe for pack-kind classification: does the pack carry
    /// .ter-based scenery, and does it hold photo-tile quantities of images?
    /// Orthos ship hundreds of image tiles — Ortho4XP puts them in textures/,
    /// SpainUHD keeps the .dds right beside each .ter in terrain/ — while a
    /// plain elevation mesh ships a handful. Name guessing misclassified
    /// packs like z_SpainUHDv2: ortho tiles with no "ortho" in the name.
    func terrainAndTextureProbe(_ packURL: URL) -> (hasTerrain: Bool, isPhotoTextured: Bool) {
        var terCount = 0
        var imageCount = 0
        let imageSuffixes = [".dds", ".png", ".jpg", ".jpeg"]
        for folder in ["terrain", "textures"] {
            guard let entries = try? fm.contentsOfDirectory(
                atPath: packURL.appendingPathComponent(folder).path) else { continue }
            for name in entries.prefix(500) {
                let lower = name.lowercased()
                if lower.hasSuffix(".ter") { terCount += 1 }
                if imageSuffixes.contains(where: { lower.hasSuffix($0) }) { imageCount += 1 }
            }
        }
        // Photo scenery carries roughly one image per .ter tile (SpainUHD:
        // dds beside every ter; Ortho4XP: the same volume in textures/). An
        // elevation mesh has hundreds of .ter sharing a handful of textures.
        let photoTextured = imageCount >= 20 || (imageCount >= 5 && imageCount >= terCount)
        return (terCount > 0, photoTextured)
    }

    /// The pack folder's symlink target as an absolute, standardized URL —
    /// nil when the folder is a real directory. Deliberately NOT
    /// resolvingSymlinksInPath: that rewrites unrelated components
    /// (/var → /private/var), forking path spellings for every pack.
    static func resolvedPackRoot(_ url: URL) -> URL? {
        guard let dest = try? FileManager.default.destinationOfSymbolicLink(atPath: url.path)
        else { return nil }
        let target = dest.hasPrefix("/")
            ? URL(fileURLWithPath: dest, isDirectory: true)
            : url.deletingLastPathComponent().appendingPathComponent(dest, isDirectory: true)
        return target.standardizedFileURL
    }

    /// Content signature for cache invalidation: names, sizes and mtimes of
    /// everything down to depth 2, plus every DSF (any depth, above). Catches
    /// adds, removals and replaced files; the one blind spot is an IN-PLACE
    /// edit of a file deeper than two levels — our own FixEngine edits
    /// invalidate explicitly, and manual Analyze Selection always bypasses
    /// the cache.
    func packSignature(_ packURL: URL, hash: inout FNV1a, stats: inout ProbeStats) -> String {
        signatureWalk(packURL, depth: 0, hash: &hash, stats: &stats)
        return String(hash.value, radix: 16)
    }

    private func signatureWalk(_ dir: URL, depth: Int, hash: inout FNV1a,
                               stats: inout ProbeStats) {
        let entries = (try? fm.contentsOfDirectory(
            at: dir,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]
        )) ?? []
        for entry in entries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            let name = entry.lastPathComponent
            if depth == 0, name == "Earth nav data" { continue } // hashed per-DSF already
            let values = try? entry.resourceValues(
                forKeys: [.contentModificationDateKey, .fileSizeKey, .isDirectoryKey])
            hash.combine(name)
            hash.combine(values?.contentModificationDate?.timeIntervalSinceReferenceDate ?? 0)
            hash.combine(Double(values?.fileSize ?? 0))
            if values?.isDirectory == true {
                if depth < 2 {
                    signatureWalk(entry, depth: depth + 1, hash: &hash, stats: &stats)
                }
            } else {
                stats.record(size: values?.fileSize, modified: values?.contentModificationDate)
            }
        }
    }
}

/// Deterministic 64-bit FNV-1a accumulator (Swift's Hasher is seeded per
/// process, useless for persisted signatures).
struct FNV1a {
    private(set) var value: UInt64 = 0xcbf29ce484222325

    mutating func combine(_ string: String) {
        for byte in string.utf8 {
            value = (value ^ UInt64(byte)) &* 0x100000001b3
        }
        value = (value ^ 0x7c) &* 0x100000001b3 // separator
    }

    mutating func combine(_ number: Double) {
        var bits = number.bitPattern
        for _ in 0..<8 {
            value = (value ^ (bits & 0xff)) &* 0x100000001b3
            bits >>= 8
        }
    }
}
