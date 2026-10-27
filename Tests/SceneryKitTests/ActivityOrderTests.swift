import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_activity_order.py` (#1341): both read
/// `Ortho4XP/tests/fixtures/activity_order_cases.json`.
@Suite struct ActivityOrderTests {
    struct Cases: Decodable {
        struct Finished: Decodable { let state: String; let label: String; let finished: Bool }
        struct Compact: Decodable { let state: String; let compact: Bool }
        struct ToneCase: Decodable {
            let state: String, label: String, has_issues: Bool, tone: String
        }
        struct Step: Decodable { let rows: [[String]]; let order: [String] }
        struct Sequence: Decodable { let name: String; let steps: [Step] }
        let finished: [Finished]
        let compact: [Compact]
        let tones: [ToneCase]
        let sequences: [Sequence]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/activity_order_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func finishedLikeThePythonTwin() {
        for c in Self.cases.finished {
            #expect(ActivityOrder.isFinished(state: c.state, label: c.label) == c.finished,
                    "\(c.state) \(c.label)")
        }
    }

    @Test func compactLikeThePythonTwin() {
        #expect(!Self.cases.compact.isEmpty)
        for c in Self.cases.compact {
            #expect(ActivityOrder.isCompact(state: c.state) == c.compact, "\(c.state)")
        }
    }

    @Test func toneLikeThePythonTwin() {
        for c in Self.cases.tones {
            let tone = ActivityOrder.tone(state: c.state, label: c.label, hasIssues: c.has_issues)
            #expect(tone.rawValue == c.tone, "\(c.state) \(c.label)")
        }
    }

    @Test func orderLikeThePythonTwin() {
        for sequence in Self.cases.sequences {
            var stamps: [String: ActivityOrder.Stamp] = [:]
            var counter = 0
            for (number, step) in sequence.steps.enumerated() {
                let rows: [(key: String, finished: Bool)] = step.rows.map {
                    (key: $0[0], finished: ActivityOrder.isFinished(state: $0[1], label: $0[2]))
                }
                let next = ActivityOrder.restamp(rows, stamps: stamps, counter: counter)
                stamps = next.stamps
                counter = next.counter
                let order = ActivityOrder.order(step.rows.map { $0[0] }, stamps: stamps)
                #expect(order == step.order, "\(sequence.name) step \(number)")
            }
        }
    }
}
