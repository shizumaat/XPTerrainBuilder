import Foundation

/// Clicking a patch LINE selects its whole shape, JOSM-style (issue #759,
/// patch-editor spec §4 as amended 2026-10-15). Pure functions of the
/// document and screen points, so the gestures are tested without a window:
///
/// * precedence of what a click lands on: node > "+" handle > edge > empty;
/// * the shapes an edge belongs to, smallest plan area first (adjacent faces
///   share vertices, so one edge can belong to several shapes);
/// * the repeat-click cycle: clicking the same spot again (within 4 pt, no
///   move) steps to the next shape on that edge.
public enum PatchShapePick {
    /// A repeat click within this many points of the last one cycles.
    public static let repeatRadius: Double = 4

    /// What a click in Edit mode lands on.
    public enum Target: Equatable, Sendable {
        case node(Int64)
        case handle
        case edge
        case empty
    }

    /// Node > "+" handle > edge > empty map (each already hit-tested at 8 pt).
    public static func target(node: Int64?, onHandle: Bool, onEdge: Bool) -> Target {
        if let node { return .node(node) }
        if onHandle { return .handle }
        return onEdge ? .edge : .empty
    }

    /// The ids of the ways in which `a` and `b` are consecutive (either
    /// direction), smallest plan area first (an open way has none), ties by
    /// way id.
    public static func shapes(onEdge a: Int64, _ b: Int64, in doc: PatchDocument) -> [Int64] {
        let shared = Set(doc.wayIndicesByNode[a] ?? []).intersection(doc.wayIndicesByNode[b] ?? [])
        let hits = shared.map { doc.ways[$0] }.filter { way in
            zip(way.refs, way.refs.dropFirst()).contains { ($0 == a && $1 == b) || ($0 == b && $1 == a) }
        }
        return hits.map { ($0.id, PatchShapeStats.planArea(of: $0, in: doc)) }
            .sorted { ($0.1, $0.0) < ($1.1, $1.0) }
            .map(\.0)
    }

    /// The last edge click: where, which shapes were on that edge, which one
    /// it chose.
    public struct Click: Equatable, Sendable {
        public let x: Double
        public let y: Double
        public let candidates: [Int64]
        public let chosen: Int64

        public init(x: Double, y: Double, candidates: [Int64], chosen: Int64) {
            self.x = x; self.y = y; self.candidates = candidates; self.chosen = chosen
        }
    }

    /// The shape a click on an edge selects. A click within `repeatRadius`
    /// of `previous` on the same candidate list steps to the shape after
    /// the one it chose (wrapping); any other click picks the smallest.
    /// Nil when there is no candidate.
    public static func choose(candidates: [Int64], x: Double, y: Double, previous: Click?) -> Click? {
        guard let first = candidates.first else { return nil }
        var chosen = first
        if let previous, previous.candidates == candidates,
           hypot(previous.x - x, previous.y - y) <= repeatRadius,
           let i = candidates.firstIndex(of: previous.chosen) {
            chosen = candidates[(i + 1) % candidates.count]
        }
        return Click(x: x, y: y, candidates: candidates, chosen: chosen)
    }
}
