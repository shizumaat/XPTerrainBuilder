import Foundation

// Rotating whole shapes in the patch editor (#1746): Option-drag near a
// shape's node turns the shape about its centre. The Swift twin of
// `Ortho4XP/src/o4_engine/patch_rotate.py` (+ `patch_edit.rotate_ways`);
// both run the `rotate_ways` cases of `patch_edit_ops.json`.

/// The rotation geometry the gesture's live preview and the edit share.
public enum PatchRotate {
    private static func k(_ lat: Double) -> Double { max(cos(lat * .pi / 180), 1.0e-6) }

    /// The pivot of the ways whose refs are `rings` (a closed way repeats
    /// its first ref last): the area-weighted centroid of the closed ones,
    /// or the mean of the distinct nodes when they enclose no area.
    public static func centre(nodes: [Int64: PatchNode], rings: [[Int64]]) -> (lat: Double, lon: Double)? {
        let rings = rings.map { $0.filter { nodes[$0] != nil } }
        var seen = Set<Int64>(), distinct: [PatchNode] = []
        for id in rings.joined() where seen.insert(id).inserted { distinct.append(nodes[id]!) }
        guard !distinct.isEmpty else { return nil }
        let lat0 = distinct.reduce(0) { $0 + $1.lat } / Double(distinct.count)
        let lon0 = distinct.reduce(0) { $0 + $1.lon } / Double(distinct.count)
        let k = k(lat0)
        var area = 0.0, cx = 0.0, cy = 0.0
        for refs in rings where refs.count >= 4 && refs.first == refs.last {
            let pts = refs.map { ((nodes[$0]!.lon - lon0) * k, nodes[$0]!.lat - lat0) }
            var a = 0.0, sx = 0.0, sy = 0.0
            for (p, q) in zip(pts, pts.dropFirst()) {
                let cross = p.0 * q.1 - q.0 * p.1
                a += cross
                sx += (p.0 + q.0) * cross
                sy += (p.1 + q.1) * cross
            }
            guard abs(a) > 0 else { continue }
            let w = abs(a) / 2  // a ring's centroid is (sx, sy) / (3a)
            area += w
            cx += w * sx / (3 * a)
            cy += w * sy / (3 * a)
        }
        guard area > 1.0e-18 else { return (lat0, lon0) }
        return (lat0 + cy / area, lon0 + cx / (area * k))
    }

    /// `(lat, lon)` turned about `pivot` by `degrees`, counter-clockwise
    /// seen from above (north up), in the pivot's east/north plane.
    public static func rotate(lat: Double, lon: Double, about pivot: (lat: Double, lon: Double),
                              degrees: Double) -> (lat: Double, lon: Double) {
        let k = k(pivot.lat)
        let x = (lon - pivot.lon) * k, y = lat - pivot.lat
        let c = cos(degrees * .pi / 180), s = sin(degrees * .pi / 180)
        return (pivot.lat + x * s + y * c, pivot.lon + (x * c - y * s) / k)
    }
}

extension PatchDocument {
    /// The pivot `rotateWays` turns these ways about (nil: none of them).
    public func rotationCentre(of wayIDs: Set<Int64>) -> (lat: Double, lon: Double)? {
        PatchRotate.centre(nodes: nodes, rings: ways.filter { wayIDs.contains($0.id) }.map(\.refs))
    }

    /// Turn every node of the ways by `degrees` (counter-clockwise, north
    /// up) about their `rotationCentre`. Elevations kept; never merges.
    public mutating func rotateWays(_ wayIDs: [Int64], degrees: Double) throws {
        let present = Set(ways.map(\.id))
        for id in wayIDs where !present.contains(id) { throw PatchEditError.unknownWay(id) }
        let wanted = Set(wayIDs)
        guard let pivot = rotationCentre(of: wanted) else { return }
        var seen = Set<Int64>()
        for id in ways.filter({ wanted.contains($0.id) }).flatMap(\.refs)
        where nodes[id] != nil && seen.insert(id).inserted {
            let p = PatchRotate.rotate(lat: nodes[id]!.lat, lon: nodes[id]!.lon, about: pivot, degrees: degrees)
            nodes[id]!.lat = p.lat
            nodes[id]!.lon = p.lon
        }
        reindex()
    }
}
