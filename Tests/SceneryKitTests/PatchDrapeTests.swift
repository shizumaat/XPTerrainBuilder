import Testing
import Foundation
import simd
@testable import SceneryKit

/// Round 6c of the 3D preview (patch-editor spec §5): the imagery drape's
/// tile choice and UV mapping, the "Preview | Last build" state, and the
/// last build's surface under a building.
struct PatchDrapeTests {
    /// About 6 km × 5.5 km at 30° N (a HECA-sized preview extent).
    private let box = O4LatLonBox(minLat: 30.09, minLon: 31.37, maxLat: 30.14, maxLon: 31.43)

    // MARK: - Drape plan

    @Test func theFinestZoomWhoseTextureFits8192() throws {
        let plan = try #require(PatchDrapePlan(box: box, maxZoom: 19))
        #expect(plan.width <= 8192 && plan.height <= 8192)
        // one zoom finer would not fit
        let finer = (WebMercator.tileX(lon: box.maxLon, z: plan.zoom + 1)
                     - WebMercator.tileX(lon: box.minLon, z: plan.zoom + 1)) * 256
        let finerH = (WebMercator.tileY(lat: box.minLat, z: plan.zoom + 1)
                      - WebMercator.tileY(lat: box.maxLat, z: plan.zoom + 1)) * 256
        #expect(finer > 8192 || finerH > 8192)
        #expect(plan.zoom == 17)                       // 5,592 px wide; ZL 18 would be 11,184
    }

    @Test func theSourceCeilingCapsTheZoom() throws {
        let plan = try #require(PatchDrapePlan(box: box, maxZoom: 14))
        #expect(plan.zoom == 14 && plan.width < 8192)
    }

    @Test func theTilesCoverTheBoxAndLandInPlace() throws {
        let plan = try #require(PatchDrapePlan(box: box, maxZoom: 15))
        let z = plan.zoom
        let xs = Set(plan.tiles.map(\.x)), ys = Set(plan.tiles.map(\.y))
        #expect(xs.min() == Int(WebMercator.tileX(lon: box.minLon, z: z)))
        #expect(xs.max() == Int(WebMercator.tileX(lon: box.maxLon, z: z)))
        #expect(ys.min() == Int(WebMercator.tileY(lat: box.maxLat, z: z)))     // north = top row
        #expect(plan.tiles.count == xs.count * ys.count)
        // the north-west tile overhangs the texture's top-left corner
        let nw = plan.rect(x: xs.min()!, y: ys.min()!)
        #expect(nw.minX <= 0 && nw.maxX > 0 && nw.minY <= 0 && nw.maxY > 0)
        // the south-east tile reaches the bottom-right corner
        let se = plan.rect(x: xs.max()!, y: ys.max()!)
        #expect(se.maxX >= Double(plan.width) - 1 && se.maxY >= Double(plan.height) - 1)
    }

    @Test func uvRunsEastAndSouthOverTheBox() {
        let nw = PatchDrapePlan.uv(lat: box.maxLat, lon: box.minLon, box: box)
        let se = PatchDrapePlan.uv(lat: box.minLat, lon: box.maxLon, box: box)
        #expect(abs(nw.x) < 1e-6 && abs(nw.y) < 1e-6)
        #expect(abs(se.x - 1) < 1e-6 && abs(se.y - 1) < 1e-6)
        // mercator, not linear latitude: the centre latitude sits just south of v = 0.5
        let mid = PatchDrapePlan.uv(lat: (box.minLat + box.maxLat) / 2, lon: 31.40, box: box)
        #expect(abs(mid.x - 0.5) < 1e-6 && mid.y > 0.5 && mid.y < 0.5001)
        // a texel's UV lands on the same pixel the plan painted it at
        let plan = PatchDrapePlan(box: box, maxZoom: 15)!
        let x = plan.tiles[0].x + 1, y = plan.tiles[0].y + 1
        let lat = WebMercator.lat(tileY: Double(y), z: plan.zoom)
        let lon = WebMercator.lon(tileX: Double(x), z: plan.zoom)
        let uv = PatchDrapePlan.uv(lat: lat, lon: lon, box: box)
        let r = plan.rect(x: x, y: y)
        #expect(abs(Double(uv.x) * Double(plan.width) - r.minX) < 1.0)
        #expect(abs(Double(uv.y) * Double(plan.height) - r.minY) < 1.0)
    }

    // MARK: - Preview | Last build

    @Test func lastBuildFetchesOncePerBuildAndFallsBackWhenThereIsNoMesh() {
        var s = PatchLastBuildState()
        #expect(s.mode == .preview && s.canShowLastBuild)
        let r1 = s.select(.lastBuild, build: 100)           // first showing: fetch
        #expect(r1)
        s.fetching(build: 100)
        let r2 = s.select(.lastBuild, build: 100)          // already loading
        #expect(!r2)
        s.fetched(true)
        #expect(s.mode == .lastBuild && s.mesh == .available)
        let r3 = s.select(.preview, build: 100)
        #expect(!r3)
        let r4 = s.select(.lastBuild, build: 100)          // same build: no refetch
        #expect(!r4)
        let r5 = s.tileBuilt(100)                          // nothing new
        #expect(!r5)
        let r6 = s.tileBuilt(200)                           // rebuilt while showing: refetch
        #expect(r6)
        s.fetching(build: 200)
        s.fetched(false, reason: "the mesh was deleted")
        #expect(s.mode == .preview && !s.canShowLastBuild)
        #expect(s.unavailableReason == "the mesh was deleted")
        let r7 = s.select(.lastBuild, build: 200)          // refused while unavailable
        #expect(!r7)
        #expect(s.mode == .preview)
        let r8 = s.tileBuilt(300)    // a new build may have a mesh
        #expect(!r8 && s.canShowLastBuild)
    }

    // MARK: - Buildings on the last build

    @Test func aBuildingStandsOnTheLastBuildsMesh() throws {
        // one square of two triangles, 100 m at the west edge rising to 110 m at the east
        let verts: [Double] = [31.40, 30.10, 100, 31.41, 30.10, 110, 31.41, 30.11, 110, 31.40, 30.11, 100]
        let tris: [UInt32] = [0, 1, 2, 0, 2, 3]
        let json: [String: Any] = [
            "mesh_path": "/m",
            "vertices_f64_b64": verts.withUnsafeBytes { Data($0) }.base64EncodedString(),
            "triangles_u32_b64": tris.withUnsafeBytes { Data($0) }.base64EncodedString(),
        ]
        let crop = try O4JSON.from(json).decode(O4MeshCrop.self)
        let frame = PatchLocalFrame(originLat: 30.105, originLon: 31.405)
        let locator = PatchSurfaceLocator(meshCrop: crop, frame: frame, cells: 4)
        let space = PatchPreviewSpace(frame: frame, base: 90, terrain: nil)
        let mid = locator.surface(lat: 30.105, lon: 31.405, space: space)
        #expect(mid.way == nil && abs(mid.z - 105) < 1e-6)
        #expect(locator.surface(lat: 30.2, lon: 31.405, space: space).z == 90)   // off the mesh
    }
}
