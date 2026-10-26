import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_map_overzoom.py` (#1315): both run
/// `Ortho4XP/tests/fixtures/map_overzoom_cases.json`, so the Mac and Qt
/// maps draw the same ancestor tile past the source's ceiling and show
/// the same badge.
@Suite struct MapOverzoomTests {
    struct Cases: Decodable {
        struct AncestorCase: Decodable {
            let z: Int, x: Int, y: Int, max_z: Int
            let ancestor: [Int]
            let sub: [Double]
        }
        struct Badge: Decodable {
            let view_zl: Int, source: String?, max_zl: Int?, factor: Int, text: String
        }
        let max_view_zl: Int
        let ancestor: [AncestorCase]
        let badge: [Badge]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/map_overzoom_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func viewCeilingLikeThePythonTwin() {
        #expect(MapOverzoom.maxViewZL == Self.cases.max_view_zl)
    }

    @Test func ancestorLikeThePythonTwin() {
        for c in Self.cases.ancestor {
            let a = MapOverzoom.ancestor(z: c.z, x: c.x, y: c.y, maxZ: c.max_z)
            #expect([a.z, a.x, a.y] == c.ancestor, "\(c)")
            #expect([a.subX, a.subY, a.subSize] == c.sub, "\(c)")
        }
    }

    @Test func badgeLikeThePythonTwin() {
        for c in Self.cases.badge {
            if let maxZL = c.max_zl {
                #expect(MapOverzoom.overzoomFactor(viewZL: c.view_zl, maxZL: maxZL) == c.factor)
            }
            #expect(MapOverzoom.badgeText(viewZL: c.view_zl, source: c.source,
                                          maxZL: c.max_zl) == c.text, "\(c)")
        }
    }

    @Test func viewCeilingScaleIsTheCeilingZL() {
        let scale = MapOverzoom.scale(forZL: MapOverzoom.maxViewZL)
        #expect(Int(ceil(log2(scale * 360 / 256) - 1e-9)) == MapOverzoom.maxViewZL)
    }
}
