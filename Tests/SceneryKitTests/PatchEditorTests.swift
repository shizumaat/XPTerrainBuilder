import Testing
import Foundation
@testable import SceneryKit

/// The patch editor's protocol-1.12 replies (spec
/// `Ortho4XP/docs/specs/patch-editor-20261015.md` §2), the document, its
/// spatial grid and the role styling. The JSON keys in the fixture are the
/// FROZEN wire contract; a rename on either side fails here.
struct PatchEditorTests {

    private func fixture(_ command: String) throws -> O4JSON {
        let url = try #require(Bundle.module.url(
            forResource: "Fixtures/PatchEditor/patch_protocol_1_12", withExtension: "json"))
        let object = try JSONSerialization.jsonObject(with: Data(contentsOf: url))
        return try #require(O4JSON.from(object)[command])
    }

    /// Through the client's own reply path (`O4Reply` → typed result).
    private func decode<T: Decodable>(_ command: String, as: T.Type) throws -> T {
        let reply = O4Reply(ok: true, result: try fixture(command), error: nil)
        let result: Result<T, Error> = OrthoEngineClient.decodeReply(reply, command: command)
        return try result.get()
    }

    private func document() throws -> PatchDocument {
        PatchDocument(tile: "+45-123", load: try decode("patch_load", as: O4PatchLoad.self))
    }

    // MARK: - Decoding

    @Test func patchListDecodes() throws {
        let list = try decode("patch_list", as: O4PatchList.self)
        let entry = try #require(list.airports.first)
        #expect(entry.icao == "ZZZZ")
        #expect(entry.source == .auto)
        #expect(entry.nodes == 14 && entry.ways == 7)
        #expect(entry.bbox.minLat == 45.539 && entry.bbox.maxLon == -122.938)
    }

    @Test func patchLoadDecodesNodesWaysAndHeader() throws {
        let load = try decode("patch_load", as: O4PatchLoad.self)
        #expect(load.minDistinctSpacingM == 0.5)
        #expect(load.identityDp == 11)
        #expect(load.stale == false && load.staleInputs.isEmpty)
        // Header and tag KEYS keep their snake case (no key strategy).
        #expect(load.header["o4_fresh_v"] == "3")
        #expect(load.nodes.first == O4PatchNodeRow(id: -1, lat: 45.54, lon: -122.95, alt: 62.4))
        #expect(load.nodes.first { $0.id == -8 }?.alt == nil)
        #expect(load.ways.first?.refs == [-1, -2, -3, -4, -1])
        #expect(load.ways.first?.tags["ref"] == "15/33")
    }

    @Test func binaryRepliesDecodeLittleEndian() throws {
        let terrain = try decode("terrain_sample", as: O4TerrainSample.self)
        #expect(terrain.rows == 2 && terrain.cols == 3)
        #expect(terrain.elevations == [61.5, 62.0, 62.25, 63.0, -1.5, 1000.125])
        #expect(terrain.sources["base"] == .some("N45W123.hgt"))
        let mesh = try decode("mesh_crop", as: O4MeshCrop.self)
        #expect(mesh.vertices == [-122.95, 45.54, 62.4, -122.94, 45.5405, 62.7])
        #expect(mesh.triangles == [0, 1, 4_000_000_000])
        let objects = try decode("pack_objects", as: O4PackObjects.self)
        #expect(objects.models.first?.key == "7")
        #expect(objects.models.first?.vertices == [1, 2.5, -3])
        #expect(objects.placements.first?.model == "7")
        #expect(objects.facades.first?.heightM == 8.5)
        let outlines = try decode("pack_outlines", as: O4PackOutlines.self)
        #expect(outlines.pavement.first?.rings.first?.count == 3)
        #expect(outlines.pavement.last?.kind == "boundary" && outlines.pavement.last?.rings.count == 2)
    }

    @Test func refusedCommandCarriesTheEngineSentence() {
        let reply = O4Reply(ok: false, result: nil, error: "No patch for ZZZZ. Build the tile first.")
        let result: Result<O4PatchList, Error> = OrthoEngineClient.decodeReply(reply, command: "patch_list")
        #expect(throws: O4CommandError("No patch for ZZZZ. Build the tile first.")) { try result.get() }
    }

    @Test func protocolGateIsOneTwelve() {
        #expect(O4ProtocolVersion.supportsPatchEditor("1.12"))
        #expect(O4ProtocolVersion.supportsPatchEditor("2.0"))
        #expect(!O4ProtocolVersion.supportsPatchEditor("1.11"))
        #expect(!O4ProtocolVersion.supportsPatchEditor(""))
    }

    @Test func saveRowsRoundTripTheLoad() throws {
        let load = try decode("patch_load", as: O4PatchLoad.self)
        let rows = PatchDocument(tile: "+45-123", load: load).saveRows
        #expect(rows.nodes == load.nodes)
        #expect(rows.ways == load.ways)
    }

    // MARK: - Document, bbox, grid

    @Test func documentBboxIndexAndNewIDs() throws {
        let doc = try document()
        let box = try #require(doc.bbox)
        #expect(box.minLat == 45.539 && box.maxLat == 45.5425)
        #expect(box.minLon == -122.95 && box.maxLon == -122.938)
        // -4 and -3 are welded: the runway and the taxiway share that edge.
        #expect(Set(doc.waysUsing(-4).map(\.id)) == [-101, -102])
        #expect(doc.nextNewNodeID == -15)
        #expect(doc.nodesWithoutElevation == 1)
        #expect(!doc.isUserEdited)
    }

    @Test func gridFindsTheNearestNodeWithinRadius() throws {
        let doc = try document()
        let grid = PatchSpatialGrid(document: doc)
        let n1 = doc.frame.metres(lat: 45.54, lon: -122.95)
        #expect(grid.nearestNode(x: n1.x + 3, y: n1.y - 2, within: 8) == -1)
        #expect(grid.nearestNode(x: n1.x + 30, y: n1.y + 30, within: 8) == nil)
        // Box select around the building's three nodes only.
        let a = doc.frame.metres(lat: 45.54205, lon: -122.94795)
        let b = doc.frame.metres(lat: 45.54255, lon: -122.94745)
        #expect(grid.nodes(minX: a.x, minY: a.y, maxX: b.x, maxY: b.y) == [-11, -10, -9])
    }

    @Test func gridFindsEdgesAlongLongSegments() throws {
        let doc = try document()
        let grid = PatchSpatialGrid(document: doc)
        // Mid-way along the runway's south edge -1 → -2 (~780 m long),
        // 4 m north of it: far from every node, on the edge.
        let mid = doc.frame.metres(lat: 45.54, lon: -122.945)
        let hit = try #require(grid.nearestEdge(x: mid.x, y: mid.y + 4, within: 8))
        #expect(Set([hit.a, hit.b]) == [-1, -2])
        #expect(abs(hit.distance - 4) < 1e-6)
        #expect(abs(hit.t - 0.5) < 1e-6)
        #expect(grid.nearestNode(x: mid.x, y: mid.y + 4, within: 8) == nil)
        #expect(grid.nearestEdge(x: mid.x, y: mid.y + 20, within: 8) == nil)
    }

    @Test func localFrameMatchesTheEmitPlane() {
        let frame = PatchLocalFrame(originLat: 60, originLon: 10)
        #expect(abs(frame.metresPerDegreeLon - 55_660) < 1e-6)
        let p = frame.metres(lat: 60.001, lon: 10.001)
        #expect(abs(p.y - 111.32) < 1e-9)
        let back = frame.latLon(x: p.x, y: p.y)
        #expect(abs(back.lat - 60.001) < 1e-12 && abs(back.lon - 10.001) < 1e-12)
    }

    // MARK: - Role styling

    @Test func roleStylingOfTheEnginesTags() throws {
        let doc = try document()
        let styles = Dictionary(uniqueKeysWithValues: doc.ways.map { ($0.id, $0.style) })
        #expect(styles[-101] == .runway)
        #expect(styles[-102] == .taxiway)       // primary_parallel → aeroway=taxiway
        #expect(styles[-103] == .apron)
        #expect(styles[-104] == .building)      // role wins over aeroway=apron
        #expect(styles[-105] == .ground)        // graded_strip, aeroway=apron
        #expect(styles[-106] == .road)
        #expect(styles[-107] == .ground)        // untagged helper line
        #expect(doc.ways.first { $0.id == -106 }?.isClosed == false)
        #expect(PatchStyleClass(tags: ["aeroway": "taxiway", "role": "junction"]) == .taxiway)
        #expect(PatchStyleClass(tags: ["role": "groundside_pavement"]) == .groundside)   // #1099
        #expect(PatchStyleClass(tags: ["role": "parking_lot", "aeroway": "apron"]) == .groundside)
        #expect(PatchStyleClass(tags: ["aeroway": "aerodrome"]) == .ground)
        #expect(PatchStyleClass(tags: ["highway": "residential"]) == .road)
    }
}
