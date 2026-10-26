import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_coordinate_query.py` (#1317): both read
/// `Ortho4XP/tests/fixtures/latlon_search_cases.json`, so the Mac and Qt
/// search fields read a typed coordinate the same way.
@Suite struct CoordinateQueryTests {
    struct Cases: Decodable {
        struct Tile: Decodable { let text: String; let lat: Int; let lon: Int }
        struct Point: Decodable { let text: String; let lat: Double; let lon: Double }
        let tiles: [Tile]
        let points: [Point]
        let rejects: [String]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/latlon_search_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func tileKeysWinLikeThePythonTwin() {
        for c in Self.cases.tiles {
            #expect(CoordinateQuery.parse(c.text) == .tile(lat: c.lat, lon: c.lon), "\(c.text)")
        }
    }

    @Test func pointsLikeThePythonTwin() {
        for c in Self.cases.points {
            guard case let .point(lat, lon)? = CoordinateQuery.parse(c.text) else {
                Issue.record("not a point: \(c.text)")
                continue
            }
            #expect(abs(lat - c.lat) < 1e-9 && abs(lon - c.lon) < 1e-9, "\(c.text)")
        }
    }

    @Test func rejectsLikeThePythonTwin() {
        for text in Self.cases.rejects {
            #expect(CoordinateQuery.parse(text) == nil, "\(text)")
        }
    }
}
