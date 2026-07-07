import Foundation
import SwiftUI
import SceneryKit

/// Equirectangular camera: world position of the view center plus zoom.
struct MapCamera: Equatable {
    var centerLon: Double = -40
    var centerLat: Double = 30
    /// Pixels per degree.
    var scale: Double = 3.4

    func point(lon: Double, lat: Double, in size: CGSize) -> CGPoint {
        CGPoint(x: size.width / 2 + (lon - centerLon) * scale,
                y: size.height / 2 - (lat - centerLat) * scale)
    }

    func coordinate(of point: CGPoint, in size: CGSize) -> (lon: Double, lat: Double) {
        (centerLon + (Double(point.x) - Double(size.width) / 2) / scale,
         centerLat - (Double(point.y) - Double(size.height) / 2) / scale)
    }

    /// Keep the viewport inside the world: minimum zoom is "the map fills
    /// the window", and the center can't pan past the edges.
    mutating func clamp(in size: CGSize) {
        if size.width > 0, size.height > 0 {
            let minScale = max(Double(size.width) / 360, Double(size.height) / 180)
            scale = max(scale, minScale)
        }
        scale = min(scale, 400)
        if size.width > 0 {
            let halfW = Double(size.width) / 2 / scale
            centerLon = min(max(centerLon, -180 + halfW), 180 - halfW)
        }
        if size.height > 0 {
            let halfH = Double(size.height) / 2 / scale
            centerLat = min(max(centerLat, -90 + halfH), 90 - halfH)
        }
    }

    /// World-filling fit for a fresh window.
    static func fitted(to size: CGSize) -> MapCamera {
        var cam = MapCamera(centerLon: -40, centerLat: 30,
                            scale: max(Double(size.width) / 360, Double(size.height) / 180))
        cam.clamp(in: size)
        return cam
    }
}

/// Offline Natural Earth land polygons at two detail levels: 110m for world
/// views, 50m (with per-ring bounding boxes for viewport culling) at zoom.
enum LandData {
    struct Ring {
        let minLon: Double, minLat: Double, maxLon: Double, maxLat: Double
        let points: [CGPoint]
    }

