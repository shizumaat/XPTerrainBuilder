import Foundation

/// The pack's building footprints on the patch editor's map (spec §2 as
/// amended before L4, §4): the PLAN OUTLINE of each placed model — the
/// 2-D convex hull of its grey-massing vertices, turned by the placement's
/// heading — and each roofed facade's ring, all from one `pack_objects`
/// result: the map asks `footprintsOnly` (each model's plan hull, #797),
/// and a full answer (the 3D window's) serves it too. Pure; rings are
/// `[lat, lon]`.
public enum PackFootprints {
    /// One ring per drawn placement (a model with fewer than three distinct
    /// plan points has none), then one per facade.
    public static func outlines(_ objects: O4PackObjects) -> [[O4LatLon]] {
        var hulls: [String: [SIMD2<Double>]] = [:]
        for model in objects.models {
            hulls[model.key] = model.planHull.isEmpty
                ? planHull(authored: model.vertices) : pairs(model.planHull)
        }
        var out: [[O4LatLon]] = []
        out.reserveCapacity(objects.placements.count + objects.facades.count)
        for p in objects.placements {
            guard let hull = hulls[p.model], hull.count >= 3 else { continue }
            out.append(place(hull, lat: p.lat, lon: p.lon, headingDeg: p.headingDeg))
        }
        for f in objects.facades where f.ring.count >= 3 { out.append(f.ring) }
        return out
    }

    /// A footprints-only answer's plan hull: `(x, z)` pairs, already a hull.
    static func pairs(_ flat: [Float]) -> [SIMD2<Double>] {
        stride(from: 0, to: flat.count - 1, by: 2).map { SIMD2(Double(flat[$0]), Double(flat[$0 + 1])) }
    }

    /// The plan hull of authored `(x, y, z)` triples, as `(x, z)` points
    /// (x east, z south at heading 0).
    public static func planHull(authored vertices: [Float]) -> [SIMD2<Double>] {
        var points: [SIMD2<Double>] = []
        points.reserveCapacity(vertices.count / 3)
        var i = 0
        while i + 2 < vertices.count {
            points.append(SIMD2(Double(vertices[i]), Double(vertices[i + 2])))
            i += 3
        }
        return convexHull(points)
    }

    /// Andrew's monotone chain; collinear points dropped.
    public static func convexHull(_ points: [SIMD2<Double>]) -> [SIMD2<Double>] {
        let p = points.sorted { $0.x != $1.x ? $0.x < $1.x : $0.y < $1.y }
        guard p.count >= 3 else { return p }
        func cross(_ o: SIMD2<Double>, _ a: SIMD2<Double>, _ b: SIMD2<Double>) -> Double {
            (a.x - o.x) * (b.y - o.y) - (a.y - o.y) * (b.x - o.x)
        }
        var lower: [SIMD2<Double>] = [], upper: [SIMD2<Double>] = []
        for q in p {
            while lower.count >= 2, cross(lower[lower.count - 2], lower[lower.count - 1], q) <= 0 { lower.removeLast() }
            lower.append(q)
        }
        for q in p.reversed() {
            while upper.count >= 2, cross(upper[upper.count - 2], upper[upper.count - 1], q) <= 0 { upper.removeLast() }
            upper.append(q)
        }
        return Array(lower.dropLast() + upper.dropLast())
    }

    /// An authored plan hull at a placement: turned by the heading the way
    /// `PatchBuildingPose` turns the model (clockwise from north), then
    /// offset in metres from the anchor.
    static func place(_ hull: [SIMD2<Double>], lat: Double, lon: Double, headingDeg: Double) -> [O4LatLon] {
        let h = headingDeg * .pi / 180
        let c = cos(h), s = sin(h)
        let mLat = PatchLocalFrame.metresPerDegreeLat
        let mLon = mLat * max(cos(lat * .pi / 180), 1e-6)
        return hull.map { q in
            let east = c * q.x - s * q.y
            let north = -(s * q.x + c * q.y)
            return O4LatLon(lat: lat + north / mLat, lon: lon + east / mLon)
        }
    }
}
