import Foundation

/// Checks that need to know WHERE a pack places things, not just what it
/// references — powered by DSFGeometryReader:
///
/// - **Exact pack position**: centroid of every object placement, for the
///   map's landmark marks (tile centroids were the stand-in).
/// - **C-13 LOAD_CENTER** (fixable): a pack-local draped polygon using a
///   ≥2048 px texture with no LOAD_CENTER loads that texture at full
///   resolution from any distance. Center and size are computed from the
///   DSF windings that actually use the .pol — Laminar calls this fix out
///   explicitly ("Three Things You Need for Fast Orthophotos").
/// - **C-01 overdraw** (flag-only): draped .pol coverage beyond ~5 km² pays
///   for the base mesh twice (Laminar: "use .ter files" for anything larger
///   than an airport or downtown). Conversion needs mesh rebuilding, so
///   there is no auto-fix.
/// - **C-09 escalation**: an instancing-hostile OBJ (animation, dataref
///   light level) is cheap as a one-off but expensive placed dozens of
///   times — the DSF placement counts say which it is.
/// - **C-17**: dataref-driven LIGHT_SPILL_CUSTOM in a heavily-placed object
///   (Laminar: "you really want that param version" for repeated fixtures).
/// - **C-15**: overlay DSFs that place real content but declare no
///   sim/exclude_* properties — default autogen renders underneath
///   simultaneously ("double scenery").
/// - **C-16**: facade rings with excessive node counts (facades are
///   per-instance meshes; huge rings are a memory multiplier).
public struct PlacementAnalyzer {
    let installation: Installation

    /// Geometry decoding reads whole DSFs; packs beyond this many tiles are
    /// region-scale (simHeaven, ortho continents) where per-.pol LOAD_CENTER
    /// advice stops being meaningful anyway.
    static let maxDSFsPerPack = 100
    static let loadCenterMinTexturePx = 2048
    static let overdrawWarnSquareMeters = 5_000_000.0 // ~5 km²
    /// PITFALLS heuristic: an animated OBJ placed ≥ ~25× in one tile is off
    /// the instancing path that many times; ≥ 100× is a real frame cost.
    static let heavyPlacementCount = 25
    static let severePlacementCount = 100
    /// Laminar: overlays with substantial placements should exclude the
    /// scenery beneath them.
    static let exclusionObjectThreshold = 100
    /// Heuristic (PITFALLS §6): facade rings beyond ~100 nodes.
    static let maxFacadeRingNodes = 100
    static let maxFindingsPerCheck = 5

    public init(installation: Installation) {
        self.installation = installation
    }

    public struct PackResult: Sendable {
        public var findings: [Finding] = []
        /// Centroid of every object placement (small-footprint packs only).
        public var marker: GeoPoint? = nil
    }

