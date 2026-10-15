import Testing
import Foundation
import simd
@testable import SceneryKit

/// The pack buildings in the 3D preview (patch-editor spec §5, round 6b):
/// the placement transform (heading, agl, exaggeration), the surface under
/// an anchor, the re-seat after an edit, and the `PackObjectsReady` decode.
struct PatchBuildingSeatsTests {

    /// A 0.01° square apron (-101, alt 100) holding a building face (-103,
    /// alt 100) — the building is the apron's hole (§5 ruling 1).
    private func document() throws -> PatchDocument {
        let nodes: [(Int64, Double, Double)] = [
            (-1, 45.00, -123.00), (-2, 45.00, -122.99), (-3, 45.01, -122.99), (-4, 45.01, -123.00),
            (-9, 45.006, -122.994), (-10, 45.006, -122.992), (-11, 45.008, -122.992),
        ]
        let object: [String: Any] = [
            "icao": "ZZZZ", "source": "auto", "path": "/p", "stale": false, "stale_inputs": [String](),
            "min_distinct_spacing_m": 0.5, "identity_dp": 11, "header": [String: String](),
            "nodes": nodes.map { [$0.0, $0.1, $0.2, 100.0] as [Any] },
            "ways": [O4PatchWayRow(id: -101, refs: [-1, -2, -3, -4, -1], tags: ["role": "apron"]).wireObject,
                     O4PatchWayRow(id: -103, refs: [-9, -10, -11, -9], tags: ["role": "building"]).wireObject],
        ]
        return PatchDocument(tile: "+45-123", load: try O4JSON.from(object).decode(O4PatchLoad.self))
    }

    private func meshes(_ doc: PatchDocument) -> [Int64: PatchShapeMesh] {
        Dictionary(uniqueKeysWithValues: PatchShapeAssembly.shapes(of: doc).map {
            ($0.wayID, PatchShapeMesh(shape: $0, document: doc))
        })
    }

    private func placement(_ lat: Double, _ lon: Double, heading: Double = 0,
                           agl: Double = 0) throws -> O4PackObjects.Placement {
        try O4JSON.from(["model": "m.obj", "lat": lat, "lon": lon, "heading_deg": heading,
                         "agl_m": agl] as [String: Any]).decode(O4PackObjects.Placement.self)
    }

    // MARK: - Transform

    @Test func headingTurnsTheModelClockwiseFromNorth() {
        let space = PatchPreviewSpace(frame: PatchLocalFrame(originLat: 45, originLon: -123),
                                      base: 100, terrain: nil)
        let pose = PatchBuildingPose(anchorLat: 45, anchorLon: -123, headingDeg: 90, aglM: 2,
                                     surfaceZ: 110, space: space)
        #expect(pose.position == SIMD3(0, 12, 0))                  // surface + agl - base
        // the model's nose (authored -z, north at heading 0) points EAST at 90°
        let nose = pose.place(SIMD3(0, 0, -10))
        #expect(abs(nose.x - 10) < 1e-4 && abs(nose.z) < 1e-4)
        // its right side (authored +x) points SOUTH (+z)
        let right = pose.place(SIMD3(5, 0, 0))
        #expect(abs(right.x) < 1e-4 && abs(right.z - 5) < 1e-4)
        // exaggeration lifts the seat, never the building's own height
        let roof = pose.place(SIMD3(0, 20, 0), exaggeration: 3)
        #expect(abs(roof.y - (12 * 3 + 20)) < 1e-4)
    }

    @Test func headingZeroKeepsTheAuthoredFrame() {
        let space = PatchPreviewSpace(frame: PatchLocalFrame(originLat: 45, originLon: -123),
                                      base: 0, terrain: nil)
        let pose = PatchBuildingPose(anchorLat: 45, anchorLon: -123, headingDeg: 0, aglM: 0,
                                     surfaceZ: 0, space: space)
        #expect(pose.place(SIMD3(1, 2, -3)) == SIMD3(1, 2, -3))
        #expect(pose.yaw == 0)
    }

    // MARK: - Surface and re-seat

    @Test func theAnchorSitsOnThePatchShapeUnderIt() throws {
        let doc = try document()
        let space = PatchPreviewSpace(frame: doc.frame, base: 90, terrain: nil)
        let locator = PatchSurfaceLocator(meshes: meshes(doc), document: doc)
        let onApron = locator.surface(lat: 45.002, lon: -122.998, space: space)
        #expect(onApron.way == -101 && abs(onApron.z - 100) < 1e-9)
        let onBuilding = locator.surface(lat: 45.0065, lon: -122.9925, space: space)
        #expect(onBuilding.way == -103)                            // the hole is not the apron
        let off = locator.surface(lat: 45.02, lon: -122.95, space: space)
        #expect(off.way == nil && off.z == 90)                     // no terrain yet: the base
    }

    @Test func anEditReseatsOnlyThePlacementsOnTheChangedShape() throws {
        var doc = try document()
        let space = PatchPreviewSpace(frame: doc.frame, base: 90, terrain: nil)
        let placements = [try placement(45.002, -122.998, agl: 1),          // on the apron
                          try placement(45.0065, -122.9925, heading: 30),   // on the building
                          try placement(45.02, -122.95)]                    // off the patch
        var meshes = self.meshes(doc)
        var seats = PatchBuildingSeats(placements: placements,
                                       locator: PatchSurfaceLocator(meshes: meshes, document: doc),
                                       space: space)
        #expect(seats.shapeOf == [-101, -103, nil])
        #expect(seats.poses[0].position.y == 11)                   // 100 + 1 - 90
        // lower the building's nodes by 4 m: only the building's placement moves
        for id: Int64 in [-9, -10, -11] { doc.nodes[id]?.alt = 96 }
        meshes = self.meshes(doc)
        let moved = seats.reseat(changedShapes: [-103],
                                 locator: PatchSurfaceLocator(meshes: meshes, document: doc), space: space)
        #expect(moved == [1])
        #expect(abs(seats.poses[1].position.y - 6) < 1e-4)
        #expect(seats.poses[0].position.y == 11)
        #expect(seats.reseat(changedShapes: [], locator: PatchSurfaceLocator(meshes: meshes, document: doc),
                             space: space).isEmpty)
    }

    // MARK: - The completion event

    @Test func packObjectsReadyDecodesTheResultOrTheError() throws {
        let ok = O4JSON.from(["event": "PackObjectsReady", "request": 7, "error": "", "result": [
            "models": [[String: Any]](), "placements": [[String: Any]](),
            "facades": [[String: Any]](), "missing": ["a sentence"]]] as [String: Any])
        let objects = try OrthoEngineClient.decodePackObjectsReady(ok).get()
        #expect(objects.missing == ["a sentence"])
        let failed = O4JSON.from(["event": "PackObjectsReady", "request": 7, "error": "no pack",
                                  "result": NSNull()] as [String: Any])
        #expect(throws: O4CommandError.self) { try OrthoEngineClient.decodePackObjectsReady(failed).get() }
        #expect(throws: O4CommandError.self) { try OrthoEngineClient.decodePackObjectsReady(nil).get() }
    }
}
