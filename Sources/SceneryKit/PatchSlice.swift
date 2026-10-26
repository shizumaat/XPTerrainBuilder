import Foundation

// Slice (issue #1318; owner rulings Q130–Q133): one shape cut in two along
// the straight line between two of its nodes that are not neighbours,
// leaving a 0.5 m gap. The Swift twin of `Ortho4XP/src/o4_engine/patch_slice.py`
// (the geometry) and `patch_edit.slice_shape` (the document edit); both run
// the `slice_shape` cases of `Ortho4XP/tests/fixtures/patch_edit_ops.json`.
//
// * Each cut node becomes two nodes `gapM` apart, half the gap either side
//   of the cut line, perpendicular to it, each keeping its height.
// * A hole the cut crosses (an `o4_feature=gap_interior_ring` ring of the
//   shape) gets two new nodes at each crossing, height interpolated along
//   its edge, and stops being a way: its sides become notches.
// * The half with the larger plan area keeps the way id, its place and the
//   two nodes' ids; the other half is a new way right after it. Both keep
//   the tags. Refused: a cut that leaves or runs along the outline, one
//   through a hole's corner, one that would leave more than two pieces.
//
// Working orientation: the outer ring counter-clockwise, holes clockwise,
// so the shape is on the LEFT of every directed edge; "left" is the side
// left of the direction a → b.

public enum PatchSlice {
    /// The gap a slice leaves between the two halves (owner Q130), metres.
    public static let gapM = 0.5

    enum Side: Hashable { case left, right }

    /// A ring entry: a node, or the copy of cut point `k` on one side.
    enum Label: Hashable {
        case node(Int64)
        case cut(Int, Side)
    }

    struct Cut {
        /// The two halves, each starting at its copy of a, counter-clockwise.
        let left: [Label]
        let right: [Label]
        /// Every cut point: a, the hole crossings in order, b.
        let points: [(lat: Double, lon: Double, alt: Double?)]
        let copies: [Label: (lat: Double, lon: Double)]
        let leftArea: Double
        let rightArea: Double
        /// Whether the input outer ring was counter-clockwise.
        let ccw: Bool
        /// The holes the cut crossed.
        let crossed: [Int64]
    }

    typealias P = (x: Double, y: Double)

    static func orient(_ p: P, _ q: P, _ r: P) -> Double {
        (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)
    }

    /// Signed plan area (positive counter-clockwise) of an open ring.
    static func ringArea(_ pts: [P]) -> Double {
        var s = 0.0
        for i in pts.indices {
            let p = pts[i], q = pts[(i + 1) % pts.count]
            s += p.x * q.y - q.x * p.y
        }
        return s / 2.0
    }

    /// Even-odd point in an open ring.
    static func inside(_ p: P, _ pts: [P]) -> Bool {
        var hit = false
        for i in pts.indices {
            let u = pts[i], v = pts[(i + 1) % pts.count]
            if (u.y > p.y) != (v.y > p.y), p.x < u.x + (p.y - u.y) * (v.x - u.x) / (v.y - u.y) { hit.toggle() }
        }
        return hit
    }

    private static func onSegment(_ p: P, _ q: P, _ r: P) -> Bool {
        min(p.x, q.x) <= r.x && r.x <= max(p.x, q.x) && min(p.y, q.y) <= r.y && r.y <= max(p.y, q.y)
    }

    /// The closed segments p1–p2 and q1–q2 share a point.
    static func touch(_ p1: P, _ p2: P, _ q1: P, _ q2: P) -> Bool {
        let o1 = orient(p1, p2, q1), o2 = orient(p1, p2, q2)
        let o3 = orient(q1, q2, p1), o4 = orient(q1, q2, p2)
        if ((o1 > 0 && o2 < 0) || (o1 < 0 && o2 > 0)) && ((o3 > 0 && o4 < 0) || (o3 < 0 && o4 > 0)) {
            return true
        }
        return (o1 == 0 && onSegment(p1, p2, q1)) || (o2 == 0 && onSegment(p1, p2, q2))
            || (o3 == 0 && onSegment(q1, q2, p1)) || (o4 == 0 && onSegment(q1, q2, p2))
    }

    private static func refuse(_ why: String) -> PatchEditError { .sliceRefused(why) }