    public func scanPack(_ pack: SceneryPack) -> PackResult {
        var result = PackResult()
        let fm = FileManager.default

        let wantsMarker = pack.kind == .landmark && pack.airports.isEmpty
            && (1...2).contains(pack.tiles.count)
        // Placement-count / exclusion / facade checks apply to object-placing
        // packs (airports, landmarks). Ortho and mesh tiles place terrain,
        // not clutter — reading their geometry would cost minutes for
        // nothing, and region-scale packs are capped out by maxDSFsPerPack
        // anyway.
        let wantsPlacementChecks = pack.kind == .airport || pack.kind == .landmark

        // Pack-local .pol/.obj files (library resources belong to their author).
        var dsfURLs: [URL] = []
        var polFiles: [String: URL] = [:] // normalized rel path -> url
        var objFiles: [String: URL] = [:]
        let packPrefix = pack.url.path + "/"
        if let enumerator = fm.enumerator(at: pack.url, includingPropertiesForKeys: nil,
                                          options: [.skipsHiddenFiles, .skipsPackageDescendants]) {
            for case let url as URL in enumerator {
                switch url.pathExtension.lowercased() {
                case "dsf": dsfURLs.append(url)
                case "pol":
                    let rel = ResourceAuditAnalyzer.normalize(String(url.path.dropFirst(packPrefix.count)))
                    polFiles[rel] = url
                case "obj" where wantsPlacementChecks:
                    // Not collected otherwise: library packs hold tens of
                    // thousands of OBJs and path-derived keys hash slowly.
                    let rel = ResourceAuditAnalyzer.normalize(String(url.path.dropFirst(packPrefix.count)))
                    objFiles[rel] = url
                default: break
                }
            }
        }

        guard wantsMarker || wantsPlacementChecks || !polFiles.isEmpty else { return result }
        guard !dsfURLs.isEmpty, dsfURLs.count <= Self.maxDSFsPerPack else { return result }

        // One pass over the pack's DSF geometry: object centroid + winding
        // extents per polygon definition (keyed by normalized DEFN path).
        var lonSum = 0.0, latSum = 0.0
        var placementCount = 0
        struct PolyUsage {
            var minLon = Double.infinity, maxLon = -Double.infinity
            var minLat = Double.infinity, maxLat = -Double.infinity
            var areaSquareMeters = 0.0
            var windings = 0
        }
        var usage: [String: PolyUsage] = [:]
        // Placement counts per object def, the MAX seen in any single DSF
        // (the per-tile count is what the instancing thresholds refer to).
        var objPlacementMax: [String: Int] = [:]
        // Facade rings beyond the node heuristic, worst first.
        var facadeRings: [(def: String, nodes: Int)] = []
        // Exclusion audit across the pack's overlay tiles. Exclusion CREDIT
        // counts any overlay tile declaring sim/exclude_* (authors often put
        // the exclusions in one tile and the bulk of the clutter in its
        // neighbor); only zero exclusions anywhere in the pack raises C-15.
        var overlayTilesWithContent = 0
        var overlayTilesWithExclusions = 0
        var exclusionContentSummary = (objects: 0, polygons: 0)
        var contentMinLon = Double.infinity, contentMaxLon = -Double.infinity
        var contentMinLat = Double.infinity, contentMaxLat = -Double.infinity

        for dsfURL in dsfURLs {
            // A pack we're only reading for placement checks doesn't justify
            // decompressing region-sized tiles (the marker/.pol interests
            // predate this gate and keep their behavior).
            if !wantsMarker, polFiles.isEmpty,
               let size = (try? fm.attributesOfItem(atPath: dsfURL.path))?[.size] as? Int,
               size > 32 * 1024 * 1024 {
                continue
            }
            guard let geometry = autoreleasepool(invoking: { DSFGeometryReader.read(url: dsfURL) })
            else { continue }
            var dsfObjectCount = 0
            var dsfObjectPerDef: [String: Int] = [:]
            for (defIndex, points) in geometry.objectPlacements {
                for point in points {
                    lonSum += point.lon
                    latSum += point.lat
                    placementCount += 1
                    if wantsPlacementChecks {
                        contentMinLon = min(contentMinLon, point.lon)
                        contentMaxLon = max(contentMaxLon, point.lon)
                        contentMinLat = min(contentMinLat, point.lat)
                        contentMaxLat = max(contentMaxLat, point.lat)
                    }
                }
                dsfObjectCount += points.count
                if wantsPlacementChecks, defIndex < geometry.definitions.objects.count {
                    let name = ResourceAuditAnalyzer.normalize(geometry.definitions.objects[defIndex])
                    dsfObjectPerDef[name, default: 0] += points.count
                }
            }
            for (name, count) in dsfObjectPerDef {
                objPlacementMax[name] = max(objPlacementMax[name] ?? 0, count)
            }

            var dsfClutterPolygons = 0
            for (defIndex, windings) in geometry.polygonWindings {
                guard defIndex < geometry.definitions.polygons.count else { continue }
                let name = ResourceAuditAnalyzer.normalize(geometry.definitions.polygons[defIndex])
                // Facades and forests double-draw over autogen; draped .pol
                // imagery does not.
                if name.hasSuffix(".fac") || name.hasSuffix(".for") {
                    dsfClutterPolygons += windings.count
                }
                if name.hasSuffix(".fac") {
                    for winding in windings where winding.count > Self.maxFacadeRingNodes {
                        facadeRings.append((name, winding.count))
                    }
                }
                guard name.hasSuffix(".pol"), polFiles[name] != nil else { continue }
                var u = usage[name] ?? PolyUsage()
                for winding in windings where winding.count >= 3 {
                    for p in winding {
                        u.minLon = min(u.minLon, p.lon); u.maxLon = max(u.maxLon, p.lon)
                        u.minLat = min(u.minLat, p.lat); u.maxLat = max(u.maxLat, p.lat)
                    }
                    u.areaSquareMeters += Self.areaSquareMeters(of: winding)
                    u.windings += 1
                }
                usage[name] = u
            }

            // C-15 accounting: content and exclusion-credit are tracked
            // independently — an exclusion declared on ANY overlay tile
            // clears the pack.
            let props = geometry.definitions.properties
            if props["sim/overlay"] == "1" {
                if props.keys.contains(where: { $0.hasPrefix("sim/exclude_") }) {
                    overlayTilesWithExclusions += 1
                }
                if dsfObjectCount > Self.exclusionObjectThreshold || dsfClutterPolygons > 0 {
                    overlayTilesWithContent += 1
                    exclusionContentSummary.objects += dsfObjectCount
                    exclusionContentSummary.polygons += dsfClutterPolygons
                }
            }
        }

        if wantsMarker, placementCount > 0 {
            result.marker = GeoPoint(lon: lonSum / Double(placementCount),
                                     lat: latSum / Double(placementCount))
        }

        if wantsPlacementChecks {
            result.findings.append(contentsOf: placementCountFindings(
                pack: pack, objFiles: objFiles, objPlacementMax: objPlacementMax))
            result.findings.append(contentsOf: facadeFindings(
                pack: pack, facadeRings: facadeRings))
            if overlayTilesWithContent > 0, overlayTilesWithExclusions == 0 {
                result.findings.append(exclusionFinding(
                    pack: pack,
                    tiles: overlayTilesWithContent,
                    content: exclusionContentSummary,
                    bounds: contentMinLon.isFinite
                        ? (contentMinLon, contentMaxLon, contentMinLat, contentMaxLat) : nil))
            }
        }

        for (rel, u) in usage.sorted(by: { $0.key < $1.key }) {
            guard let polURL = polFiles[rel], u.minLon.isFinite else { continue }
            let pol = Self.parsePol(at: polURL, packURL: pack.url)

            // C-13: big texture, no LOAD_CENTER — mechanical fix.
            if let textureInfo = pol.texture,
               max(textureInfo.width, textureInfo.height) >= Self.loadCenterMinTexturePx,
               !pol.hasLoadCenter {
                let centerLat = (u.minLat + u.maxLat) / 2
                let centerLon = (u.minLon + u.maxLon) / 2
                let widthMeters = (u.maxLon - u.minLon) * 111_320 * cos(centerLat * .pi / 180)
                let heightMeters = (u.maxLat - u.minLat) * 110_574
                let size = max(Int(max(widthMeters, heightMeters).rounded()), 100)
                let resolution = max(textureInfo.width, textureInfo.height)
                result.findings.append(Finding(
                    checkID: "C-13",
                    severity: .warning,
                    category: .performance,
                    title: "Ortho texture without LOAD_CENTER: \(polURL.lastPathComponent)",
                    detail: "'\(rel)' in '\(pack.name)' drapes a \(textureInfo.width)×\(textureInfo.height) texture over ~\(Self.formatArea(u.areaSquareMeters)) with no LOAD_CENTER, so the full-resolution texture stays loaded no matter how far away it is. Laminar: LOAD_CENTER \"saves VRAM, since textures that are far away won't be loaded at full resolution\".",
                    path: polURL.path,
                    suggestion: "Apply Fix to insert 'LOAD_CENTER \(String(format: "%.4f %.4f", centerLat, centerLon)) \(size) \(resolution)' (computed from the DSF polygons that use this file). Backed up and revertible.",
                    url: URL(string: "https://developer.x-plane.com/2011/03/three-things-you-need-for-fast-orthophotos/"),
                    fixability: .auto,
                    proposedFix: .insertLoadCenter(polPath: polURL.path,
                                                   latitude: centerLat, longitude: centerLon,
                                                   sizeMeters: size, resolutionPx: resolution),
                    packName: pack.name,
                    packKind: pack.kind
                ))
            }

            // C-01: large draped coverage — the mesh is drawn twice under it.
            if u.areaSquareMeters > Self.overdrawWarnSquareMeters {
                result.findings.append(Finding(
                    checkID: "C-01",
                    severity: .warning,
                    category: .performance,
                    title: "Large draped polygon: \(polURL.lastPathComponent)",
                    detail: "'\(rel)' in '\(pack.name)' covers ~\(Self.formatArea(u.areaSquareMeters)) across \(u.windings) winding\(u.windings == 1 ? "" : "s") as a draped polygon. X-Plane pays for the base mesh twice under draped polygons — double the VRAM and fill rate. Laminar: \"If you want high performance orthophotos over an area any larger than an airport or down-town, please use .ter files!\"",
                    path: polURL.path,
                    suggestion: "Author-level change: rebuild the area as .ter-based ortho (Ortho4XP-style). Converting requires mesh rebuilding, so there is no automatic fix.",
                    url: URL(string: "https://developer.x-plane.com/2011/03/three-things-you-need-for-fast-orthophotos/"),
                    fixability: .manual,
                    packName: pack.name,
                    packKind: pack.kind
                ))
            }
        }

        return result
    }

