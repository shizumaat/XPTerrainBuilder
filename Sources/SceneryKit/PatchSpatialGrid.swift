import Foundation

/// A uniform grid over a `PatchDocument` in its local metric frame, for
/// hit-testing nodes and edges (patch-editor spec §4: 8 pt click radius,
/// box select, "+" handles). Rebuilt from the document after an edit;
/// queries take metres in `document.frame`.
public struct PatchSpatialGrid: Sendable {
    /// One way segment: `refs[segment]` → `refs[segment + 1]` of `ways[way]`.
    public struct Edge: Hashable, Sendable {
        public let way: Int
        public let segment: Int
    }

    public struct EdgeHit: Equatable, Sendable {
        public let edge: Edge
        public let a: Int64
        public let b: Int64
        /// Distance from the query point, metres.
        public let distance: Double
        /// Where along a → b the nearest point lies (0…1).
        public let t: Double
    }

    public let cellSize: Double
    private let frame: PatchLocalFrame
    private var points: [Int64: (x: Double, y: Double)] = [:]
    private var nodeCells: [Int64: [Int64]] = [:]
    private var edgeCells: [Int64: [Edge]] = [:]
    private var edgeEnds: [Edge: (Int64, Int64)] = [:]

    public init(document: PatchDocument, cellSize: Double = 25) {
        self.cellSize = cellSize
        frame = document.frame
        for (id, node) in document.nodes {
            let p = frame.metres(lat: node.lat, lon: node.lon)
            points[id] = p
            nodeCells[cellKey(p.x, p.y), default: []].append(id)
        }
        for (w, way) in document.ways.enumerated() where way.refs.count > 1 {
            for s in 0..<(way.refs.count - 1) {
                let a = way.refs[s], b = way.refs[s + 1]
                guard a != b, let pa = points[a], let pb = points[b] else { continue }
                let edge = Edge(way: w, segment: s)
                edgeEnds[edge] = (a, b)
                insert(edge, from: pa, to: pb)
            }
        }
    }

    /// The node nearest (x, y) within `radius` metres; ties go to the
    /// larger id so the answer never depends on dictionary order.
    public func nearestNode(x: Double, y: Double, within radius: Double) -> Int64? {
        var best: (id: Int64, d: Double)?
        forEachCell(x - radius, y - radius, x + radius, y + radius) { key in
            for id in nodeCells[key] ?? [] {
                guard let p = points[id] else { continue }
                let d = hypot(p.x - x, p.y - y)
                guard d <= radius else { continue }
                if best == nil || d < best!.d || (d == best!.d && id > best!.id) { best = (id, d) }
            }
        }
        return best?.id
    }

    /// Every node inside the metric rectangle (box select).
    public func nodes(minX: Double, minY: Double, maxX: Double, maxY: Double) -> [Int64] {
        var found: [Int64] = []
        forEachCell(minX, minY, maxX, maxY) { key in
            for id in nodeCells[key] ?? [] {
                guard let p = points[id] else { continue }
                if p.x >= minX, p.x <= maxX, p.y >= minY, p.y <= maxY { found.append(id) }
            }
        }
        return found.sorted()
    }

    /// The edge nearest (x, y) within `radius` metres.
    public func nearestEdge(x: Double, y: Double, within radius: Double) -> EdgeHit? {
        // Edges are filed by samples at half-cell steps, so a cell ring of
        // margin around the query square reaches every edge within radius.
        let pad = radius + cellSize
        var seen = Set<Edge>()
        var best: EdgeHit?
        forEachCell(x - pad, y - pad, x + pad, y + pad) { key in
            for edge in edgeCells[key] ?? [] where seen.insert(edge).inserted {
                guard let (a, b) = edgeEnds[edge], let pa = points[a], let pb = points[b] else { continue }
                let (d, t) = Self.distance(x, y, pa, pb)
                guard d <= radius else { continue }
                if best == nil || d < best!.distance
                    || (d == best!.distance && (edge.way, edge.segment) < (best!.edge.way, best!.edge.segment)) {
                    best = EdgeHit(edge: edge, a: a, b: b, distance: d, t: t)
                }
            }
        }
        return best
    }

    // MARK: - Internals

    private func cellIndex(_ v: Double) -> Int32 {
        Int32(clamping: Int((v / cellSize).rounded(.down)))
    }

    private func cellKey(_ x: Double, _ y: Double) -> Int64 {
        Self.key(cellIndex(x), cellIndex(y))
    }

    private static func key(_ i: Int32, _ j: Int32) -> Int64 {
        (Int64(i) << 32) | Int64(UInt32(bitPattern: j))
    }

    private func forEachCell(_ minX: Double, _ minY: Double, _ maxX: Double, _ maxY: Double,
                             _ body: (Int64) -> Void) {
        let i0 = cellIndex(minX), i1 = cellIndex(maxX)
        let j0 = cellIndex(minY), j1 = cellIndex(maxY)
        guard i0 <= i1, j0 <= j1 else { return }
        for i in i0...i1 { for j in j0...j1 { body(Self.key(i, j)) } }
    }

    private mutating func insert(_ edge: Edge, from pa: (x: Double, y: Double), to pb: (x: Double, y: Double)) {
        let length = hypot(pb.x - pa.x, pb.y - pa.y)
        let steps = max(1, Int((length / (cellSize / 2)).rounded(.up)))
        var last: Int64?
        for k in 0...steps {
            let t = Double(k) / Double(steps)
            let key = cellKey(pa.x + (pb.x - pa.x) * t, pa.y + (pb.y - pa.y) * t)
            if key != last { edgeCells[key, default: []].append(edge); last = key }
        }
    }

    /// Distance from (x, y) to segment a–b and the clamped parameter.
    static func distance(_ x: Double, _ y: Double,
                         _ a: (x: Double, y: Double), _ b: (x: Double, y: Double)) -> (Double, Double) {
        let dx = b.x - a.x, dy = b.y - a.y
        let len2 = dx * dx + dy * dy
        let t = len2 > 0 ? min(max(((x - a.x) * dx + (y - a.y) * dy) / len2, 0), 1) : 0
        return (hypot(a.x + dx * t - x, a.y + dy * t - y), t)
    }
}