    /// Slice the shape `outer` (an OPEN ring of node ids) with `holes`
    /// along a → b. Throws `PatchEditError.sliceRefused`.
    static func cut(outer: [Int64], holes: [(key: Int64, ring: [Int64])], nodes: [Int64: PatchNode],
                    a: Int64, b: Int64, gap: Double = gapM) throws -> Cut {
        let n = outer.count
        guard outer.filter({ $0 == a }).count == 1, outer.filter({ $0 == b }).count == 1,
              let ia = outer.firstIndex(of: a), let ib = outer.firstIndex(of: b) else {
            throw refuse("Slice needs two nodes that are each on the shape's outline once.")
        }
        let apart = ((ia - ib) % n + n) % n
        if a == b || apart == 1 || apart == n - 1 {
            throw refuse("Slice needs two nodes that are not neighbours on the shape.")
        }
        let mLat = PatchLocalFrame.metresPerDegreeLat
        let na = nodes[a]!, nb = nodes[b]!
        let lat0 = (na.lat + nb.lat) / 2.0, lon0 = (na.lon + nb.lon) / 2.0
        let mLon = mLat * max(cos(lat0 * (Double.pi / 180.0)), 1.0e-6)
        func xy(_ id: Int64) -> P {
            let node = nodes[id]!
            return ((node.lon - lon0) * mLon, (node.lat - lat0) * mLat)
        }
        let A = xy(a), B = xy(b)
        let length = hypot(B.x - A.x, B.y - A.y)
        if length == 0.0 { throw refuse("The two nodes are at the same place.") }
        let area = ringArea(outer.map(xy))
        if area == 0.0 { throw refuse("The shape has no area.") }
        let ccw = area > 0.0
        let ring: [Int64] = ccw ? outer : Array(outer.reversed())
        let pts = ring.map(xy)
        let m = ring.count

        let leaves = "The cut line leaves the shape."
        for i in 0..<m {
            let u = ring[i], v = ring[(i + 1) % m]
            let U = pts[i], V = pts[(i + 1) % m]
            if u == a || u == b || v == a || v == b {
                let x = (u == a || v == a) ? a : b
                let (X, Y) = x == u ? (U, V) : (V, U)
                let far = x == a ? B : A
                if orient(A, B, Y) == 0.0, (Y.x - X.x) * (far.x - X.x) + (Y.y - X.y) * (far.y - X.y) > 0.0 {
                    throw refuse("The cut line runs along the shape's edge.")
                }
            } else if touch(A, B, U, V) {
                throw refuse(leaves)
            }
        }
        if !inside(((A.x + B.x) / 2.0, (A.y + B.y) / 2.0), pts) { throw refuse(leaves) }

        // Hole crossings: t along a → b, hole index, the edge, s along it.
        var holeRings: [[Int64]] = []
        var keys: [Int64] = []
        var crossings: [(t: Double, hole: Int, u: Int64, v: Int64, s: Double)] = []
        for hole in holes {
            var h = hole.ring
            guard h.count >= 3 else { continue }
            var hp = h.map(xy)
            if ringArea(hp) > 0.0 {
                h.reverse()
                hp.reverse()
            }
            var found: [(t: Double, hole: Int, u: Int64, v: Int64, s: Double)] = []
            for i in h.indices {
                let U = hp[i], V = hp[(i + 1) % h.count]
                guard touch(A, B, U, V) else { continue }
                let o1 = orient(A, B, U), o2 = orient(A, B, V)
                let o3 = orient(U, V, A), o4 = orient(U, V, B)
                guard o1 * o2 < 0.0, o3 * o4 < 0.0 else {
                    throw refuse("The cut line passes through a corner of a hole; move a node slightly.")
                }
                found.append((o3 / (o3 - o4), holeRings.count, h[i], h[(i + 1) % h.count], o1 / (o1 - o2)))
            }
            if found.isEmpty { continue }
            if h.contains(a) || h.contains(b) || !hp.allSatisfy({ inside($0, pts) }) {
                throw refuse("The cut line crosses a hole that is not inside this shape.")
            }
            holeRings.append(h)
            keys.append(hole.key)
            crossings += found
        }
        crossings = crossings.enumerated().sorted { ($0.element.t, $0.offset) < ($1.element.t, $1.offset) }
            .map(\.element)
        let equalT = zip(crossings, crossings.dropFirst()).contains { pair in pair.0.t == pair.1.t }
        let unpaired = stride(from: 0, to: crossings.count, by: 2).contains {
            $0 + 1 >= crossings.count || crossings[$0].hole != crossings[$0 + 1].hole
        }
        if crossings.count % 2 != 0 || equalT || unpaired {
            throw refuse("The cut line crosses holes that overlap.")
        }

        // The cut points: a, the crossings in order, b.
        let last = crossings.count + 1
        var points: [(lat: Double, lon: Double, alt: Double?)] = [(na.lat, na.lon, na.alt)]
        for c in crossings {
            let cu = nodes[c.u]!, cv = nodes[c.v]!
            let alt: Double? = if let x = cu.alt, let y = cv.alt { x + c.s * (y - x) } else { nil }
            points.append((cu.lat + c.s * (cv.lat - cu.lat), cu.lon + c.s * (cv.lon - cu.lon), alt))
        }
        points.append((nb.lat, nb.lon, nb.alt))

        // The directed boundary, one successor per entry.
        var succ: [Label: Label] = [:]
        var order: [Label] = []
        func link(_ src: Label, _ dst: Label) throws {
            guard succ[src] == nil else {
                throw refuse("The shape's outline and a hole share a node; the cut cannot be traced.")
            }
            succ[src] = dst
            order.append(src)
        }
        func outOf(_ id: Int64) -> Label { id == a ? .cut(0, .right) : id == b ? .cut(last, .left) : .node(id) }
        func into(_ id: Int64) -> Label { id == a ? .cut(0, .left) : id == b ? .cut(last, .right) : .node(id) }
        for i in 0..<m { try link(outOf(ring[i]), into(ring[(i + 1) % m])) }

        func side(_ id: Int64) -> Side { orient(A, B, xy(id)) > 0.0 ? .left : .right }
        var onEdge: [[Int64]: Int] = [:]
        for (k, c) in crossings.enumerated() { onEdge[[c.u, c.v]] = k + 1 }
        for h in holeRings {
            for i in h.indices {
                let u = h[i], v = h[(i + 1) % h.count]
                if let k = onEdge[[u, v]] {
                    try link(.node(u), .cut(k, side(u)))
                    try link(.cut(k, side(v)), .node(v))
                } else {
                    try link(.node(u), .node(v))
                }
            }
        }
        for p in stride(from: 0, to: last, by: 2) {
            try link(.cut(p, .left), .cut(p + 1, .left))
            try link(.cut(p + 1, .right), .cut(p, .right))
        }

        var cycles: [[Label]] = []
        var seen: Set<Label> = []
        for start in [Label.cut(0, .left), .cut(0, .right)] + order where !seen.contains(start) {
            var cycle: [Label] = []
            var x = start
            while !seen.contains(x) {
                seen.insert(x)
                cycle.append(x)
                guard let next = succ[x] else { throw refuse("The cut cannot be traced through this shape.") }
                x = next
            }
            if x != start { throw refuse("The cut cannot be traced through this shape.") }
            cycles.append(cycle)
        }
        guard cycles.count == 2, cycles[0].contains(.cut(last, .left)), cycles[1].contains(.cut(last, .right)) else {
            throw refuse("The cut would leave more than two pieces.")
        }

        // The copies, half the gap either side of the cut line.
        let nx = -(B.y - A.y) / length, ny = (B.x - A.x) / length
        let half = gap / 2.0
        var copies: [Label: (lat: Double, lon: Double)] = [:]
        for (k, p) in points.enumerated() {
            for (sd, sign) in [(Side.left, 1.0), (Side.right, -1.0)] {
                copies[.cut(k, sd)] = (p.lat + sign * half * ny / mLat, p.lon + sign * half * nx / mLon)
            }
        }
        func areaOf(_ cycle: [Label]) -> Double {
            ringArea(cycle.map { label -> P in
                switch label {
                case .node(let id): return xy(id)
                case .cut:
                    let c = copies[label]!
                    return ((c.lon - lon0) * mLon, (c.lat - lat0) * mLat)
                }
            })
        }
        return Cut(left: cycles[0], right: cycles[1], points: points, copies: copies,
                   leftArea: areaOf(cycles[0]), rightArea: areaOf(cycles[1]), ccw: ccw, crossed: keys)
    }
}

