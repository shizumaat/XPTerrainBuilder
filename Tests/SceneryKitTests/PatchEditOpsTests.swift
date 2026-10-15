import Testing
import Foundation
@testable import SceneryKit

/// The §3 edit operations against the engine's twin fixture
/// `Ortho4XP/tests/fixtures/patch_edit_ops.json` (read in place, never
/// copied), undo/redo round trips of each op, and the §3.3 snap choice.
struct PatchEditOpsTests {

    // MARK: - Fixture

    struct Fixture {
        let degTolerance: Double
        let mTolerance: Double
        let cases: [[String: Any]]
    }

    static func fixture() throws -> Fixture {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/patch_edit_ops.json")
        let root = try #require(try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let tolerance = try #require(root["tolerance"] as? [String: Double])
        return Fixture(degTolerance: try #require(tolerance["deg"]), mTolerance: try #require(tolerance["m"]),
                       cases: try #require(root["cases"] as? [[String: Any]]))
    }

    /// A document from a fixture `{nodes, ways}` through the real
    /// `patch_load` decoding path.
    static func document(_ doc: [String: Any], identityDp: Int = 11) throws -> PatchDocument {
        let load: [String: Any] = [
            "icao": "ZZZZ", "source": "auto", "path": "/tmp/ZZZZ_auto.patch.osm", "stale": false,
            "stale_inputs": [], "min_distinct_spacing_m": 0.5, "identity_dp": identityDp, "header": [:],
            "nodes": doc["nodes"] ?? [], "ways": doc["ways"] ?? [],
        ]
        let data = try JSONSerialization.data(withJSONObject: load)
        return PatchDocument(tile: "+30+031", load: try JSONDecoder().decode(O4PatchLoad.self, from: data))
    }

    static func ids(_ value: Any?) -> [Int64] {
        ((value as? [Any]) ?? []).compactMap { ($0 as? NSNumber)?.int64Value }
    }

    static func number(_ value: Any?) -> Double? { (value as? NSNumber)?.doubleValue }

    static func apply(_ op: [String: Any], to doc: inout PatchDocument) throws {
        let args = op["args"] as? [String: Any] ?? [:]
        func int(_ k: String) -> Int64 { (args[k] as! NSNumber).int64Value }
        switch op["op"] as? String {
        case "move": try doc.move(ids(args["ids"]), dlat: number(args["dlat"])!, dlon: number(args["dlon"])!)
        case "set_position": try doc.setPosition(int("id"), lat: number(args["lat"])!, lon: number(args["lon"])!)
        case "set_alt": try doc.setAlt(ids(args["ids"]), alt: number(args["alt"]))
        case "offset_alt": try doc.offsetAlt(ids(args["ids"]), by: number(args["d"])!)
        case "delete_nodes": try doc.deleteNodes(ids(args["ids"]))
        case "insert_on_edge": try doc.insertOnEdge(int("a"), int("b"))
        case "merge_nodes": try doc.mergeNodes(source: int("source"), target: int("target"))
        default: Issue.record("unknown op \(op["op"] ?? "nil")")
        }
    }

    @Test func everyFixtureCaseMatchesTheEngine() throws {
        let fixture = try Self.fixture()
        #expect(fixture.cases.count >= 22)
        for c in fixture.cases {
            let name = c["name"] as? String ?? "?"
            var doc = try Self.document(try #require(c["doc"] as? [String: Any]))
            for op in try #require(c["ops"] as? [[String: Any]]) { try Self.apply(op, to: &doc) }
            let expect = try #require(c["expect"] as? [String: Any])
            let rows = doc.saveRows
            let nodes = try #require(expect["nodes"] as? [[Any]])
            #expect(rows.nodes.count == nodes.count, "\(name): node count")
            for (got, want) in zip(rows.nodes, nodes) {
                #expect(got.id == (want[0] as! NSNumber).int64Value, "\(name): node order")
                #expect(abs(got.lat - Self.number(want[1])!) <= fixture.degTolerance, "\(name): lat of \(got.id)")
                #expect(abs(got.lon - Self.number(want[2])!) <= fixture.degTolerance, "\(name): lon of \(got.id)")
                switch (got.alt, Self.number(want[3])) {
                case (nil, nil): break
                case let (g?, w?): #expect(abs(g - w) <= fixture.mTolerance, "\(name): alt of \(got.id)")
                default: Issue.record("\(name): alt of \(got.id) is \(String(describing: got.alt))")
                }
            }
            let ways = try #require(expect["ways"] as? [[String: Any]])
            #expect(rows.ways.map(\.id) == ways.map { ($0["id"] as! NSNumber).int64Value }, "\(name): ways")
            for (got, want) in zip(rows.ways, ways) {
                #expect(got.refs == Self.ids(want["refs"]), "\(name): refs of way \(got.id)")
                #expect(got.tags == (want["tags"] as? [String: String] ?? [:]), "\(name): tags of way \(got.id)")
            }
        }
    }

    // MARK: - Undo / redo

    /// The first fixture case's document: a ring -1…-4 plus an open way.
    private func smallDoc() throws -> PatchDocument {
        let c = try #require(try Self.fixture().cases.first { $0["name"] as? String == "insert_on_shared_edge_both_ways" })
        return try Self.document(try #require(c["doc"] as? [String: Any]))
    }

    private func roundTrip(_ edit: (inout PatchDocument) throws -> Void) throws -> PatchEditStep {
        let before = try smallDoc()
        var after = before
        try edit(&after)
        let step = PatchEditStep(from: before, to: after)
        var undone = after
        undone.apply(step, reversed: true)
        #expect(undone == before)
        var redone = undone
        redone.apply(step)
        #expect(redone == after)
        return step
    }

    @Test func everyOpUndoesAndRedoes() throws {
        let doc = try smallDoc()
        let ring = try #require(doc.ways.first)
        let a = ring.refs[0], b = ring.refs[1], c = ring.refs[2]

        let move = try roundTrip { try $0.move([a, b], dlat: 1e-5, dlon: -2e-5) }
        #expect(move.movedNodes == [a, b] && !move.topology)
        let place = try roundTrip { try $0.setPosition(c, lat: 30.5, lon: 31.5) }
        #expect(place.movedNodes == [c] && place.changedWays.isEmpty)
        let alt = try roundTrip { try $0.setAlt([a], alt: 12.5) }
        #expect(alt.movedNodes == [a] && !alt.topology)
        let offset = try roundTrip { try $0.offsetAlt([a, b], by: -1) }
        #expect(offset.movedNodes.isSubset(of: [a, b]))
        let delete = try roundTrip { try $0.deleteNodes([b]) }
        #expect(delete.topology && delete.changedWays.contains(ring.id) && delete.movedNodes.isEmpty)
        var newID: Int64 = 0
        let insert = try roundTrip { newID = try $0.insertOnEdge(a, b) }
        #expect(insert.topology && insert.changedWays.contains(ring.id) && insert.nodes[newID]?.before == nil)
        let merge = try roundTrip {
            try $0.move([b], dlat: 0, dlon: 1e-6)
            try $0.mergeNodes(source: b, target: a)
        }
        #expect(merge.topology && merge.nodes[b]?.after == nil && merge.changedWays.contains(ring.id))
    }

    @Test func newNodeIDsGoBelowTheMinimum() throws {
        var doc = try smallDoc()
        let low = try #require(doc.nodeOrder.min())
        let ring = try #require(doc.ways.first)
        let id = try doc.insertOnEdge(ring.refs[0], ring.refs[1])
        #expect(id == low - 1)
        #expect(doc.nodeOrder.last == id)
    }

    @Test func refusalsNameTheCause() throws {
        var doc = try smallDoc()
        #expect(throws: PatchEditError.unknownNode(999)) { try doc.move([999], dlat: 0, dlon: 0) }
        let ring = try #require(doc.ways.first)
        #expect(throws: PatchEditError.mergeIntoItself(ring.refs[0])) {
            try doc.mergeNodes(source: ring.refs[0], target: ring.refs[0])
        }
        #expect(throws: PatchEditError.notAnEdge(ring.refs[0], ring.refs[0])) {
            try doc.insertOnEdge(ring.refs[0], ring.refs[0])
        }
    }

    @Test func markSavedMakesItTheEditedManualPatch() throws {
        var doc = try smallDoc()
        #expect(!doc.isHandMade && doc.source == .auto)
        doc.markSaved(path: "/p/ZZZZ_edited.patch.osm")
        #expect(doc.source == .manual && doc.isUserEdited && !doc.isHandMade)
        doc.markSaved(path: "/p/ZZZZ_runways.patch.osm")
        #expect(doc.isHandMade)
    }

    // MARK: - Snap (§3.3)

    @Test func snapPicksTheNearestOnScreenWithinEightPoints() {
        let far = PatchSnap.Candidate(id: -1, x: 108.1, y: 100, lat: 1, lon: 1)
        let near = PatchSnap.Candidate(id: -2, x: 103, y: 104, lat: 2, lon: 2)
        let mid = PatchSnap.Candidate(id: -3, x: 100, y: 106, lat: 0, lon: 0)
        #expect(PatchSnap.target(pointerX: 100, pointerY: 100, candidates: [far, mid, near], identityDp: 11) == -2)
        #expect(PatchSnap.target(pointerX: 100, pointerY: 100, candidates: [far], identityDp: 11) == nil)
        let edge = PatchSnap.Candidate(id: -4, x: 108, y: 100, lat: 0, lon: 0)
        #expect(PatchSnap.target(pointerX: 100, pointerY: 100, candidates: [edge], identityDp: 11) == -4)
    }

    @Test func snapTiesGoToTheLowestSurvivorKey() {
        let north = PatchSnap.Candidate(id: -1, x: 104, y: 100, lat: 45.00000002, lon: -122.5)
        let south = PatchSnap.Candidate(id: -2, x: 96, y: 100, lat: 45.0, lon: -122.4)
        #expect(PatchSnap.target(pointerX: 100, pointerY: 100, candidates: [north, south], identityDp: 11) == -2)
        // Equal at the identity precision: lon decides.
        let west = PatchSnap.Candidate(id: -5, x: 100, y: 96, lat: 45.0, lon: -122.6)
        #expect(PatchSnap.target(pointerX: 100, pointerY: 100, candidates: [south, west], identityDp: 11) == -5)
        // Keys equal after rounding: the lower id.
        let twinA = PatchSnap.Candidate(id: -7, x: 100, y: 104, lat: 45.0, lon: -122.6)
        let twinB = PatchSnap.Candidate(id: -8, x: 100, y: 96, lat: 45.0000000000001, lon: -122.6)
        #expect(PatchSnap.target(pointerX: 100, pointerY: 100, candidates: [twinA, twinB], identityDp: 11) == -8)
    }
}
