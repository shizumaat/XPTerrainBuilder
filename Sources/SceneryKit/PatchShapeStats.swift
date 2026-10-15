import Foundation

/// What the inspector says about one selected shape (#759): plan area and
/// perimeter in the document's metric frame, node count, elevation range
/// and how many other shapes share its nodes.
public struct PatchShapeStats: Equatable, Sendable {
    public let nodeCount: Int
    /// m²; 0 for an open way.
    public let area: Double
    /// Metres along the refs (a closed way's refs include the closing edge).
    public let perimeter: Double
    public let minAlt: Double?
    public let maxAlt: Double?
    /// Nodes that carry no elevation (the mesh gives theirs).
    public let nodesWithoutElevation: Int
    /// Other ways that share at least one node with it.
    public let neighbours: Int

    public init(way: PatchWay, in doc: PatchDocument) {
        let ids = Array(Set(way.refs))
        nodeCount = ids.count
        area = PatchShapeStats.planArea(of: way, in: doc)
        let points = way.refs.compactMap { doc.nodes[$0] }.map { doc.frame.metres(lat: $0.lat, lon: $0.lon) }
        perimeter = zip(points, points.dropFirst()).reduce(0) { $0 + hypot($1.1.x - $1.0.x, $1.1.y - $1.0.y) }
        let alts = ids.compactMap { doc.nodes[$0]?.alt }
        minAlt = alts.min()
        maxAlt = alts.max()
        nodesWithoutElevation = ids.count - alts.count
        let mine = doc.ways.firstIndex { $0.id == way.id }
        neighbours = Set(ids.flatMap { doc.wayIndicesByNode[$0] ?? [] }).subtracting(mine.map { [$0] } ?? []).count
    }

    /// |signed area| of a closed way in m² (`PatchTriangulator.signedArea`);
    /// 0 for an open way.
    public static func planArea(of way: PatchWay, in doc: PatchDocument) -> Double {
        guard way.isClosed else { return 0 }
        var xy: [Double] = []
        for id in way.refs.dropLast() {
            guard let n = doc.nodes[id] else { continue }
            let p = doc.frame.metres(lat: n.lat, lon: n.lon)
            xy += [p.x, p.y]
        }
        return abs(PatchTriangulator.signedArea(xy))
    }
}