extension PatchDocument {
    private static func isSurface(_ way: PatchWay) -> Bool {
        way.isClosed && way.refs.count > 3 && way.tags["o4_feature"] == nil
    }

    /// The id a new way gets: one below the document's minimum way id.
    public var nextNewWayID: Int64 { min(ways.map(\.id).min() ?? 0, 0) - 1 }

    /// The shape a slice between a and b would cut: the one shape whose
    /// outline holds both (`way` when given), the two not neighbours on it
    /// — when Slice is offered. Throws saying why there is none.
    public func sliceWay(_ a: Int64, _ b: Int64, way: Int64? = nil) throws -> PatchWay {
        for id in [a, b] where nodes[id] == nil { throw PatchEditError.unknownNode(id) }
        let hits = ways.filter {
            Self.isSurface($0) && $0.refs.contains(a) && $0.refs.contains(b) && (way == nil || $0.id == way)
        }
        guard a != b, let hit = hits.first else {
            throw PatchEditError.sliceRefused("Slice needs two nodes of the same shape.")
        }
        guard hits.count == 1 else {
            throw PatchEditError.sliceRefused("These nodes are on more than one shape: select the shape first.")
        }
        let ring = Array(hit.refs.dropLast())
        let apart = ((ring.firstIndex(of: a)! - ring.firstIndex(of: b)!) % ring.count + ring.count) % ring.count
        if apart == 1 || apart == ring.count - 1 {
            throw PatchEditError.sliceRefused("Slice needs two nodes that are not neighbours on the shape.")
        }
        return hit
    }

