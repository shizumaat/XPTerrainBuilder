import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_map_labels.py` (#817): both run
/// `Ortho4XP/tests/fixtures/map_label_cases.json`, so the Mac and Qt maps
/// mark, size and place the same airport labels.
@Suite struct MapLabelLayoutTests {
    struct Cases: Decodable {
        struct Gate: Decodable {
            let size_class: Int, custom: Bool, scale: Double, mark: Bool, label: Bool
        }
        struct Font: Decodable { let scale: Double; let size: Double }
        struct Radius: Decodable { let scale: Double; let radius: Double }
        struct Imagery: Decodable { let provider: String?; let zl: Int?; let zones: Bool; let text: String }
        struct Candidate: Decodable {
            let code: String, x: Double, y: Double, size_class: Int, runway_m: Int, custom: Bool
        }
        struct Place: Decodable {
            let scale: Double, radius: Double
            let candidates: [Candidate]
            let marks: [String], labels: [String]
        }
        let gates: [Gate]
        let font: [Font]
        let radius: [Radius]
        let imagery: [Imagery]
        let place: [Place]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/map_label_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func gatesLikeThePythonTwin() {
        for c in Self.cases.gates {
            #expect(MapLabelLayout.markVisible(sizeClass: c.size_class, custom: c.custom,
                                               scale: c.scale) == c.mark, "\(c)")
            #expect(MapLabelLayout.labelAllowed(sizeClass: c.size_class, custom: c.custom,
                                                scale: c.scale) == c.label, "\(c)")
        }
    }

    @Test func fontSizeLikeThePythonTwin() {
        for c in Self.cases.font {
            #expect(MapLabelLayout.fontSize(scale: c.scale) == c.size, "\(c.scale)")
        }
    }

    @Test func markRadiusLikeThePythonTwin() {
        for c in Self.cases.radius {
            #expect(MapLabelLayout.markRadius(scale: c.scale) == c.radius, "\(c.scale)")
        }
    }

    @Test func imageryLabelLikeThePythonTwin() {
        for c in Self.cases.imagery {
            #expect(MapLabelLayout.imageryLabel(provider: c.provider, zl: c.zl,
                                                hasZones: c.zones) == c.text)
        }
    }

    @Test func placementLikeThePythonTwin() {
        for c in Self.cases.place {
            let candidates = c.candidates.map {
                MapLabelLayout.Candidate(code: $0.code, x: $0.x, y: $0.y, sizeClass: $0.size_class,
                                         runwayMeters: $0.runway_m, custom: $0.custom)
            }
            let (marks, labels) = MapLabelLayout.place(candidates, scale: c.scale,
                                                       markRadius: c.radius)
            #expect(marks.map { candidates[$0].code } == c.marks)
            #expect(labels.map { candidates[$0.index].code } == c.labels)
        }
    }

    @Test func denseGridNeverOverlaps() {
        var candidates: [MapLabelLayout.Candidate] = []
        for i in 0..<40 {
            for j in 0..<40 {
                candidates.append(.init(code: String(format: "A%03d", i * 40 + j),
                                        x: 8.0 * Double(i), y: 8.0 * Double(j),
                                        sizeClass: 0, runwayMeters: 3000, custom: false))
            }
        }
        let boxes = MapLabelLayout.place(candidates, scale: 100, markRadius: 5).labels.map(\.box)
        #expect(!boxes.isEmpty && boxes.count <= MapLabelLayout.maxAirportLabels)
        for a in boxes.indices {
            for b in boxes.indices where b > a {
                #expect(!boxes[a].overlaps(boxes[b]))
            }
        }
    }
}
