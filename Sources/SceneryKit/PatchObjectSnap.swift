import Foundation

/// Shape nodes snap to pack objects too (#1703, owner decision (3)(a)): to
/// an object's footprint corners and the middle of each footprint edge.
/// Pure functions of plan points (any planar frame — the map's mercator
/// plane, or screen points), so they are tested without a window; Qt's
/// `O4_Qt_Object_Seat.vertex_at` is the same rule.
public enum PatchObjectSnap {
    /// A ring's snap points: each corner, then the middle of each edge
    /// (the ring is closed implicitly; a repeated closing point is dropped).
    public static func vertices(_ ring: [SIMD2<Double>]) -> [SIMD2<Double>] {
        var r = ring
        if r.count > 1, r.first == r.last { r.removeLast() }
        guard r.count >= 2 else { return r }
        let mids = r.indices.map { (r[$0] + r[($0 + 1) % r.count]) / 2 }
        return r + mids
    }

    /// The nearest of `points` to `pointer` within `radius` (inclusive), as
    /// its index; ties go to the first.
    public static func nearest(_ pointer: SIMD2<Double>, in points: [SIMD2<Double>], radius: Double) -> Int? {
        var best: (i: Int, d: Double)?
        for (i, p) in points.enumerated() {
            let d = hypot(p.x - pointer.x, p.y - pointer.y)
            if d <= radius, best == nil || d < best!.d { best = (i, d) }
        }
        return best?.i
    }
}