    /// Slice the shape holding a and b (`way` picks it when several do)
    /// along a → b (#1318; the rules are this file's header). New nodes
    /// count down from `nextNewNodeID` along the cut: a's copy, each
    /// crossing's left then right copy, b's copy.
    public mutating func sliceShape(_ a: Int64, _ b: Int64, way: Int64? = nil) throws {
        let target = try sliceWay(a, b, way: way)
        let sid = target.tags["shapeID"]
        let holes = ways.filter {
            $0.isClosed && $0.tags["o4_feature"] == PatchShapeAssembly.holeFeature
                && (sid == nil || $0.tags["shapeID"] == nil || $0.tags["shapeID"] == sid)
        }.map { (key: $0.id, ring: Array($0.refs.dropLast())) }
        let c = try PatchSlice.cut(outer: Array(target.refs.dropLast()), holes: holes, nodes: nodes, a: a, b: b)
        // A tie (within float noise, so both apps agree) goes to the left half.
        let keep: PatchSlice.Side = c.rightArea > c.leftArea * (1.0 + 1.0e-9) ? .right : .left
        let other: PatchSlice.Side = keep == .right ? .left : .right
        let last = c.points.count - 1
        var ids: [PatchSlice.Label: Int64] = [:]
        var newID = nextNewNodeID
        for (k, point) in c.points.enumerated() {
            let ends = k == 0 || k == last
            if ends {
                let original = k == 0 ? a : b
                let copy = c.copies[.cut(k, keep)]!
                ids[.cut(k, keep)] = original
                nodes[original]!.lat = copy.lat
                nodes[original]!.lon = copy.lon
            }
            let sides: [PatchSlice.Side] = ends ? [other] : [.left, .right]
            for side in sides {
                let copy = c.copies[.cut(k, side)]!
                ids[.cut(k, side)] = newID
                nodes[newID] = PatchNode(id: newID, lat: copy.lat, lon: copy.lon, alt: point.alt)
                nodeOrder.append(newID)
                newID -= 1
            }
        }
        func refs(_ cycle: [PatchSlice.Label]) -> [Int64] {
            var ring = cycle.map { label -> Int64 in
                switch label {
                case .node(let id): return id
                case .cut: return ids[label]!
                }
            }
            if !c.ccw { ring = [ring[0]] + ring.dropFirst().reversed() }
            return ring + [ring[0]]
        }
        let halves: [PatchSlice.Side: [PatchSlice.Label]] = [.left: c.left, .right: c.right]
        let crossed = Set(c.crossed)
        let wayID = nextNewWayID
        var out: [PatchWay] = []
        for w in ways {
            if w.id == target.id {
                var kept = w
                kept.refs = refs(halves[keep]!)
                out.append(kept)
                out.append(PatchWay(id: wayID, refs: refs(halves[other]!), tags: w.tags))
            } else if !crossed.contains(w.id) {
                out.append(w)
            }
        }
        ways = out
        reindex()
    }
}
