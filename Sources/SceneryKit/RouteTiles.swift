import Foundation

/// Route → tiles for "Select from flight plan" (issue #829): the Swift half
/// of `Ortho4XP/src/O4_Flight_Plan.py`'s geometry, twinned on
/// `Ortho4XP/tests/fixtures/flight_plan_cases.json`. Every operation is
/// written in the Python half's order so the two agree to the last bit.
///
/// Every leg is densified along the GREAT CIRCLE (a long leg bends poleward
/// of the straight lat/lon line), samples `sampleStepKm` apart; a tile is
/// kept when its nearest point lies within the radius of a sample. The step
/// is fixed, so a larger radius never drops a tile. Departure and arrival
/// tiles are always kept; longitudes wrap at the antimeridian.
public enum RouteTiles {
    public static let earthRadiusKm = 6371.0088
    public static let kmPerNm = 1.852
    public static let sampleStepKm = 5.0

    private static let degPerRad = 180.0 / Double.pi
    private static let radPerDeg = Double.pi / 180.0

    typealias Vec = (Double, Double, Double)

    static func vec(_ lat: Double, _ lon: Double) -> Vec {
        let p = lat * radPerDeg, l = lon * radPerDeg
        return (cos(p) * cos(l), cos(p) * sin(l), sin(p))
    }

    /// `lon` in [-180, 180); an in-range value is returned unchanged.
    static func normLon(_ lon: Double) -> Double {
        if lon >= -180, lon < 180 { return lon }
        var l = fmod(lon + 180.0, 360.0)
        if l < 0 { l += 360.0 }
        return l - 180.0
    }

    static func latLon(_ v: Vec) -> (lat: Double, lon: Double) {
        let lat = atan2(v.2, hypot(v.0, v.1)) * degPerRad
        return (lat, normLon(atan2(v.1, v.0) * degPerRad))
    }

    static func centralAngle(_ a: Vec, _ b: Vec) -> Double {
        let cx = a.1 * b.2 - a.2 * b.1
        let cy = a.2 * b.0 - a.0 * b.2
        let cz = a.0 * b.1 - a.1 * b.0
        let dot = a.0 * b.0 + a.1 * b.1 + a.2 * b.2
        return atan2((cx * cx + cy * cy + cz * cz).squareRoot(), dot)
    }

    /// `points` with great-circle samples at most `stepKm` apart along
    /// every leg; the waypoints themselves are kept.
    public static func densify(_ points: [(lat: Double, lon: Double)],
                               stepKm: Double = sampleStepKm) -> [(lat: Double, lon: Double)] {
        var out: [(lat: Double, lon: Double)] = []
        for (i, p) in points.enumerated() {
            if i == 0 {
                out.append((p.lat, normLon(p.lon)))
                continue
            }
            let a = vec(points[i - 1].lat, points[i - 1].lon), b = vec(p.lat, p.lon)
            let omega = centralAngle(a, b)
            let n = max(1, Int((omega * earthRadiusKm / stepKm).rounded(.up)))
            let sinOmega = sin(omega)
            if n > 1 {
                for k in 1..<n {
                    let t = Double(k) / Double(n)
                    let wa: Double, wb: Double
                    if sinOmega < 1e-12 {
                        wa = 1.0 - t
                        wb = t
                    } else {
                        wa = sin((1.0 - t) * omega) / sinOmega
                        wb = sin(t * omega) / sinOmega
                    }
                    out.append(latLon((wa * a.0 + wb * b.0, wa * a.1 + wb * b.1, wa * a.2 + wb * b.2)))
                }
            }
            out.append((p.lat, normLon(p.lon)))
        }
        return out
    }

    /// Python's floored modulo for doubles.
    private static func pmod(_ x: Double, _ m: Double) -> Double {
        let r = fmod(x, m)
        return (r != 0 && (r < 0) != (m < 0)) ? r + m : r
    }

    private static func wrapLon(_ lon: Int) -> Int {
        (((lon + 180) % 360) + 360) % 360 - 180
    }

    /// Great-circle distance from (lat, lon) to the nearest point of tile
    /// (tlat, tlon), its 1×1 lat/lon rectangle, km.
    static func tileDistanceKm(_ lat: Double, _ lon: Double, _ tlat: Int, _ tlon: Int) -> Double {
        let east = pmod(lon - Double(tlon), 360.0)
        if east <= 1.0 {
            let nearest = min(max(lat, Double(tlat)), Double(tlat + 1))
            return earthRadiusKm * (abs(lat - nearest) * radPerDeg)
        }
        let dl = min(east - 1.0, 360.0 - east) * radPerDeg
        let p = lat * radPerDeg
        let sp = sin(p), cp = cos(p), cdl = cos(dl)
        let lo = Double(tlat) * radPerDeg, hi = Double(tlat + 1) * radPerDeg
        var candidates = [lo, hi]
        let star = atan2(sp, cp * cdl)
        if lo < star, star < hi { candidates.append(star) }
        let best = candidates.map { sp * sin($0) + cp * cos($0) * cdl }.max()!
        return earthRadiusKm * acos(max(-1.0, min(1.0, best)))
    }

