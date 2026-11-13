import XCTest
@testable import SceneryKit

/// #2061: the map's patch loads without the staleness check when the
/// engine answers it on its own, and the answer completes only the document
/// it was asked for. Twin of `Ortho4XP/tests/test_qt_patch_view_load.py`:
/// both read `Ortho4XP/tests/fixtures/patch_view_load_cases.json`.
final class PatchViewLoadTests: XCTestCase {
    private func fixture() throws -> [String: Any] {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/patch_view_load_cases.json")
        return try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
    }

    func testTheSharedLoadCases() throws {
        let cases = try XCTUnwrap(try fixture()["load_cases"] as? [[String: Any]])
        XCTAssertFalse(cases.isEmpty)
        for test in cases {
            let got = PatchViewLoad.loadArguments(tile: test["tile"] as? String ?? "",
                                                  icao: test["icao"] as? String ?? "",
                                                  fast: test["fast"] as? Bool ?? false)
            let want = try XCTUnwrap(test["arguments"] as? [String: Any])
            XCTAssertEqual(NSDictionary(dictionary: got), NSDictionary(dictionary: want),
                           test["name"] as? String ?? "")
        }
    }

    func testTheSharedAppliesCases() throws {
        let cases = try XCTUnwrap(try fixture()["applies_cases"] as? [[String: Any]])
        XCTAssertFalse(cases.isEmpty)
        for test in cases {
            XCTAssertEqual(PatchViewLoad.stalenessApplies(openedPath: test["opened_path"] as? String ?? "",
                                                          answerPath: test["answer_path"] as? String ?? ""),
                           test["applies"] as? Bool, test["name"] as? String ?? "")
        }
    }

    func testAnAnswerFillsTheDocumentItWasAskedFor() throws {
        let json = """
        {"icao": "LXYZ", "source": "auto", "path": "/P/LXYZ_auto.patch.osm", "stale": false,
         "stale_inputs": [], "stale_pending": true, "min_distinct_spacing_m": 0.05, "identity_dp": 11,
         "header": {}, "nodes": [], "ways": []}
        """
        let load = try JSONDecoder().decode(O4PatchLoad.self, from: Data(json.utf8))
        var doc = PatchDocument(tile: "+30+031", load: load)
        XCTAssertFalse(doc.applyStaleness(O4PatchStaleness(path: "/P/other.patch.osm", stale: true,
                                                           staleInputs: ["o4_dem"])))
        XCTAssertFalse(doc.stale)
        XCTAssertTrue(doc.applyStaleness(O4PatchStaleness(path: "/P/LXYZ_auto.patch.osm", stale: true,
                                                          staleInputs: ["o4_dem"])))
        XCTAssertTrue(doc.stale)
        XCTAssertEqual(doc.staleInputs, ["o4_dem"])
    }
}
