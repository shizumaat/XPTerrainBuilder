import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_text_scale.py` (#827): both read
/// `Ortho4XP/tests/fixtures/text_scale_cases.json`.
@Suite struct TextScaleTests {
    struct Cases: Decodable {
        struct Titles: Decodable { let bigger: String, smaller: String, actual: String }
        struct Clamp: Decodable { let value: Double; let step: Double }
        struct Step: Decodable { let value: Double; let next: Double }
        struct Scaled: Decodable { let points: Double; let value: Double; let result: Double }
        let steps: [Double]
        let defaultValue: Double
        let pref_key: String
        let titles: Titles
        let clamp: [Clamp]
        let bigger: [Step]
        let smaller: [Step]
        let scaled: [Scaled]

        enum CodingKeys: String, CodingKey {
            case steps, defaultValue = "default", pref_key, titles, clamp, bigger, smaller, scaled
        }
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/text_scale_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func stepsKeyAndTitlesLikeThePythonTwin() {
        let c = Self.cases
        #expect(TextScale.steps == c.steps)
        #expect(TextScale.defaultValue == c.defaultValue)
        #expect(TextScale.prefKey == c.pref_key)
        #expect(TextScale.biggerTitle == c.titles.bigger)
        #expect(TextScale.smallerTitle == c.titles.smaller)
        #expect(TextScale.actualTitle == c.titles.actual)
    }

    @Test func clampBiggerSmallerScaledLikeThePythonTwin() {
        for c in Self.cases.clamp { #expect(TextScale.clamp(c.value) == c.step) }
        for c in Self.cases.bigger { #expect(TextScale.bigger(c.value) == c.next) }
        for c in Self.cases.smaller { #expect(TextScale.smaller(c.value) == c.next) }
        for c in Self.cases.scaled { #expect(TextScale.scaled(c.points, c.value) == c.result) }
        #expect(TextScale.clamp(.nan) == TextScale.defaultValue)
    }

    @Test func persistsThroughUserDefaults() throws {
        let suite = "TextScaleTests-\(UUID().uuidString)"
        let defaults = try #require(UserDefaults(suiteName: suite))
        defer { defaults.removePersistentDomain(forName: suite) }
        #expect(TextScale.load(defaults) == TextScale.defaultValue)
        TextScale.save(1.2, defaults)
        #expect(TextScale.load(defaults) == 1.15)
        TextScale.save(TextScale.bigger(TextScale.load(defaults)), defaults)
        #expect(TextScale.load(defaults) == 1.3)
    }
}
