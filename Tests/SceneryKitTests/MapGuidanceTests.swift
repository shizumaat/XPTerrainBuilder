import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_map_guidance.py` (#828): both read
/// `Ortho4XP/tests/fixtures/map_guidance_cases.json`.
@Suite struct MapGuidanceTests {
    struct Cases: Decodable {
        struct Copy: Decodable {
            let hint: String, show_tips: String, empty_selection: String
            let nothing_built: String, pref_key: String
        }
        struct Sequence: Decodable { let dismissed: Bool; let events: [String]; let shown: [Bool] }
        let copy: Copy
        let sequences: [Sequence]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/map_guidance_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func copyLikeThePythonTwin() {
        let copy = Self.cases.copy
        #expect(MapGuidance.hintText == copy.hint)
        #expect(MapGuidance.showTipsTitle == copy.show_tips)
        #expect(MapGuidance.emptySelectionText == copy.empty_selection)
        #expect(MapGuidance.nothingBuiltText == copy.nothing_built)
        #expect(MapGuidance.hintDismissedKey == copy.pref_key)
    }

    @Test func dismissalLikeThePythonTwin() throws {
        for c in Self.cases.sequences {
            var dismissed = c.dismissed
            var shown: [Bool] = []
            for name in c.events {
                let event = try #require(MapGuidance.Event(rawValue: name))
                dismissed = MapGuidance.dismissed(after: event, from: dismissed)
                shown.append(!dismissed)
            }
            #expect(shown == c.shown, "\(c.events)")
        }
    }
}
