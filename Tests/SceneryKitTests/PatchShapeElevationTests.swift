import Testing
import Foundation
@testable import SceneryKit

/// "Set elevation…" on selected shapes (issue #1357; twin of Qt's
/// `test_patch_shape_elevation.py`): the nodes it sets (holes too), the
/// shared nodes and neighbouring shapes it reports, the mean that prefills
/// the field, undo, and the ft → m conversion.
struct PatchShapeElevationTests {

    /// A 100 m apron (-101) with a gap-ring hole (-110), a taxiway (-102)
    /// sharing its nodes -2 and -3, and an open line (-103) from -4.
    private func doc() throws -> PatchDocument {
        let dLat = 100 / PatchLocalFrame.metresPerDegreeLat
        let dLon = 100 / (PatchLocalFrame.metresPerDegreeLat * cos(30.0 * .pi / 180))
        func n(_ id: Int, _ i: Double, _ j: Double, _ alt: Double?) -> [Any] {
            [id, 30.0 + i * dLat, 31.0 + j * dLon, alt.map { $0 as Any } ?? NSNull()]
        }
        return try PatchEditOpsTests.document([
            "nodes": [n(-1, 0, 0, 100), n(-2, 0, 1, 102), n(-3, 1, 1, 104), n(-4, 1, 0, 106),
                      n(-6, 0, 3, 101), n(-7, 1, 3, nil), n(-8, 2, 0, 99),
                      n(-21, 0.4, 0.4, 100), n(-22, 0.4, 0.6, nil), n(-23, 0.6, 0.5, 100)],
            "ways": [
                ["id": -101, "refs": [-1, -2, -3, -4, -1], "tags": ["role": "apron"]],
                ["id": -102, "refs": [-2, -6, -7, -3, -2], "tags": ["role": "taxiway"]],
                ["id": -103, "refs": [-4, -8], "tags": ["o4_feature": "crown_spine"]],
                ["id": -110, "refs": [-21, -22, -23, -21], "tags": ["o4_feature": "gap_interior_ring"]],
            ],
        ])
    }

    @Test func oneShapeSetsItsRingAndHoleAndReportsItsNeighbours() throws {
        let d = try doc()
        let plan = PatchShapeElevation(shapes: [-101], in: d)
        #expect(plan.ways == [-101, -110])
        #expect(plan.own == [-1, -21, -22, -23])
        #expect(plan.shared == [-2, -3, -4])
        #expect(plan.neighbours == [-102, -103])
        #expect(abs(plan.meanAlt! - (100 + 102 + 104 + 106 + 100 + 100) / 6.0) < 1e-9)
        #expect(plan.summary() == "3 shared nodes, 2 neighbouring shapes affected.")
        #expect(plan.targets(includeShared: false) == [-23, -22, -21, -1])
    }

    @Test func twoShapesSharingTwoNodesSetEveryNodeAndUndoRestores() throws {
        let before = try doc()
        let plan = PatchShapeElevation(shapes: [-101, -102], in: before)
        #expect(plan.shared == [-4] && plan.neighbours == [-103])
        var after = before
        try after.setShapeElevation(plan, alt: 95.5)
        for id in plan.targets() { #expect(after.nodes[id]?.alt == 95.5) }
        #expect(after.nodes[-8]?.alt == 99)                    // the line's own end stays
        let step = PatchEditStep(from: before, to: after)
        after.apply(step, reversed: true)
        #expect(after.nodes == before.nodes)
    }

    @Test func sharedNodesStayWhenTheBoxIsOff() throws {
        var d = try doc()
        let plan = PatchShapeElevation(shapes: [-101], in: d)
        try d.setShapeElevation(plan, alt: 90, includeShared: false)
        #expect(d.nodes[-1]?.alt == 90 && d.nodes[-22]?.alt == 90)
        #expect(d.nodes[-2]?.alt == 102 && d.nodes[-4]?.alt == 106)  // the taxiway and line keep theirs
    }

    @Test func feetConvertToMetresExactlyToAMillimetre() {
        #expect(abs(PatchShapeElevation.metres(1000, from: .feet) - 304.8) < 0.001)
        #expect(abs(PatchShapeElevation.metres(328.084, from: .feet) - 100) < 0.001)
        #expect(PatchShapeElevation.metres(12.5, from: .metres) == 12.5)
        #expect(abs(PatchShapeElevation.value(304.8, in: .feet) - 1000) < 0.001)
    }
}
