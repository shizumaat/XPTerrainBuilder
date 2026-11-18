import Testing
import Foundation
@testable import SceneryKit

/// A patch shape's own elevation tags (#2137) against the engine's twin
/// fixture `Ortho4XP/tests/fixtures/patch_shape_alt.json` (read in place).
struct PatchShapeAltitudeTests {
    static func fixture() throws -> [String: Any] {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/patch_shape_alt.json")
        return try #require(try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }

    static func cases(_ key: String) throws -> [[String: Any]] {
        try #require(try fixture()[key] as? [[String: Any]])
    }

    static func number(_ v: Any?) -> Double? { (v as? NSNumber)?.doubleValue }

    /// The fixture's expectation in the Swift enum.
    static func expected(_ want: Any?) -> PatchShapeAltitude? {
        guard let want = want as? [String: Any], let form = want["form"] as? String else { return nil }
        if form == "slope" {
            return .slope(high: number(want["high"]), low: number(want["low"]), valid: want["valid"] as? Bool ?? false)
        }
        return .level(form: PatchShapeAltitude.Form(rawValue: form)!, key: want["key"] as! String,
                      value: number(want["value"]))
    }

    @Test func recognizesEveryFixtureCase() throws {
        let cases = try Self.cases("recognize")
        #expect(cases.count >= 10)
        for c in cases {
            let tags = c["tags"] as! [String: String]
            let refs = (c["refs"] as! [NSNumber]).map(\.int64Value)
            #expect(PatchShapeAltitude(tags: tags, refs: refs) == Self.expected(c["expect"]), "\(c["name"]!)")
        }
    }

    @Test func levelEditsWriteTheFixtureTags() throws {
        for c in try Self.cases("level") {
            let got = PatchShapeAltitude.levelTags(c["tags"] as! [String: String], value: Self.number(c["value"])!)
            #expect(got == c["expect"] as! [String: String], "\(c["name"]!)")
        }
    }

    @Test func slopeEditsWriteTheFixtureTags() throws {
        for c in try Self.cases("slope") {
            let got = PatchShapeAltitude.slopeTags(c["tags"] as! [String: String],
                                                   high: Self.number(c["high"]), low: Self.number(c["low"]))
            #expect(got == c["expect"] as! [String: String], "\(c["name"]!)")
        }
    }

    @Test func labelsAreTheFixtureWords() throws {
        for c in try Self.cases("labels") {
            let side = PatchShapeAltitude.Side(rawValue: c["side"] as! String)!
            #expect(PatchShapeAltitude.label(side, Self.number(c["value"])) == c["expect"] as! String)
        }
    }

    @Test func slopeMarksMatchTheEngine() throws {
        let tol = try #require((try Self.fixture()["tolerance"] as? [String: Double])?["deg"])
        func points(_ v: Any?) -> [PatchSlopeMarks.LatLon] {
            (v as! [[NSNumber]]).map { .init(lat: $0[0].doubleValue, lon: $0[1].doubleValue) }
        }
        func close(_ a: [PatchSlopeMarks.LatLon], _ b: [PatchSlopeMarks.LatLon]) -> Bool {
            a.count == b.count && zip(a, b).allSatisfy { abs($0.lat - $1.lat) <= tol && abs($0.lon - $1.lon) <= tol }
        }
        for c in try Self.cases("marks") {
            let got = PatchSlopeMarks(corners: points(c["corners"]))
            guard let want = c["expect"] as? [String: Any] else {
                #expect(got == nil, "\(c["name"]!)")
                continue
            }
            let g = try #require(got)
            #expect(close(g.highEdge, points(want["high_edge"])), "\(c["name"]!) high edge")
            #expect(close(g.lowEdge, points(want["low_edge"])), "\(c["name"]!) low edge")
            #expect(close(g.arrow, points(want["arrow"])), "\(c["name"]!) arrow")
            #expect(close([g.highLabel], points([want["high_label"]!])), "\(c["name"]!) high label")
            #expect(close([g.lowLabel], points([want["low_label"]!])), "\(c["name"]!) low label")
        }
    }

    /// The editor's path: set the tags on a document, save rows carry them.
    @Test func setWayTagsReachesTheSaveRows() throws {
        var doc = try PatchEditOpsTests.document([
            "nodes": [[-1, 30.0, 31.0, NSNull()], [-2, 30.0, 31.001, NSNull()], [-3, 30.001, 31.001, NSNull()],
                      [-4, 30.001, 31.0, NSNull()]],
            "ways": [["id": -9, "refs": [-1, -2, -3, -4, -1],
                      "tags": ["altitude_high": "172.40", "altitude_low": "170.90", "role": "tunnel_ramp"]]],
        ])
        let way = doc.ways[0]
        try doc.setWayTags(-9, put: PatchShapeAltitude.slopeTags(way.tags, high: nil, low: 168.5))
        let row = try #require(doc.saveRows.ways.first)
        #expect(row.tags["altitude_low"] == "168.50")
        #expect(row.tags["altitude_high"] == "172.40")
        #expect(PatchShapeAltitude(way: doc.ways[0]) == .slope(high: 172.4, low: 168.5, valid: true))
        #expect(PatchSlopeMarks(way: doc.ways[0], in: doc) != nil)
        #expect(throws: PatchEditError.unknownWay(-1)) { try doc.setWayTags(-1, put: [:]) }
    }
}
