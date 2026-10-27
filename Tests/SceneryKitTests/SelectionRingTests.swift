import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_qt_selection_ring.py` (#1537): both read
/// `Ortho4XP/tests/fixtures/selection_ring_cases.json`.
@Suite struct SelectionRingTests {
    struct Case: Decodable {
        let name: String
        let rows: [String]
        let selected: [String]
        let active: String?
        let rings: [String: String]
    }
    struct Cases: Decodable { let cases: [Case] }

    static let cases: [Case] = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/selection_ring_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url)).cases
    }()

    @Test func ringsLikeThePythonTwin() {
        #expect(!Self.cases.isEmpty)
        for c in Self.cases {
            let rings = SelectionRing.rings(rows: c.rows, selected: Set(c.selected), active: c.active)
            #expect(rings.mapValues(\.rawValue) == c.rings, "\(c.name)")
        }
    }
}
