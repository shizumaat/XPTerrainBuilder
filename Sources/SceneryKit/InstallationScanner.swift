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
        scan(cache: [:], progress: progress, onPartial: onPartial).installation
    }

    /// Cache-aware scan: packs whose content signature matches the cached
    /// probe skip every file-content read (apt.dat parse, DSF header,
    /// terrain listing) AND every subtree walk beyond Earth nav data — the
    /// signature touches only apt.dat/DSF metadata plus the pack's top-level
    /// listing. Returns the refreshed cache for persisting.
    public func scan(cache: [String: SceneryIndexCache.CachedProbe],
                     progress: ((Int, Int) -> Void)? = nil,
                     onPartial: (([SceneryPack]) -> Void)? = nil)
        -> (installation: Installation, cache: [String: SceneryIndexCache.CachedProbe]) {
        let customScenery = root.appendingPathComponent("Custom Scenery")
        let iniOrder = parseSceneryPacksIni(customScenery.appendingPathComponent("scenery_packs.ini"))
        let entries = packEntries()

        // The per-pack work (apt.dat parse, DSF probe) is I/O bound and packs
        // are independent, so fan out; installs with thousands of packs exist.
        func makePack(url: URL, installed: Bool, probe: PackProbe) -> SceneryPack {
            self.makePack(url: url, installed: installed, probe: probe, iniOrder: iniOrder)
        }

        var probes = [PackProbe?](repeating: nil, count: entries.count)
        var newCache: [String: SceneryIndexCache.CachedProbe] = [:]
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
                    // Metadata-only walks; together they yield the pack's
                    // content signature — the cache validity key.
                    let (tiles, sampleDSF) = collectDSFTiles(contentURL, into: &hash, stats: &stats)
                    let signature = packSignature(contentURL, hash: &hash)
                    let airports: [String: AirportInfo]
                    let isOverlay: Bool?
                    let hasTerrain: Bool
                    let isPhotoTextured: Bool
                    let sizeBytes: Int64
                    let modifiedDate: Date?
                    if let cached = cache[url.path], cached.signature == signature {
                        // Unchanged since last scan: reuse everything that
                        // required reading file contents or walking subtrees.
                        airports = cached.airports
                        isOverlay = cached.isOverlay
                        hasTerrain = cached.hasTerrain
                        isPhotoTextured = cached.isPhotoTextured
                        sizeBytes = cached.sizeBytes
                        modifiedDate = cached.modifiedDate
                    } else {
                        statsWalk(contentURL, depth: 0, stats: &stats)
                        airports = parseAirports(inPack: contentURL)
                        if let sampleDSF,
                           case .ok(let defs) = DSFReader.readDefinitions(url: sampleDSF) {
                            isOverlay = defs.isOverlay
                        } else {
                            isOverlay = nil
                        }
                        let content = terrainAndTextureProbe(contentURL)
                        hasTerrain = content.hasTerrain
                        isPhotoTextured = content.isPhotoTextured
                        sizeBytes = stats.sizeBytes
                        modifiedDate = stats.latestModified
                    }
                    return PackProbe(
                        isLibrary: fm.fileExists(atPath: url.appendingPathComponent("library.txt").path),
                        airports: airports,
                        tiles: tiles,
                        isOverlay: isOverlay,
                        hasTerrain: hasTerrain,
                        isPhotoTextured: isPhotoTextured,
                        hasPlugins: fm.fileExists(
                            atPath: contentURL.appendingPathComponent("plugins").path),
                        signature: signature,
                        sizeBytes: sizeBytes,
                        modifiedDate: modifiedDate
                    )
                }
                lock.lock()
                buf.buffer[i] = probe
                newCache[url.path] = SceneryIndexCache.CachedProbe(
                    signature: probe.signature,
                    airports: probe.airports,
                    tiles: probe.tiles,
                    isLibrary: probe.isLibrary,
                    isOverlay: probe.isOverlay,
                    hasTerrain: probe.hasTerrain,
                    isPhotoTextured: probe.isPhotoTextured,
                    hasPlugins: probe.hasPlugins,
                    sizeBytes: probe.sizeBytes,
                    modifiedDate: probe.modifiedDate)
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

        var packs: [SceneryPack] = []
        for (entry, probe) in zip(entries, probes) {
            guard let probe else { continue }
            packs.append(makePack(url: entry.url, installed: entry.installed, probe: probe))
        }

        return (Installation(root: root, packs: packs,
                             packMarkers: Self.packMarkers(for: packs)),
                newCache)
    }

    /// Exact map marks for the scanned packs. The scan is deliberately
    /// metadata-only (see `packSignature`), so it can pin a pack only when
    /// the data it already parsed says exactly where the pack sits: a pack
    /// whose whole footprint is one airport. Everything else keeps the map's
    /// own tile-coverage centroid — pinning a sprawling landmark pack would
    /// need a full DSF placement parse per tile, which is not scan-grade work.
    public static func packMarkers(for packs: [SceneryPack]) -> [PackMarker] {
        packs.compactMap { pack in
            guard pack.tiles.count <= 1, pack.airports.count == 1,
                  let airport = pack.airports.values.first,
                  airport.latitude != 0 || airport.longitude != 0 else { return nil }
            return PackMarker(packName: pack.name,
                              point: GeoPoint(lon: airport.longitude, lat: airport.latitude))
        }
    }

    struct PackProbe {
        let isLibrary: Bool
        let airports: [String: AirportInfo]
        let tiles: Set<String>
        let isOverlay: Bool?
        let hasTerrain: Bool
        let isPhotoTextured: Bool
        let hasPlugins: Bool
        let signature: String
        let sizeBytes: Int64
        let modifiedDate: Date?
    }

    func makePack(url: URL, installed: Bool, probe: PackProbe,
                  iniOrder: [String: IniEntry]) -> SceneryPack {
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
            hasPlugins: probe.hasPlugins,
            sizeBytes: probe.sizeBytes,
            modifiedDate: probe.modifiedDate,
            resolvedURL: resolved
        )
    }

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

    /// Every pack folder in Custom Scenery (installed) and
    /// Custom Scenery (Disabled) (uninstalled).
    func packEntries() -> [(url: URL, installed: Bool)] {
        packDirectories(in: root.appendingPathComponent("Custom Scenery")).map { ($0, true) }
            + packDirectories(in: root.appendingPathComponent("Custom Scenery (Disabled)"))
                .map { ($0, false) }
    }

    /// The pack list rebuilt straight from a persisted probe cache — two
    /// folder listings, the ini, and one readlink per pack; no per-pack
    /// walks or content reads. Powers optimistic launch: the map shows last
    /// session's state instantly while the real scan revalidates in the
    /// background. Packs with no cache entry (new since last session) are
    /// omitted — the follow-up scan streams them in. Display-grade only:
    /// the library index needs file contents, so the full scan's
    /// Installation remains authoritative.
    public func packsFromCache(
        _ probes: [String: SceneryIndexCache.CachedProbe]) -> [SceneryPack] {
        guard !probes.isEmpty else { return [] }
        let iniOrder = parseSceneryPacksIni(root
            .appendingPathComponent("Custom Scenery/scenery_packs.ini"))
        return packEntries().compactMap { url, installed in
            guard let cached = probes[url.path] else { return nil }
            let probe = PackProbe(
                isLibrary: cached.isLibrary,
                airports: cached.airports,
                tiles: cached.tiles,
                isOverlay: cached.isOverlay,
                hasTerrain: cached.hasTerrain,
                isPhotoTextured: cached.isPhotoTextured,
                hasPlugins: cached.hasPlugins,
                signature: cached.signature,
                sizeBytes: cached.sizeBytes,
                modifiedDate: cached.modifiedDate)
            return makePack(url: url, installed: installed, probe: probe, iniOrder: iniOrder)
        }
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
    /// Size / freshness accumulated from the stats the walks were already
    /// reading — no extra I/O. Fed by the Earth nav data walk every scan
    /// and by statsWalk on cache miss; cache hits carry the totals in the
    /// cached probe instead.
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
        for case let file as URL in enumerator {
            let ext = file.pathExtension.lowercased()
            let isDSF = ext == "dsf"
            // apt.dat must feed the signature too: the walk skips this
            // subtree, and a replaced apt.dat has to invalidate the cached
            // airport probe.
            let isApt = file.lastPathComponent.lowercased() == "apt.dat"
            guard isDSF || isApt else { continue }
            let values = try? file.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
            hash.combine(file.lastPathComponent)
            hash.combine(values?.contentModificationDate?.timeIntervalSinceReferenceDate ?? 0)
            hash.combine(Double(values?.fileSize ?? 0))
            stats.record(size: values?.fileSize, modified: values?.contentModificationDate)
            if isDSF {
                tiles.insert(file.deletingPathExtension().lastPathComponent)
                if sample == nil { sample = file }
            }
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

    /// Content signature for cache invalidation. X-Plane's loadable scenery
    /// is rooted entirely in apt.dat and DSF files, so those are what decide
    /// validity: every one of them, any depth, is hashed by the Earth nav
    /// data walk that runs first (names, sizes, mtimes). This adds only the
    /// pack's TOP-LEVEL listing — no recursion — which keeps signatures
    /// distinct for packs with no Earth nav data at all (libraries; rename
    /// reconciliation matches by signature) and, via directory mtimes,
    /// catches adds/removals one level deeper (a swapped-in textures file).
    /// The blind spot is an in-place edit of a non-DSF file below the top
    /// level — our own FixEngine edits invalidate explicitly, and manual
    /// Analyze Selection always bypasses the cache.
    func packSignature(_ packURL: URL, hash: inout FNV1a) -> String {
        let entries = (try? fm.contentsOfDirectory(
            at: packURL,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey],
            options: [.skipsHiddenFiles]
        )) ?? []
        for entry in entries.sorted(by: { $0.lastPathComponent < $1.lastPathComponent }) {
            let name = entry.lastPathComponent
            if name == "Earth nav data" { continue } // hashed per-DSF already
            let values = try? entry.resourceValues(
                forKeys: [.contentModificationDateKey, .fileSizeKey])
            hash.combine(name)
            hash.combine(values?.contentModificationDate?.timeIntervalSinceReferenceDate ?? 0)
            hash.combine(Double(values?.fileSize ?? 0))
        }
        return String(hash.value, radix: 16)
    }

    /// Size / freshness for a freshly probed pack: files to depth 3 plus
    /// every DSF (recorded by the Earth nav data walk); deeper trees
    /// under-count slightly. Cache misses only — warm rescans reuse the
    /// cached totals instead of re-walking thousands of texture files.
    private func statsWalk(_ dir: URL, depth: Int, stats: inout ProbeStats) {
        let entries = (try? fm.contentsOfDirectory(
            at: dir,
            includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey, .isDirectoryKey],
            options: [.skipsHiddenFiles]
        )) ?? []
        for entry in entries {
            if depth == 0, entry.lastPathComponent == "Earth nav data" { continue }
            let values = try? entry.resourceValues(
                forKeys: [.contentModificationDateKey, .fileSizeKey, .isDirectoryKey])
            if values?.isDirectory == true {
                if depth < 2 {
                    statsWalk(entry, depth: depth + 1, stats: &stats)
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
