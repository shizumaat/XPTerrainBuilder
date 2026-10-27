import Testing
import Foundation
@testable import SceneryKit

/// Issue #825: the per-step strip of each tile's Activity row. Replays the
/// fixture the Qt twin replays (`Ortho4XP/tests/test_step_strip.py`), so
/// both apps show the same strip for the same engine events.
@Suite struct StepStripTests {
    struct Step {
        let t: Double
        let event: O4Event
        let expect: [[String]]?
    }

    struct Case {
        let name: String
        let steps: [Step]
    }

    static let cases: [Case] = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/step_strip_cases.json")
        // swiftlint:disable force_try force_cast
        let root = try! JSONSerialization.jsonObject(with: Data(contentsOf: url)) as! [String: Any]
        return (root["cases"] as! [[String: Any]]).map { item in
            Case(name: item["name"] as! String,
                 steps: (item["steps"] as! [[String: Any]]).map { step in
                     Step(t: (step["t"] as! NSNumber).doubleValue,
                          event: O4Event.parse(object: step["event"] as! [String: Any])!,
                          expect: step["expect"] as? [[String]])
                 })
        }
        // swiftlint:enable force_try force_cast
    }()

    @Test func fixtureCasesMatchTheQtTwin() {
        #expect(!Self.cases.isEmpty)
        for item in Self.cases {
            var strip = O4StepStrip()
            var checked = 0
            for step in item.steps {
                strip.apply(step.event, at: step.t)
                guard let expect = step.expect else { continue }
                let got = strip.segments.map { [$0.state.rawValue, $0.text] }
                #expect(got == expect, "\(item.name) after t=\(step.t)")
                checked += 1
            }
            #expect(checked > 0, "\(item.name)")
        }
    }

    @Test func stopFreezesTheStrip() {
        var strip = O4StepStrip()
        strip.apply(.stepProgress(lat: 1, lon: 2, stepKey: "mesh", label: "", percent: 0,
                                  indeterminate: false), at: 0)
        strip.stop(at: 5)
        strip.apply(.stepProgress(lat: 1, lon: 2, stepKey: "masks", label: "", percent: 0,
                                  indeterminate: false), at: 6)
        #expect(strip.segments.map(\.state) == [.skipped, .skipped, .stopped,
                                                 .waiting, .waiting, .waiting])
    }

    @Test func airportStageWords() {
        #expect(O4StepStrip.airportStage("Solving the surface (HiGHS LP)") == "shaping runways")
        #expect(O4StepStrip.airportStage("Something new") == "grading")
    }
}
