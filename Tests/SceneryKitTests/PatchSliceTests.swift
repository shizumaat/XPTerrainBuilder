import Testing
import Foundation
@testable import SceneryKit

/// Slice (#1318) beyond the twin fixture's `slice_shape` cases (which
/// `PatchEditOpsTests` runs): the refusals, the `way` choice, the gap and
/// one undo step. Mirrors `Ortho4XP/tests/test_patch_slice.py`.
struct PatchSliceTests {
    static let d = 0.0009765625

    private static func doc(_ name: String) throws -> (PatchDocument, Int64, Int64) {
        let c = try #require(try PatchEditOpsTests.fixture().cases.first { $0["name"] as? String == name })
        let args = try #require((c["ops"] as? [[String: Any]])?.first?["args"] as? [String: Any])
        return (try PatchEditOpsTests.document(try #require(c["doc"] as? [String: Any])),
                (args["a"] as! NSNumber).int64Value, (args["b"] as! NSNumber).int64Value)
    }

    private static func make(_ nodes: [[Any]], _ ways: [[String: Any]]) throws -> PatchDocument {
        try PatchEditOpsTests.document(["nodes": nodes, "ways": ways])
    }

    private static func refused(_ doc: PatchDocument, _ a: Int64, _ b: Int64, way: Int64? = nil,
                                containing text: String) {
        var copy = doc
        do {
            try copy.sliceShape(a, b, way: way)
            Issue.record("slice \(a) → \(b) was not refused")
        } catch {
            #expect("\(error)".contains(text), "\(error)")
        }
    }

    @Test func refusedCutsOnTheL() throws {
        let (l, _, _) = try Self.doc("slice_clockwise_concave_l_larger_half_keeps_id")
        Self.refused(l, -3, -6, containing: "leaves the shape")
        Self.refused(l, -1, -2, containing: "not neighbours")
        Self.refused(l, -1, -1, containing: "same shape")
    }

    @Test func refusedAlongAnEdgeAndOffTheShape() throws {
        let d = Self.d
        let line = try Self.make([[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + d, 1.0], [-3, 30.0, 31.0 + 2 * d, 1.0],
                                  [-4, 30.0 + d, 31.0 + 2 * d, 1.0], [-5, 30.0 + d, 31.0, 1.0]],
                                 [["id": -1, "refs": [-1, -2, -3, -4, -5, -1], "tags": [String: String]()]])
        Self.refused(line, -1, -3, containing: "along the shape's edge")
        let (square, _, _) = try Self.doc("slice_square_diagonal_keeps_neighbour_welded")
        Self.refused(square, -5, -3, containing: "same shape")
        var copy = square
        #expect(throws: PatchEditError.unknownNode(-99)) { try copy.sliceShape(-1, -99) }
    }

    private static func squareWithHole(_ hole: [(Double, Double)]) throws -> PatchDocument {
        let d = Self.d
        var nodes: [[Any]] = [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + d, 1.0],
                              [-3, 30.0 + d, 31.0 + d, 1.0], [-4, 30.0 + d, 31.0, 1.0]]
        for (i, p) in hole.enumerated() { nodes.append([-10 - i, 30.0 + p.0 * d, 31.0 + p.1 * d, 1.0]) }
        let refs = hole.indices.map { -10 - $0 } + [-10]
        return try Self.make(nodes, [["id": -1, "refs": [-1, -2, -3, -4, -1], "tags": ["role": "apron"]],
                                     ["id": -2, "refs": refs, "tags": ["o4_feature": "gap_interior_ring"]]])
    }

