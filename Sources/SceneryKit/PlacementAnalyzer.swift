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
public struct PlacementAnalyzer {
    let installation: Installation

    /// Geometry decoding reads whole DSFs; packs beyond this many tiles are
    /// region-scale (simHeaven, ortho continents) where per-.pol LOAD_CENTER
    /// advice stops being meaningful anyway.
    static let maxDSFsPerPack = 100
    static let loadCenterMinTexturePx = 2048
    static let overdrawWarnSquareMeters = 5_000_000.0 // ~5 km²

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

        // Pack-local .pol files (library polygons belong to their author).
        var dsfURLs: [URL] = []
        var polFiles: [String: URL] = [:] // normalized rel path -> url
        let packPrefix = pack.url.path + "/"
        if let enumerator = fm.enumerator(at: pack.url, includingPropertiesForKeys: nil,
                                          options: [.skipsHiddenFiles, .skipsPackageDescendants]) {
            for case let url as URL in enumerator {
                switch url.pathExtension.lowercased() {
                case "dsf": dsfURLs.append(url)
                case "pol":
                    let rel = ResourceAuditAnalyzer.normalize(String(url.path.dropFirst(packPrefix.count)))
                    polFiles[rel] = url
                default: break
                }
            }
        }

        guard wantsMarker || !polFiles.isEmpty else { return result }
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

        for dsfURL in dsfURLs {
            guard let geometry = autoreleasepool(invoking: { DSFGeometryReader.read(url: dsfURL) })
            else { continue }
            for (_, points) in geometry.objectPlacements {
                for point in points {
                    lonSum += point.lon
                    latSum += point.lat
                    placementCount += 1
                }
            }
            for (defIndex, windings) in geometry.polygonWindings {
                guard defIndex < geometry.definitions.polygons.count else { continue }
                let name = ResourceAuditAnalyzer.normalize(geometry.definitions.polygons[defIndex])
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
        }

        if wantsMarker, placementCount > 0 {
            result.marker = GeoPoint(lon: lonSum / Double(placementCount),
                                     lat: latSum / Double(placementCount))
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
