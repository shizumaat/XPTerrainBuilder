import Foundation

// Which rings of a patch make one surface for the 3D preview
// (Ortho4XP/docs/specs/patch-editor-20261015.md §5). A SURFACE is a closed
// way without an `o4_feature` tag (runway, taxiway, apron, building,
// graded strip …). Its holes are:
//   1. the `o4_feature=gap_interior_ring` rings paired with it — the emit
//      (`auto_patch_v2/emit/osm_adapter.py`) writes an uncovered hole of
//      face F as a closed way tagged with F's `shapeID`; the hole goes to
//      the smallest surface that contains it, among the surfaces with the
//      hole's `shapeID` when it has one (v1 patches write none), else
//      among all surfaces;
//   2. the surfaces nested directly inside it — the emit does NOT write a
//      hole that the faces inside it cover ("the hole IS the faces inside
//      it"), so the outer face's ring runs round them; the mesh's
//      constrained triangulation gives that area the inner faces'
//      elevations, and so does the preview. A face inside one of its
//      parent's gap rings is not a second hole of the parent.
// Structure rims, crown spines and other `o4_feature` ways are not surfaces.

/// One surface: an outer ring and its holes, node ids, rings OPEN (the
/// closing id dropped).
public struct PatchShape: Equatable, Sendable {
    public let wayID: Int64
    public var outer: [Int64]
    public var holes: [[Int64]]

    public init(wayID: Int64, outer: [Int64], holes: [[Int64]] = []) {
        self.wayID = wayID; self.outer = outer; self.holes = holes
    }

    /// Every node the shape draws.
    public var nodeIDs: Set<Int64> { Set(outer).union(holes.joined()) }
}

public enum PatchShapeAssembly {
    public static let holeFeature = "gap_interior_ring"

    public static func isSurface(_ way: PatchWay) -> Bool {
        way.isClosed && way.tags["o4_feature"] == nil
    }

    public static func isGapRing(_ way: PatchWay) -> Bool {
        way.isClosed && way.tags["o4_feature"] == holeFeature
    }

    /// Every surface of the document with its holes, in way order.
    public static func shapes(of document: PatchDocument) -> [PatchShape] {
        let frame = document.frame
        func ring(_ way: PatchWay) -> Ring? {
            var ids = way.refs
            if ids.count > 1, ids.first == ids.last { ids.removeLast() }
            let pts = ids.compactMap { id in document.nodes[id].map { frame.metres(lat: $0.lat, lon: $0.lon) } }
            guard pts.count == ids.count, pts.count >= 3 else { return nil }
            return Ring(ids: ids, points: pts)
        }
        var surfaces: [(way: PatchWay, ring: Ring)] = []
        var gaps: [(way: PatchWay, ring: Ring)] = []
        for way in document.ways {
            if isSurface(way), let r = ring(way) { surfaces.append((way, r)) }
            else if isGapRing(way), let r = ring(way) { gaps.append((way, r)) }
        }
        var shapes = surfaces.map { PatchShape(wayID: $0.way.id, outer: $0.ring.ids) }
        var gapRings: [[Ring]] = Array(repeating: [], count: surfaces.count)

        // 1. gap rings → the smallest containing surface (same shapeID first)
        for gap in gaps {
            let sid = gap.way.tags["shapeID"]
            let tagged = sid == nil ? [] : surfaces.indices.filter { surfaces[$0].way.tags["shapeID"] == sid }
            let pool = tagged.isEmpty ? Array(surfaces.indices) : tagged
            var best = smallestContaining(gap.ring, among: pool, surfaces.map(\.ring))
            if best == nil && !tagged.isEmpty {
                best = smallestContaining(gap.ring, among: Array(surfaces.indices), surfaces.map(\.ring))
            }
            guard let host = best else { continue }
            shapes[host].holes.append(gap.ring.ids)
            gapRings[host].append(gap.ring)
        }

        // 2. a surface nested in another is a hole of its direct parent
        let rings = surfaces.map(\.ring)
        for g in surfaces.indices {
            let others = surfaces.indices.filter { $0 != g && rings[$0].area > rings[g].area }
            guard let parent = smallestContaining(rings[g], among: others, rings) else { continue }
            if gapRings[parent].contains(where: { $0.contains(rings[g]) }) { continue }
            shapes[parent].holes.append(rings[g].ids)
        }
        return shapes
    }