    @Test func refusedThroughAHoleCornerAndIntoThreePieces() throws {
        var fine = try Self.squareWithHole([(0.25, 0.5), (0.5, 0.75), (0.75, 0.5), (0.5, 0.25)])
        try fine.sliceShape(-1, -3)
        let corner = try Self.squareWithHole([(0.25, 0.25), (0.5, 0.4), (0.75, 0.75), (0.4, 0.5)])
        Self.refused(corner, -1, -3, containing: "corner of a hole")

        let d = Self.d
        var nodes: [[Any]] = [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + d, 1.0], [-3, 30.0 + d, 31.0 + d, 1.0],
                              [-4, 30.0 + d / 2 + d / 64, 31.0 + d, 1.0], [-5, 30.0 + d, 31.0, 1.0],
                              [-6, 30.0 + d / 2, 31.0, 1.0]]
        let u: [(Double, Double)] = [(0.2, 0.2), (0.2, 0.8), (0.8, 0.8), (0.8, 0.7), (0.3, 0.7), (0.3, 0.3),
                                     (0.8, 0.3), (0.8, 0.2)]
        for (i, p) in u.enumerated() { nodes.append([-10 - i, 30.0 + p.0 * d, 31.0 + p.1 * d, 1.0]) }
        let uShape = try Self.make(nodes, [
            ["id": -1, "refs": [-1, -2, -4, -3, -5, -6, -1], "tags": [String: String]()],
            ["id": -2, "refs": u.indices.map { -10 - $0 } + [-10], "tags": ["o4_feature": "gap_interior_ring"]],
        ])
        Self.refused(uShape, -6, -4, containing: "more than two pieces")
    }

    @Test func theWayArgumentPicksOneOfTwoShapes() throws {
        let d = Self.d
        let doc = try Self.make(
            [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + d, 1.0], [-3, 30.0 + d, 31.0 + d, 1.0],
             [-4, 30.0 + d, 31.0, 1.0], [-5, 30.0 + d / 2, 31.0 + 1.5 * d, 1.0], [-6, 30.0 + d / 2, 31.0 - d / 2, 1.0]],
            [["id": -1, "refs": [-1, -2, -3, -4, -1], "tags": ["role": "apron"]],
             ["id": -2, "refs": [-1, -5, -3, -6, -1], "tags": ["role": "taxiway"]]])
        Self.refused(doc, -1, -3, containing: "more than one shape")
        var sliced = doc
        try sliced.sliceShape(-1, -3, way: -2)
        #expect(sliced.ways.count == 3)
        #expect(sliced.ways[0].refs == [-1, -2, -3, -4, -1])
        #expect(sliced.ways.dropFirst().allSatisfy { $0.tags["role"] == "taxiway" })
    }

    @Test func theGapIsHalfAMetreAndTheSliceIsOneUndoStep() throws {
        let (before, a, b) = try Self.doc("slice_through_a_hole_adds_nodes_and_drops_the_hole")
        var after = before
        try after.sliceShape(a, b)
        let frame = PatchLocalFrame(originLat: 30.0, originLon: 31.0)
        let added = after.nodes.keys.filter { before.nodes[$0] == nil }
        #expect(added.count == 6)
        for id in [a, b] {
            let kept = try #require(after.nodes[id])
            let p = frame.metres(lat: kept.lat, lon: kept.lon)
            let nearest = try #require(added.compactMap { after.nodes[$0] }.min {
                let q = frame.metres(lat: $0.lat, lon: $0.lon), r = frame.metres(lat: $1.lat, lon: $1.lon)
                return hypot(q.x - p.x, q.y - p.y) < hypot(r.x - p.x, r.y - p.y)
            })
            let q = frame.metres(lat: nearest.lat, lon: nearest.lon)
            #expect(abs(hypot(q.x - p.x, q.y - p.y) - PatchSlice.gapM) <= 1e-3)
            #expect(nearest.alt == before.nodes[id]?.alt && kept.alt == before.nodes[id]?.alt)
        }
        #expect(!after.ways.contains { $0.id == -302 })
        let step = PatchEditStep(from: before, to: after)
        #expect(step.topology)
        var undone = after
        undone.apply(step, reversed: true)
        #expect(undone == before)
        var redone = undone
        redone.apply(step)
        #expect(redone == after)
    }
}