    private static func candidateTiles(_ lat: Double, _ lon: Double, _ radius: Double) -> [AirportTile] {
        let dlat = (radius / earthRadiusKm) * degPerRad + 1e-9
        let latLo = max(-90, Int(floor(lat - dlat)))
        let latHi = min(89, Int(floor(lat + dlat)))
        let reach = min(90.0, abs(lat) + dlat)
        var lons: [Int]
        if reach >= 89.0 {
            lons = Array(-180..<180)
        } else {
            let dlon = dlat / cos(reach * radPerDeg)
            let lonLo = Int(floor(lon - dlon)), lonHi = Int(floor(lon + dlon))
            lons = lonHi - lonLo >= 359 ? Array(-180..<180) : (lonLo...lonHi).map(wrapLon)
        }
        guard latLo <= latHi else { return [] }
        return (latLo...latHi).flatMap { tlat in lons.map { AirportTile(lat: tlat, lon: $0) } }
    }

    /// The tile holding (lat, lon), longitude wrapped into [-180, 180).
    public static func tileOf(_ lat: Double, _ lon: Double) -> AirportTile {
        AirportTile(lat: min(89, Int(floor(lat))), lon: wrapLon(Int(floor(lon))))
    }

    /// Every tile within `radiusKm` of the route through `points`, plus the
    /// departure and arrival tiles; sorted.
    public static func tiles(points: [(lat: Double, lon: Double)], radiusKm: Double) -> [AirportTile] {
        guard let first = points.first, let last = points.last else { return [] }
        let radius = max(0.0, radiusKm)
        var chosen: Set<AirportTile> = [tileOf(first.lat, first.lon), tileOf(last.lat, last.lon)]
        for s in densify(points) {
            chosen.insert(tileOf(s.lat, s.lon))
            for tile in candidateTiles(s.lat, s.lon, radius) where !chosen.contains(tile) {
                if tileDistanceKm(s.lat, s.lon, tile.lat, tile.lon) <= radius {
                    chosen.insert(tile)
                }
            }
        }
        return chosen.sorted { ($0.lat, $0.lon) < ($1.lat, $1.lon) }
    }

    /// The densified route as polylines for a flat map: split where it
    /// crosses the antimeridian, each piece ending on ±180.
    public static func drawing(points: [(lat: Double, lon: Double)]) -> [[GeoPoint]] {
        let dense = densify(points)
        guard let head = dense.first else { return [] }
        var parts: [[GeoPoint]] = [[GeoPoint(lon: head.lon, lat: head.lat)]]
        for (p0, p1) in zip(dense, dense.dropFirst()) {
            if abs(p1.lon - p0.lon) > 180.0 {
                let edge = p0.lon > 0 ? 180.0 : -180.0
                let unwrapped = p1.lon + (p0.lon > 0 ? 360.0 : -360.0)
                let t = (edge - p0.lon) / (unwrapped - p0.lon)
                let latX = p0.lat + t * (p1.lat - p0.lat)
                parts[parts.count - 1].append(GeoPoint(lon: edge, lat: latX))
                parts.append([GeoPoint(lon: -edge, lat: latX)])
            }
            parts[parts.count - 1].append(GeoPoint(lon: p1.lon, lat: p1.lat))
        }
        return parts
    }

    // MARK: - Units and words

    /// The radius control's value in km (`unit` "km" or "nm").
    public static func radiusKm(_ value: Double, unit: String) -> Double {
        value * (unit == "nm" ? kmPerNm : 1.0)
    }

    public static func routeLengthKm(_ points: [(lat: Double, lon: Double)]) -> Double {
        let vecs = points.map { vec($0.lat, $0.lon) }
        var total = 0.0
        for (a, b) in zip(vecs, vecs.dropFirst()) { total += centralAngle(a, b) }
        return earthRadiusKm * total
    }

    /// "1,234" — grouping by comma whatever the locale (as Python's ",").
    static func grouped(_ n: Int) -> String {
        let digits = String(abs(n))
        var out = ""
        for (i, ch) in digits.enumerated() {
            if i > 0, (digits.count - i) % 3 == 0 { out.append(",") }
            out.append(ch)
        }
        return n < 0 ? "-" + out : out
    }

    /// "ORIG → DEST · 4 waypoints · 233 km".
    public static func summaryText(_ plan: FlightPlan, unit: String) -> String {
        var length = routeLengthKm(plan.points)
        if unit == "nm" { length /= kmPerNm }
        let origin = plan.origin.isEmpty ? "?" : plan.origin
        let destination = plan.destination.isEmpty ? "?" : plan.destination
        return "\(origin) \u{2192} \(destination) \u{00B7} \(plan.waypoints.count) waypoints \u{00B7} "
            + "\(grouped(Int(length.rounded(.toNearestOrEven)))) \(unit)"
    }

    /// "12 tiles selected".
    public static func tilesText(_ count: Int) -> String {
        "\(grouped(count)) tile\(count == 1 ? "" : "s") selected"
    }
}
