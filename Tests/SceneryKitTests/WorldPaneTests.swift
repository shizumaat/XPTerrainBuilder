import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_world_pane.py`: both read
/// `Ortho4XP/tests/fixtures/world_pane_cases.json`, so the two apps call
/// the same packs ours (never "Other scenery") and say the same World-pack
/// status in the tile pane.
@Suite struct WorldPaneTests {
    struct Cases: Decodable {
        struct Pack: Decodable { let name: String; let ours: Bool }
        struct World: Decodable {
            let state: String, origin: String, sharp: Double, source: String, volume: String
        }
        struct Pane: Decodable {
            let world: World?
            let status: String, detail: String, built: Bool
        }
        let packs: [Pack]
        let pane: [Pane]
    }

    static let cases: Cases = {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/world_pane_cases.json")
        // swiftlint:disable:next force_try
        return try! JSONDecoder().decode(Cases.self, from: Data(contentsOf: url))
    }()

    @Test func ourPacksAreNeverOtherScenery() {
        for pack in Self.cases.packs {
            #expect(O4WorldPack.isOurs(pack.name) == pack.ours, "\(pack.name)")
        }
    }

    @Test func thePaneSaysWhatTheWorldPackHolds() {
        for row in Self.cases.pane {
            let tile = row.world.map {
                O4WorldTile(state: O4WorldTile.State(rawValue: $0.state)!, origin: $0.origin,
                            sharp: $0.sharp, source: $0.source, volume: $0.volume)
            }
            #expect(O4WorldStateText.paneStatus(tile) == row.status)
            #expect(O4WorldStateText.paneDetail(tile) == row.detail)
            #expect(O4WorldStateText.builtInWorld(tile) == row.built)
        }
    }
}
