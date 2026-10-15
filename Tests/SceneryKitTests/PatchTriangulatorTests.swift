import Testing
import Foundation
@testable import SceneryKit

/// The 3D preview's shape triangulation (`PatchTriangulator`), the
/// surface/hole assembly (`PatchShapeAssembly`) and the terrain cut-out
/// (`PatchTerrainCut`) — patch-editor spec §5, brief pe-3d.
struct PatchTriangulatorTests {

    // MARK: - Helpers

    private typealias P = (x: Double, y: Double)

    /// Triangulate rings given as point lists; ids are 1, 2, 3 … in order.
    private func triangulate(_ outer: [P], _ holes: [[P]] = []) -> (tris: [PatchTriangle], pos: [Int64: P]) {
        var pos: [Int64: P] = [:]
        var next: Int64 = 1
        func ids(_ ring: [P]) -> [Int64] {
            ring.map { p in pos[next] = p; next += 1; return next - 1 }
        }
        let o = ids(outer)
        let h = holes.map(ids)
        return (PatchTriangulator.triangulate(outer: o, holes: h) { pos[$0] }, pos)
    }

    private func area(_ ring: [P]) -> Double {
        abs(PatchTriangulator.signedArea(ring.flatMap { [$0.x, $0.y] }))
    }

    private func ring(_ pts: [P]) -> Ring {
        Ring(ids: pts.indices.map { Int64($0) }, points: pts)
    }

    /// Area sum = polygon area (1e-6 relative), every triangle CCW with its
    /// centroid inside (or on) the outer ring and not inside any hole.
    private func checkCover(_ tris: [PatchTriangle], _ pos: [Int64: P], outer: [P], holes: [[P]] = [],
                            sourceLocation: SourceLocation = #_sourceLocation) {
        let expected = area(outer) - holes.map(area).reduce(0, +)
        var sum = 0.0
        let outerRing = ring(outer), holeRings = holes.map(ring)
        for t in tris {
            let a = pos[t.a]!, b = pos[t.b]!, c = pos[t.c]!
            let cross = (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
            #expect(cross >= 0, "clockwise triangle", sourceLocation: sourceLocation)
            sum += cross / 2
            let g = ((a.x + b.x + c.x) / 3, (a.y + b.y + c.y) / 3)
            // a sliver along collinear ring vertices (real faces have them)
            // has its centroid ON the edge; anything else is strictly inside
            #expect(outerRing.locate(g) != .outside, "triangle outside the shape", sourceLocation: sourceLocation)
            for h in holeRings {
                #expect(h.locate(g) != .inside, "triangle inside a hole", sourceLocation: sourceLocation)
            }
        }
        #expect(abs(sum - expected) <= 1e-6 * expected, "area \(sum) vs \(expected)",
                sourceLocation: sourceLocation)
    }

    // MARK: - Triangulator

    @Test func convexSquare() {
        let sq: [P] = [(0, 0), (10, 0), (10, 10), (0, 10)]
        let (tris, pos) = triangulate(sq)
        #expect(tris.count == 2)
        checkCover(tris, pos, outer: sq)
    }

    @Test func clockwiseInputComesOutCounterClockwise() {
        let sq: [P] = [(0, 10), (10, 10), (10, 0), (0, 0)]
        let (tris, pos) = triangulate(sq)
        checkCover(tris, pos, outer: sq)
    }

    @Test func concaveComb() {
        // a comb: three teeth pointing north
        let comb: [P] = [(0, 0), (50, 0), (50, 30), (40, 30), (40, 10), (30, 10), (30, 30),
                         (20, 30), (20, 10), (10, 10), (10, 30), (0, 30)]
        let (tris, pos) = triangulate(comb)
        #expect(tris.count == comb.count - 2)
        checkCover(tris, pos, outer: comb)
    }

    @Test func oneHole() {
        let outer: [P] = [(0, 0), (100, 0), (100, 60), (0, 60)]
        let hole: [P] = [(20, 20), (40, 20), (40, 40), (20, 40)]
        let (tris, pos) = triangulate(outer, [hole])
        checkCover(tris, pos, outer: outer, holes: [hole])
    }

