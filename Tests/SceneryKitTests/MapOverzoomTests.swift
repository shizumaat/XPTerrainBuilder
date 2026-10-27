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
        struct Placeholder: Decodable {
            let url: String, headers: [String: String], placeholder: Bool
        }
        let max_view_zl: Int
        let ancestor: [AncestorCase]
        let badge: [Badge]
        let placeholder: [Placeholder]
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

    @Test func placeholderLikeThePythonTwin() {
        for c in Self.cases.placeholder {
            #expect(MapOverzoom.isPlaceholderTile(url: c.url, headers: c.headers) == c.placeholder,
                    "\(c)")
        }
    }

    /// #1540: a view ZL above the source's max draws the max-ZL tile,
    /// scaled up — never a request (or a "no imagery" tile) above it.
    @Test func aboveTheSourceMaxDrawsTheMaxZLTile() {
        let anc = MapOverzoom.displayAncestor(z: 22, x: 300001, y: 700003, maxZ: 19) { _, _, _ in false }
        #expect(anc == MapOverzoom.ancestor(z: 22, x: 300001, y: 700003, maxZ: 19))
        #expect(anc?.z == 19 && anc?.subSize == 0.125)
    }

    /// #1540: where the server answers "no imagery here" below the declared
    /// max (Bing at HECA: ZL 20 and 21 are its camera tile), the map draws
    /// the finest level that has imagery, scaled up.
    @Test func pastNoImageryTilesDrawsTheFinestImagery() {
        let (x, y) = (1231526, 864412)
        let empty: Set<[Int]> = [[21, x, y], [20, x >> 1, y >> 1]]
        let anc = MapOverzoom.displayAncestor(z: 22, x: x * 2, y: y * 2, maxZ: 21) { z, ax, ay in
            empty.contains([z, ax, ay])
        }
        #expect(anc == MapOverzoom.ancestor(z: 22, x: x * 2, y: y * 2, maxZ: 19))
        #expect(MapOverzoom.badgeText(viewZL: 22, source: "BI", maxZL: anc?.z)
                == "ZL 22 · overzoom ×8 (BI max ZL 19)")
    }

    @Test func everyLevelEmptyDrawsNothing() {
        #expect(MapOverzoom.displayAncestor(z: 5, x: 3, y: 4, maxZ: 21) { _, _, _ in true } == nil)
    }

    @Test func viewCeilingScaleIsTheCeilingZL() {
        let scale = MapOverzoom.scale(forZL: MapOverzoom.maxViewZL)
        #expect(Int(ceil(log2(scale * 360 / 256) - 1e-9)) == MapOverzoom.maxViewZL)
    }
}