    private static func smallestContaining(_ inner: Ring, among pool: [Int], _ rings: [Ring]) -> Int? {
        var best: Int?
        for i in pool where rings[i].contains(inner) {
            if best == nil || rings[i].area < rings[best!].area { best = i }
        }
        return best
    }
}

/// A ring in the document's metric plane, with what containment needs.
struct Ring {
    let ids: [Int64]
    let points: [(x: Double, y: Double)]
    let minX, minY, maxX, maxY: Double
    let area: Double

    /// Metres within which a point counts as ON a ring edge (well under
    /// the law's 0.5 m node spacing, well over coordinate round-off).
    static let boundaryEps = 1.0e-4

    init(ids: [Int64], points: [(x: Double, y: Double)]) {
        self.ids = ids
        self.points = points
        minX = points.map(\.x).min()!; maxX = points.map(\.x).max()!
        minY = points.map(\.y).min()!; maxY = points.map(\.y).max()!
        var flat: [Double] = []
        flat.reserveCapacity(points.count * 2)
        for p in points { flat.append(p.x); flat.append(p.y) }
        area = abs(PatchTriangulator.signedArea(flat))
    }

    /// `other` lies inside this ring (touching allowed) and is not the same
    /// ring: every vertex and every edge midpoint inside or on the boundary,
    /// and no edge of one crossing an edge of the other.
    func contains(_ other: Ring) -> Bool {
        let e = Self.boundaryEps
        guard other.minX >= minX - e, other.maxX <= maxX + e,
              other.minY >= minY - e, other.maxY <= maxY + e,
              Set(other.ids) != Set(ids) else { return false }
        var strictlyInside = false
        var j = other.points.count - 1
        for i in other.points.indices {
            let p = other.points[i], q = other.points[j]
            for probe in [p, ((p.x + q.x) / 2, (p.y + q.y) / 2)] {
                switch locate(probe) {
                case .outside: return false
                case .inside: strictlyInside = true
                case .boundary: continue
                }
            }
            j = i
        }
        // a ring whose every probe is on this boundary bounds nothing inside
        return strictlyInside && !crosses(other)
    }

    /// Some edge of `other` properly crosses an edge of this ring.
    func crosses(_ other: Ring) -> Bool {
        func orient(_ a: (x: Double, y: Double), _ b: (x: Double, y: Double), _ c: (x: Double, y: Double)) -> Double {
            (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
        }
        var j = other.points.count - 1
        for i in other.points.indices {
            let a = other.points[j], b = other.points[i]
            var l = points.count - 1
            for k in points.indices {
                let c = points[l], d = points[k]
                let o1 = orient(a, b, c), o2 = orient(a, b, d)
                let o3 = orient(c, d, a), o4 = orient(c, d, b)
                if ((o1 > 0 && o2 < 0) || (o1 < 0 && o2 > 0)) && ((o3 > 0 && o4 < 0) || (o3 < 0 && o4 > 0)) {
                    return true
                }
                l = k
            }
            j = i
        }
        return false
    }

    enum Location { case inside, outside, boundary }

    func locate(_ p: (x: Double, y: Double)) -> Location {
        var inside = false
        var j = points.count - 1
        for i in points.indices {
            let a = points[j], b = points[i]
            if Self.segmentDistance(p, a, b) <= Self.boundaryEps { return .boundary }
            if (a.y > p.y) != (b.y > p.y),
               p.x < (b.x - a.x) * (p.y - a.y) / (b.y - a.y) + a.x {
                inside.toggle()
            }
            j = i
        }
        return inside ? .inside : .outside
    }

    static func segmentDistance(_ p: (x: Double, y: Double), _ a: (x: Double, y: Double),
                                _ b: (x: Double, y: Double)) -> Double {
        let dx = b.x - a.x, dy = b.y - a.y
        let len2 = dx * dx + dy * dy
        let t = len2 > 0 ? max(0, min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0
        return hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy))
    }
}
