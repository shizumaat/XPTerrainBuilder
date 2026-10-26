import Testing
import Foundation
@testable import SceneryKit

/// Selecting whole shapes (issue #759): click precedence, the shapes on an
/// edge (smallest first), the repeat-click cycle, the inspector's numbers,
/// and the shape drag and delete as ONE undo step each.
struct PatchShapePickTests {

    /// A 100 m × 100 m apron (-101) and a 100 m × 200 m taxiway (-102)
    /// sharing the edge -2/-3, an open line (-103) from -4, and a loose node.
    private func doc() throws -> PatchDocument {
        let dLat = 100 / PatchLocalFrame.metresPerDegreeLat
        let dLon = 100 / (PatchLocalFrame.metresPerDegreeLat * cos(30.0 * .pi / 180))
        func n(_ id: Int, _ i: Double, _ j: Double, _ alt: Double?) -> [Any] {
            [id, 30.0 + i * dLat, 31.0 + j * dLon, alt.map { $0 as Any } ?? NSNull()]
        }
        return try PatchEditOpsTests.document([
            "nodes": [n(-1, 0, 0, 100), n(-2, 0, 1, 102), n(-3, 1, 1, 104), n(-4, 1, 0, 106),
                      n(-6, 0, 3, 101), n(-7, 1, 3, nil), n(-8, 2, 0, 99), n(-9, 5, 5, 98)],
            "ways": [
                ["id": -101, "refs": [-1, -2, -3, -4, -1], "tags": ["role": "apron", "ref": "A1"]],
                ["id": -102, "refs": [-2, -6, -7, -3, -2], "tags": ["role": "taxiway"]],
                ["id": -103, "refs": [-4, -8], "tags": ["o4_feature": "crown_spine"]],
            ],
        ])
    }

    @Test func precedenceIsNodeThenHandleThenEdge() {
        #expect(PatchShapePick.target(node: -5, onHandle: true, onEdge: true) == .node(-5))
        #expect(PatchShapePick.target(node: nil, onHandle: true, onEdge: true) == .handle)
        #expect(PatchShapePick.target(node: nil, onHandle: false, onEdge: true) == .edge)
        #expect(PatchShapePick.target(node: nil, onHandle: false, onEdge: false) == .empty)
    }

    @Test func thePointerFollowsWhatAClickActsOn() {
        #expect(PatchShapePick.pointer(over: nil) == .openHand)
        #expect(PatchShapePick.pointer(over: .empty) == .openHand)
        #expect(PatchShapePick.pointer(over: .node(-1)) == .pointingHand)
        #expect(PatchShapePick.pointer(over: .handle) == .pointingHand)
        #expect(PatchShapePick.pointer(over: .edge) == .pointingHand)
        #expect(PatchShapePick.pointer(over: .edge, panning: true) == .closedHand)
    }

    @Test func sharedEdgeListsSmallestShapeFirst() throws {
        let d = try doc()
        #expect(PatchShapePick.shapes(onEdge: -2, -3, in: d) == [-101, -102])
        #expect(PatchShapePick.shapes(onEdge: -3, -2, in: d) == [-101, -102])
        #expect(PatchShapePick.shapes(onEdge: -1, -2, in: d) == [-101])
        #expect(PatchShapePick.shapes(onEdge: -4, -8, in: d) == [-103])
        #expect(PatchShapePick.shapes(onEdge: -1, -3, in: d).isEmpty) // a diagonal is no edge
    }

    @Test func repeatClickCyclesThroughTheEdgesShapes() throws {
        let candidates: [Int64] = [-101, -102]
        let first = try #require(PatchShapePick.choose(candidates: candidates, x: 10, y: 10, previous: nil))
        #expect(first.chosen == -101)
        let second = try #require(PatchShapePick.choose(candidates: candidates, x: 13, y: 10, previous: first))
        #expect(second.chosen == -102)
        let third = try #require(PatchShapePick.choose(candidates: candidates, x: 13, y: 10, previous: second))
        #expect(third.chosen == -101)  // wraps
        // farther than 4 pt, or another edge's list: the smallest again
        #expect(PatchShapePick.choose(candidates: candidates, x: 14.1, y: 10, previous: first)?.chosen == -101)
        #expect(PatchShapePick.choose(candidates: [-102, -101], x: 10, y: 10, previous: first)?.chosen == -102)
        #expect(PatchShapePick.choose(candidates: [], x: 10, y: 10, previous: first) == nil)
    }

    @Test func statsOfOneShape() throws {
        let d = try doc()
        let apron = try #require(d.ways.first { $0.id == -101 })
        let s = PatchShapeStats(way: apron, in: d)
        #expect(s.nodeCount == 4)
        #expect(abs(s.area - 10_000) < 10)  // the frame sits at the bbox centre, not 30°
        #expect(abs(s.perimeter - 400) < 0.5)
        #expect(s.minAlt == 100 && s.maxAlt == 106)
        #expect(s.neighbours == 2)  // the taxiway (-2, -3) and the line (-4)
        let taxiway = try #require(d.ways.first { $0.id == -102 })
        let t = PatchShapeStats(way: taxiway, in: d)
        #expect(abs(t.area - 20_000) < 20 && t.nodesWithoutElevation == 1 && t.neighbours == 1)
        let line = try #require(d.ways.first { $0.id == -103 })
        #expect(PatchShapeStats(way: line, in: d).area == 0)
    }

    @Test func shapeDragIsOneStepAndStretchesTheNeighbour() throws {
        let before = try doc()
        let apronNodes = Array(Set(try #require(before.ways.first { $0.id == -101 }).refs)).sorted()
        var after = before
        try after.move(apronNodes, dlat: 1e-5, dlon: 2e-5)
        let step = PatchEditStep(from: before, to: after)
        #expect(step.movedNodes == Set(apronNodes) && !step.topology)
        // the shared nodes moved, so the taxiway's refs still weld to them
        #expect(after.ways.first { $0.id == -102 }?.refs == [-2, -6, -7, -3, -2])
        #expect(after.nodes[-2]!.lat == before.nodes[-2]!.lat + 1e-5)
        var undone = after
        undone.apply(step, reversed: true)
        #expect(undone == before)
    }

    @Test func deleteShapeKeepsSharedNodesAndUndoes() throws {
        let before = try doc()
        var after = before
        try after.deleteWays([-102])
        #expect(after.ways.map(\.id) == [-101, -103])
        #expect(after.nodes[-6] == nil && after.nodes[-7] == nil)
        #expect(after.nodes[-2] != nil && after.nodes[-3] != nil && after.nodes[-9] != nil)
        let step = PatchEditStep(from: before, to: after)
        #expect(step.topology && step.changedWays == [-102])
        var undone = after
        undone.apply(step, reversed: true)
        #expect(undone == before)
        #expect(throws: PatchEditError.unknownWay(-999)) { try after.deleteWays([-999]) }
    }

    @Test func mixedDeleteIsOneStep() throws {
        let before = try doc()
        var after = before
        try after.deleteWays([-102])
        try after.deleteNodes([-9, -1])
        let step = PatchEditStep(from: before, to: after)
        #expect(after.ways.first { $0.id == -101 }?.refs == [-2, -3, -4, -2])
        var undone = after
        undone.apply(step, reversed: true)
        #expect(undone == before)
    }
}