    @Test func twoHolesInAConcaveFace() {
        let outer: [P] = [(0, 0), (120, 0), (120, 80), (70, 80), (70, 50), (50, 50), (50, 80), (0, 80)]
        let h1: [P] = [(10, 10), (30, 10), (30, 30), (10, 30)]
        let h2: [P] = [(80, 10), (110, 15), (100, 40), (85, 35)].reversed()   // either winding
        let (tris, pos) = triangulate(outer, [h1, h2])
        checkCover(tris, pos, outer: outer, holes: [h1, h2])
    }

    @Test func largeRingUsesTheHashedPathAndStillCovers() {
        // 200-gon with a 40-gon hole: past earcut's 80-point hashing threshold
        let outer: [P] = (0..<200).map { i in
            let a = Double(i) / 200 * 2 * .pi, r = 100 + 15 * sin(7 * a)
            return (r * cos(a), r * sin(a))
        }
        let hole: [P] = (0..<40).map { i in
            let a = Double(i) / 40 * 2 * .pi
            return (20 + 25 * cos(a), 10 + 25 * sin(a))
        }
        let (tris, pos) = triangulate(outer, [hole])
        checkCover(tris, pos, outer: outer, holes: [hole])
    }

    @Test func closingIdAndUnknownNodesAreDropped() {
        let pos: [Int64: P] = [1: (0, 0), 2: (5, 0), 3: (5, 5), 4: (0, 5)]
        let tris = PatchTriangulator.triangulate(outer: [1, 2, 3, 4, 99, 1]) { pos[$0] }
        #expect(tris.count == 2)
        #expect(PatchTriangulator.triangulate(outer: [1, 2, 1]) { pos[$0] }.isEmpty)
    }

    // MARK: - A real patch face with its gap ring