    /// Coarse (110m): drawn whole, tiny.
    static let polygons: [[CGPoint]] = {
        guard let url = Bundle.module.url(forResource: "land", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [[[Double]]]
        else { return [] }
        return raw.map { ring in
            ring.compactMap { pair in
                pair.count >= 2 ? CGPoint(x: pair[0], y: pair[1]) : nil
            }
        }
    }()

    /// Detailed (50m): 60k points across 1,421 bbox-tagged rings; the canvas
    /// draws only rings intersecting the viewport.
    static let detailedRings: [Ring] = {
        guard let url = Bundle.module.url(forResource: "land50", withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let raw = try? JSONSerialization.jsonObject(with: data) as? [[Any]]
        else { return [] }
        return raw.compactMap { entry in
            guard entry.count == 5,
                  let minLon = entry[0] as? Double, let minLat = entry[1] as? Double,
                  let maxLon = entry[2] as? Double, let maxLat = entry[3] as? Double,
                  let flat = entry[4] as? [Double], flat.count >= 8
            else { return nil }
            var points: [CGPoint] = []
            points.reserveCapacity(flat.count / 2)
            var i = 0
            while i + 1 < flat.count {
                points.append(CGPoint(x: flat[i], y: flat[i + 1]))
                i += 2
            }
            return Ring(minLon: minLon, minLat: minLat, maxLon: maxLon, maxLat: maxLat,
                        points: points)
        }
    }()
}

/// Everything the map needs, precomputed ONCE per installation scan.
/// Rebuilding this per frame (or string-parsing tile keys in the draw loop)
/// is what makes dragging jerky — the draw path only does numeric compares.
struct MapOverlays: Sendable {
    struct Airport: Identifiable, Sendable {
        var id: String { icao + packName }
        let icao: String
        let info: AirportInfo
        let packName: String
        let status: PackStatus
    }

    struct TintTile: Sendable {
        let lat: Int
        let lon: Int
        let kind: PackKind
    }

    /// Pack with its geographic coverage, for viewport tests.
    ///
    /// The bounding box is only a cheap PRE-filter — coverage is decided by
    /// the actual 1° tiles and airport positions. The hull alone lies for
    /// packs with scattered tiles: c_CAN CYHZ ships Halifax's +44-064 AND a
    /// stray sign-flipped +44+044, so its hull spans the Atlantic and half
    /// of Europe, putting a Canadian airport "in view" over Marseille.
    struct PackBounds: Sendable {
        let pack: SceneryPack
        let minLat: Double, maxLat: Double, minLon: Double, maxLon: Double
        /// 1° tile keys: (lat + 90) * 360 + (lon + 180).
        let tileKeys: Set<Int32>
        let airportPoints: [GeoPoint]

        /// Above this many viewport tiles the walk stops paying for itself
        /// and the hull is accurate enough (a near-world view shows nearly
        /// everything anyway).
        static let maxTileWalk = 1024

        func intersects(minLon vMinLon: Double, maxLon vMaxLon: Double,
                        minLat vMinLat: Double, maxLat vMaxLat: Double) -> Bool {
            guard maxLon > vMinLon && minLon < vMaxLon
                    && maxLat > vMinLat && minLat < vMaxLat else { return false }

            let lonLo = Int(floor(max(vMinLon, -180))), lonHi = Int(floor(min(vMaxLon, 179.999)))
            let latLo = Int(floor(max(vMinLat, -90))), latHi = Int(floor(min(vMaxLat, 89.999)))
            guard lonHi >= lonLo, latHi >= latLo else { return false }
            if (lonHi - lonLo + 1) * (latHi - latLo + 1) > Self.maxTileWalk {
                return true
            }
            for point in airportPoints
            where point.lon >= vMinLon && point.lon <= vMaxLon
                && point.lat >= vMinLat && point.lat <= vMaxLat {
                return true
            }
            if !tileKeys.isEmpty {
                for lat in latLo...latHi {
                    for lon in lonLo...lonHi
                    where tileKeys.contains(Int32((lat + 90) * 360 + lon + 180)) {
                        return true
                    }
                }
            }
            return false
        }
    }

    /// Where a small-footprint pack lives, for a kind-colored map mark.
    /// Position is the centroid of its covered tiles — tile-resolution until
    /// DSF placement parsing lands (the LOAD_CENTER prerequisite) and can
    /// give exact object coordinates.
    struct Marker: Sendable {
        let lon: Double
        let lat: Double
        let packName: String
        let status: PackStatus
    }

    var tintTiles: [TintTile] = []
    var airports: [Airport] = []
    var packBounds: [PackBounds] = []
    var markers: [Marker] = []
    /// Packs with no geographic footprint (libraries, plugin-only packs)
    /// plus Laminar packs (excluded from map DRAWING, but still part of the
    /// load order): they belong to every viewport — hiding them made the
    /// inspector count disagree with the catalog and buried their findings.
    var everywherePacks: [SceneryPack] = []

    static let empty = MapOverlays(packs: [])

    init(packs: [SceneryPack]) {
        var kinds: [Int: PackKind] = [:] // (lat+90)*1000 + lon+180
        func rank(_ kind: PackKind) -> Int {
            switch kind { case .ortho: return 3; case .mesh: return 2; default: return 1 }
        }

        for pack in packs {
            // Laminar packs don't draw on the map (Global Airports would
            // paint 35k marks) but they do belong in every pack list.
            if pack.isLaminar {
                everywherePacks.append(pack)
                continue
            }
            var minLat = Double.infinity, maxLat = -Double.infinity
            var minLon = Double.infinity, maxLon = -Double.infinity
            var tileKeys = Set<Int32>()
            var airportPoints: [GeoPoint] = []

            for tileKey in pack.tiles {
                guard let tile = TileMath.parse(tileKey) else { continue }
                minLat = min(minLat, Double(tile.lat)); maxLat = max(maxLat, Double(tile.lat + 1))
                minLon = min(minLon, Double(tile.lon)); maxLon = max(maxLon, Double(tile.lon + 1))
                tileKeys.insert(Int32((tile.lat + 90) * 360 + tile.lon + 180))
                if pack.kind == .ortho || pack.kind == .mesh || pack.kind == .landmark {
                    let hash = (tile.lat + 90) * 1000 + tile.lon + 180
                    if rank(pack.kind) > rank(kinds[hash] ?? .other) {
                        kinds[hash] = pack.kind
                    }
                }
            }
            for (icao, info) in pack.airports where info.latitude != 0 || info.longitude != 0 {
                airports.append(Airport(icao: icao, info: info,
                                        packName: pack.name, status: pack.status))
                minLat = min(minLat, info.latitude); maxLat = max(maxLat, info.latitude)
                minLon = min(minLon, info.longitude); maxLon = max(maxLon, info.longitude)
                airportPoints.append(GeoPoint(lon: info.longitude, lat: info.latitude))
            }
            if minLat.isFinite {
                packBounds.append(PackBounds(pack: pack, minLat: minLat, maxLat: maxLat,
                                             minLon: minLon, maxLon: maxLon,
                                             tileKeys: tileKeys, airportPoints: airportPoints))
                // Landmark-style packs with a footprint of a tile or two get
                // a point mark; airports already have their own marks, and
                // wide overlays are communicated by the tile tint.
                if pack.kind == .landmark, pack.airports.isEmpty, (1...2).contains(pack.tiles.count) {
                    markers.append(Marker(lon: (minLon + maxLon) / 2, lat: (minLat + maxLat) / 2,
                                          packName: pack.name, status: pack.status))
                }
            } else {
                // No tiles, no located airports: libraries and plugin-only
                // packs load wherever OTHER scenery references them.
                everywherePacks.append(pack)
            }
        }

        tintTiles = kinds.map { hash, kind in
            TintTile(lat: hash / 1000 - 90, lon: hash % 1000 - 180, kind: kind)
        }
    }

    /// Same overlays with landmark marks moved from tile centroids to the
    /// exact object-placement centroids the analysis computed.
    func applyingExactMarkers(_ exact: [String: GeoPoint]) -> MapOverlays {
        guard !exact.isEmpty else { return self }
        var updated = self
        updated.markers = markers.map { marker in
            guard let point = exact[marker.packName] else { return marker }
            return Marker(lon: point.lon, lat: point.lat,
                          packName: marker.packName, status: marker.status)
        }
        return updated
    }

    /// Packs whose coverage intersects the given viewport.
    func packs(inViewport bounds: (minLon: Double, maxLon: Double,
                                   minLat: Double, maxLat: Double)) -> [SceneryPack] {
        packBounds
            .filter { $0.intersects(minLon: bounds.minLon, maxLon: bounds.maxLon,
                                    minLat: bounds.minLat, maxLat: bounds.maxLat) }
            .map { $0.pack }
            + everywherePacks
    }
}