    // MARK: - Placement-count checks

    /// C-09 escalation + C-17: parse the pack-local OBJs that are placed
    /// heavily enough for instancing to matter, and flag the ones that
    /// can't instance. A handful of parses per pack — only defs past the
    /// placement threshold are read.
    private func placementCountFindings(
        pack: SceneryPack, objFiles: [String: URL], objPlacementMax: [String: Int]
    ) -> [Finding] {
        var findings: [Finding] = []
        var animated: [(url: URL, info: ObjInfo, count: Int)] = []
        var datarefSpill: [(url: URL, info: ObjInfo, count: Int)] = []

        // Worst-placed defs first, capped: a dense city overlay can have
        // hundreds of 25+-placement defs and each candidate is a full OBJ
        // parse (PackageHealthAnalyzer parses its own, separate top-150).
        let candidates = objPlacementMax
            .filter { $0.value >= Self.heavyPlacementCount && objFiles[$0.key] != nil }
            .sorted { $0.value > $1.value }
            .prefix(40)
        for (def, count) in candidates {
            guard let url = objFiles[def] else { continue } // library object: its author's problem
            guard let info = autoreleasepool(invoking: { ObjParser.parse(url: url) }) else { continue }
            if info.animated || info.hasLightLevel {
                animated.append((url, info, count))
            }
            if info.datarefSpillCount > 0 {
                datarefSpill.append((url, info, count))
            }
        }

        for entry in animated.sorted(by: { $0.count > $1.count }).prefix(Self.maxFindingsPerCheck) {
            let severe = entry.count >= Self.severePlacementCount
            let isAnim = entry.info.animated
            let reason = isAnim ? "animation (ANIM_*)" : "dataref-driven ATTR_light_level"
            findings.append(Finding(
                checkID: "C-09",
                severity: severe ? .warning : .info,
                category: .developerDebug,
                title: "\(isAnim ? "Animated" : "Instancing-hostile") object placed \(entry.count)× in one tile: \(entry.url.lastPathComponent)",
                detail: "\(entry.url.lastPathComponent) (\(entry.info.vertexCount) vertices) uses \(reason), which takes it off X-Plane's instanced drawing path — and this pack places it \(entry.count) times in a single DSF. Every placement is CPU-side draw work that instanced objects avoid entirely.\(severe ? " At \(entry.count) placements this is a measurable per-frame cost, not a rounding error." : "")",
                path: entry.url.path,
                suggestion: isAnim
                    ? "The author can split the animated part into a small separate object so the repeated geometry stays instanced, or bake the animation away if it never actually moves."
                    : "The author can move the ATTR_light_level surface into a small separate object (or drop it) so the repeated geometry stays instanced.",
                url: URL(string: "https://developer.x-plane.com/article/optimizing-object-peformance/"),
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }

        for entry in datarefSpill.sorted(by: { $0.count > $1.count }).prefix(Self.maxFindingsPerCheck) {
            findings.append(Finding(
                checkID: "C-17",
                severity: .info,
                category: .developerDebug,
                title: "Dataref spill light in object placed \(entry.count)×: \(entry.url.lastPathComponent)",
                detail: "\(entry.url.lastPathComponent) uses LIGHT_SPILL_CUSTOM driven by a dataref and is placed \(entry.count) times in one tile — each copy evaluates its dataref per frame. Laminar: \"if you're building a light used a lot (a streetlight, a taxiway light, an airport lighting fixture) you really want that param version\".",
                path: entry.url.path,
                suggestion: "The author can convert the light to the equivalent parameterized light (LIGHT_PARAM) — same look, evaluated on the fast path.",
                url: URL(string: "https://developer.x-plane.com/2013/04/customizing-spill-lights-two-ways/"),
                fixability: .manual,
                packName: pack.name,
                packKind: pack.kind
            ))
        }
        return findings
    }

    /// C-16: facades are per-instance meshes ("each facade instance consumes
    /// additional memory since facades are individually unique" — Laminar);
    /// rings with huge node counts multiply that geometry.
    private func facadeFindings(pack: SceneryPack, facadeRings: [(def: String, nodes: Int)]) -> [Finding] {
        guard !facadeRings.isEmpty else { return [] }
        var worstPerDef: [String: Int] = [:]
        var countPerDef: [String: Int] = [:]
        for ring in facadeRings {
            worstPerDef[ring.def] = max(worstPerDef[ring.def] ?? 0, ring.nodes)
            countPerDef[ring.def, default: 0] += 1
        }
        return worstPerDef.sorted { $0.value > $1.value }.prefix(Self.maxFindingsPerCheck)
            .map { def, worst in
                let count = countPerDef[def] ?? 1
                let name = URL(fileURLWithPath: def).lastPathComponent
                return Finding(
                    checkID: "C-16",
                    severity: .info,
                    category: .developerDebug,
                    title: "Facade ring with \(worst) nodes: \(name)",
                    detail: "\(count) facade placement\(count == 1 ? "" : "s") of '\(def)' in '\(pack.name)' exceed\(count == 1 ? "s" : "") \(Self.maxFacadeRingNodes) nodes per ring (largest: \(worst)). Facades generate unique per-instance geometry — every wall segment adds polygons that no other instance shares, so giant rings are a memory multiplier (Laminar: facade cost usually shows up as memory exhaustion before framerate).",
                    suggestion: "The author should simplify the ring or split it into several smaller facades in WED. Not mechanically fixable.",
                    url: URL(string: "https://developer.x-plane.com/article/performance-tuning-and-scenery/"),
                    fixability: .manual,
                    packName: pack.name,
                    packKind: pack.kind
                )
            }
    }

    /// C-15: overlay tiles that place clutter but exclude nothing beneath it.
    private func exclusionFinding(
        pack: SceneryPack, tiles: Int, content: (objects: Int, polygons: Int),
        bounds: (minLon: Double, maxLon: Double, minLat: Double, maxLat: Double)?
    ) -> Finding {
        var contentParts: [String] = []
        if content.objects > 0 { contentParts.append("\(content.objects) object placements") }
        if content.polygons > 0 { contentParts.append("\(content.polygons) facade/forest polygons") }
        let boundsClause = bounds.map {
            String(format: " A bounding exclusion would span %.4f…%.4f lat, %.4f…%.4f lon — but over-exclusion visibly blanks autogen, so the author should draw it deliberately in WED.",
                   $0.minLat, $0.maxLat, $0.minLon, $0.maxLon)
        } ?? ""
        return Finding(
            checkID: "C-15",
            severity: .info,
            category: .developerDebug,
            title: "No exclusion zones: '\(pack.name)' overlays \(contentParts.joined(separator: ", "))",
            detail: "\(tiles == 1 ? "The pack's overlay tile places" : "\(tiles) overlay tiles place") \(contentParts.joined(separator: " and ")) without any sim/exclude_* property, so whatever default scenery sits underneath (autogen, airports, trees) still renders at the same time — X-Plane draws both.\(boundsClause)",
            path: pack.url.path,
            suggestion: "Laminar: \"Custom overlay scenery packs should have exclusion zones to mask out the scenery below them.\" The author adds exclusion rectangles in WED. If the area genuinely has no autogen beneath (open water, bare terrain), this costs nothing and the finding can be ignored.",
            url: URL(string: "https://developer.x-plane.com/2014/09/prioritizing-scenery-and-exclusion-zones/"),
            fixability: .manual,
            packName: pack.name,
            packKind: pack.kind
        )
    }

    // MARK: - Helpers

    struct PolInfo {
        var texture: TextureInfo?
        var hasLoadCenter = false
    }

    /// TEXTURE/TEXTURE_NOWRAP path (resolved extension-blind next to the
    /// .pol, then pack-relative) and LOAD_CENTER presence.
    static func parsePol(at url: URL, packURL: URL) -> PolInfo {
        var info = PolInfo()
        guard let text = TextFile.head(of: url, maxBytes: 64 * 1024) else { return info }
        for line in TextFile.lines(text) {
            let trimmed = line.trimmingCharacters(in: .whitespaces)
            if trimmed.hasPrefix("LOAD_CENTER") { info.hasLoadCenter = true }
            guard info.texture == nil, trimmed.hasPrefix("TEXTURE") else { continue }
            let value = trimmed.drop(while: { $0 != " " && $0 != "\t" })
                .trimmingCharacters(in: .whitespaces)
                .replacingOccurrences(of: "\\", with: "/")
            guard !value.isEmpty else { continue }
            for base in [url.deletingLastPathComponent(), packURL] {
                let candidate = base.appendingPathComponent(value).standardizedFileURL
                for resolved in [candidate,
                                 candidate.deletingPathExtension().appendingPathExtension("dds"),
                                 candidate.deletingPathExtension().appendingPathExtension("png")] {
                    if let inspected = TextureInspector.inspect(url: resolved) {
                        info.texture = inspected
                        break
                    }
                }
                if info.texture != nil { break }
            }
        }
        return info
    }

    /// Shoelace area of a lat/lon ring, in square meters (equirectangular
    /// local scaling — plenty for threshold checks).
    static func areaSquareMeters(of ring: [GeoPoint]) -> Double {
        guard ring.count >= 3 else { return 0 }
        let midLat = ring.reduce(0.0) { $0 + $1.lat } / Double(ring.count)
        let metersPerLon = 111_320 * cos(midLat * .pi / 180)
        let metersPerLat = 110_574.0
        var sum = 0.0
        for i in ring.indices {
            let a = ring[i], b = ring[(i + 1) % ring.count]
            sum += (a.lon * metersPerLon) * (b.lat * metersPerLat)
                 - (b.lon * metersPerLon) * (a.lat * metersPerLat)
        }
        return abs(sum) / 2
    }

    static func formatArea(_ squareMeters: Double) -> String {
        squareMeters >= 1_000_000
            ? String(format: "%.1f km²", squareMeters / 1_000_000)
            : String(format: "%.0f m²", squareMeters)
    }
}