    private func excerpt() throws -> PatchDocument {
        let url = try #require(Bundle.module.url(
            forResource: "Fixtures/PatchEditor/patch_face_with_hole", withExtension: "json"))
        let object = try JSONSerialization.jsonObject(with: Data(contentsOf: url))
        let load = try O4JSON.from(object).decode(O4PatchLoad.self)
        return PatchDocument(tile: "+39-107", load: load)
    }

    @Test func realFaceWithItsGapRing() throws {
        let doc = try excerpt()
        let shapes = PatchShapeAssembly.shapes(of: doc)
        #expect(shapes.count == 1)                          // the gap ring is not a surface
        let shape = try #require(shapes.first)
        #expect(shape.holes.count == 1)
        let pos: [Int64: P] = doc.nodes.mapValues { doc.frame.metres(lat: $0.lat, lon: $0.lon) }
        let tris = PatchTriangulator.triangulate(outer: shape.outer, holes: shape.holes) { pos[$0] }
        checkCover(tris, pos, outer: shape.outer.map { pos[$0]! },
                   holes: shape.holes.map { $0.map { pos[$0]! } })
        // triangles are in node ids: every corner is a node of the shape
        let ids = shape.nodeIDs
        #expect(tris.allSatisfy { ids.contains($0.a) && ids.contains($0.b) && ids.contains($0.c) })
    }

    // MARK: - Assembly

    private func document(nodes: [(Int64, Double, Double)], ways: [O4PatchWayRow]) throws -> PatchDocument {
        let object: [String: Any] = [
            "icao": "ZZZZ", "source": "auto", "path": "/p", "stale": false, "stale_inputs": [String](),
            "min_distinct_spacing_m": 0.5, "identity_dp": 11, "header": [String: String](),
            "nodes": nodes.map { [$0.0, $0.1, $0.2, 100.0] as [Any] },
            "ways": ways.map(\.wireObject),
        ]
        return PatchDocument(tile: "+45-123", load: try O4JSON.from(object).decode(O4PatchLoad.self))
    }

    /// A 0.01° square face (-101), an untagged gap ring inside it (-102) and
    /// a face inside the square but outside the gap (-103).
    private func nestedDocument(gapShapeID: String?) throws -> PatchDocument {
        var gapTags = ["o4_feature": "gap_interior_ring"]
        if let gapShapeID { gapTags["shapeID"] = gapShapeID }
        return try document(
            nodes: [(-1, 45.00, -123.00), (-2, 45.00, -122.99), (-3, 45.01, -122.99), (-4, 45.01, -123.00),
                    (-5, 45.002, -122.998), (-6, 45.002, -122.996), (-7, 45.004, -122.996), (-8, 45.004, -122.998),
                    (-9, 45.006, -122.994), (-10, 45.006, -122.992), (-11, 45.008, -122.992)],
            ways: [O4PatchWayRow(id: -101, refs: [-1, -2, -3, -4, -1], tags: ["role": "apron", "shapeID": "7"]),
                   O4PatchWayRow(id: -102, refs: [-5, -6, -7, -8, -5], tags: gapTags),
                   O4PatchWayRow(id: -103, refs: [-9, -10, -11, -9], tags: ["role": "building"])])
    }

    @Test(arguments: ["7", nil] as [String?])
    func gapRingPairsWithTheFaceThatHoldsIt(shapeID: String?) throws {
        let shapes = PatchShapeAssembly.shapes(of: try nestedDocument(gapShapeID: shapeID))
        #expect(shapes.map(\.wayID) == [-101, -103])
        #expect(shapes[0].holes == [[-5, -6, -7, -8], [-9, -10, -11]])
        #expect(shapes[1].holes.isEmpty)
    }

    // MARK: - Terrain cut-out

    @Test func cutOutDropsExactlyTheTrianglesWhoseCentroidIsInsideAFace() throws {
        let doc = try nestedDocument(gapShapeID: "7")
        let shapes = PatchShapeAssembly.shapes(of: doc)
        let grid = PatchTerrainGrid(rows: 60, cols: 70, south: 44.999, west: -123.001,
                                    dlat: 0.0002, dlon: 0.0002)
        let covered = PatchTerrainCut.coveredTriangles(grid: grid, shapes: shapes, document: doc)
        #expect(covered.count == grid.triangleCount)
        // brute force: even-odd over each shape's rings, in the metric frame
        let f = doc.frame
        let rings = shapes.map { shape in
            ([shape.outer] + shape.holes).map { r in
                Ring(ids: r, points: r.map { f.metres(lat: doc.nodes[$0]!.lat, lon: doc.nodes[$0]!.lon) })
            }
        }
        var dropped = 0, insideGap = 0
        for t in 0..<grid.triangleCount {
            let ll = grid.centroid(ofTriangle: t)
            let g = f.metres(lat: ll.lat, lon: ll.lon)
            let inside = rings.contains { shape in
                shape.filter { $0.locate(g) == .inside }.count % 2 == 1
            }
            #expect(covered[t] == inside, "triangle \(t)")
            if inside { dropped += 1 }
            if rings[0][1].locate(g) == .inside { insideGap += 1; #expect(!covered[t]) }
        }
        #expect(dropped > 0 && insideGap > 0)
        let kept = PatchTerrainCut.keptIndices(grid: grid, covered: covered)
        #expect(kept.count == 3 * (grid.triangleCount - dropped))
    }

    @Test func gridTrianglesAreCounterClockwiseAndCoverTheCell() {
        let grid = PatchTerrainGrid(rows: 3, cols: 4, south: 0, west: 0, dlat: 1, dlon: 1)
        #expect(grid.triangleCount == 12)
        func xy(_ v: UInt32) -> P { (Double(Int(v) % 4), Double(Int(v) / 4)) }
        for t in 0..<grid.triangleCount {
            let (a, b, c) = grid.vertices(ofTriangle: t)
            let pa = xy(a), pb = xy(b), pc = xy(c)
            #expect((pb.x - pa.x) * (pc.y - pa.y) - (pb.y - pa.y) * (pc.x - pa.x) == 1)   // CCW, half a cell
            let g = grid.centroid(ofTriangle: t)
            #expect(abs(g.lon - (pa.x + pb.x + pc.x) / 3) < 1e-12 && abs(g.lat - (pa.y + pb.y + pc.y) / 3) < 1e-12)
        }
    }
}
