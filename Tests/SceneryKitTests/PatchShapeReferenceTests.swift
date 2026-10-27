import Testing
import Foundation
@testable import SceneryKit

/// "Copy shape reference" (#1281) against the engine's twin fixture
/// `Ortho4XP/tests/fixtures/patch_shape_reference.json` (read in place):
/// the Swift formatter and `O4_Qt_Patch_Reference.shape_reference_text`
/// produce the same text.
struct PatchShapeReferenceTests {

    static func cases() throws -> [[String: Any]] {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/patch_shape_reference.json")
        let root = try #require(try JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        return try #require(root["cases"] as? [[String: Any]])
    }

    @Test func everyFixtureCaseMatchesThePythonTwin() throws {
        let cases = try Self.cases()
        #expect(cases.count >= 3)
        for c in cases {
            let input = try #require(c["input"] as? [String: Any])
            let rows = try #require(input["vertices"] as? [[Any]])
            let vertices = try rows.map { row -> PatchShapeReference.Vertex in
                PatchShapeReference.Vertex(lat: try #require(row[0] as? Double), lon: try #require(row[1] as? Double),
                                           alt: row[2] as? Double)
            }
            let text = PatchShapeReference.text(
                tile: try #require(input["tile"] as? String), icao: try #require(input["icao"] as? String),
                patchFile: try #require(input["patch_file"] as? String),
                engineVersion: try #require(input["engine_version"] as? String),
                wayId: try #require((input["way_id"] as? NSNumber)?.int64Value),
                tags: try #require(input["tags"] as? [String: String]),
                closed: try #require(input["closed"] as? Bool),
                area: try #require((input["area_m2"] as? NSNumber)?.doubleValue),
                vertices: vertices)
            #expect(text == (c["expected"] as? String), "\(c["name"] as? String ?? "")")
        }
    }

    @Test func aDocumentWayDropsTheClosingNodeAndNamesTheFile() throws {
        let doc = try PatchEditOpsTests.document([
            "nodes": [[-1, 30.1, 31.4, 100.0] as [Any], [-2, 30.1, 31.401, 101.0] as [Any],
                      [-3, 30.101, 31.401, NSNull()] as [Any]] as [Any],
            "ways": [["id": -10, "refs": [-1, -2, -3, -1], "tags": ["role": "apron"]] as [String: Any]] as [Any],
        ] as [String: Any])
        let text = PatchShapeReference.text(for: doc.ways[0], in: doc, engineVersion: "1.2.3")
        #expect(text.contains("Patch file: ZZZZ_auto.patch.osm"))
        #expect(text.contains("Tile: +30+031"))
        #expect(text.contains("Vertices: 3"))
        #expect(text.contains("Elevation: 100.00 – 101.00 m (1 from the mesh)"))
        #expect(text.hasSuffix("30.101000000, 31.401000000"))
    }
}
