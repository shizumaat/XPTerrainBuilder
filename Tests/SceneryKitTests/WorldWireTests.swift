import Testing
import Foundation
@testable import SceneryKit

/// Twin of `Ortho4XP/tests/test_world_commands.py` (World spec W1): the
/// `WorldStatus` JSON the engine emits (the shared fixture
/// `Ortho4XP/tests/fixtures/world/world_status_event.json`) decodes field
/// for field, `WorldReady` completes a request, and the installed-scenery
/// scanner reads a World-pack placeholder as no tile (spec §18).
@Suite struct WorldWireTests {
    static let fixtures = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Ortho4XP/tests/fixtures")

    @Test func worldStatusDecodesThePythonEvent() throws {
        let url = Self.fixtures.appendingPathComponent("world/world_status_event.json")
        let object = try #require(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        guard case .worldStatus(let status) = try #require(O4Event.parse(object: object)) else {
            Issue.record("WorldStatus did not decode as .worldStatus")
            return
        }
        #expect(status.state == "idle" && status.installed)
        #expect(status.seenByXPlane == true && !status.restartNeeded)
        #expect(status.tiles == ["placeholder": 3, "drape": 0, "light": 1, "full": 2, "staged": 1])
        #expect(status.queue == 2 && status.slots == 1 && status.bytes == 1234)
        #expect(status.loaded == ["+53-063"])
        #expect(status.lastSwap == ["+53-064", "light", "2026-11-10T15:02:24Z"])
        #expect(abs(status.frameMS - 21.8) < 1e-9 && status.governor == "ok")
    }

    @Test func unknownSeenByXPlaneStaysNil() {
        let status = O4WorldStatus.parse(["state": "off", "seen_by_xplane": NSNull()])
        #expect(status.seenByXPlane == nil && status.state == "off")
        let reply = O4WorldStatus.parse(["regions": [["id": "europe", "name": "Europe",
                                                      "enabled": true, "placeholders": 2,
                                                      "tiles": 1]]])
        #expect(reply.regions == [.init(id: "europe", name: "Europe", enabled: true,
                                        placeholders: 2, tiles: 1)])
    }

    @Test func scannerReadsPlaceholdersAsNoTile() throws {
        let fm = FileManager.default
        let base = fm.temporaryDirectory.appendingPathComponent("world-scan-\(UUID().uuidString)")
        defer { try? fm.removeItem(at: base) }
        let root = base.appendingPathComponent("X-Plane")
        let pack = root.appendingPathComponent("Custom Scenery/\(O4WorldPack.packName)")
        let block = pack.appendingPathComponent("Earth nav data/+40+000")
        try fm.createDirectory(at: block, withIntermediateDirectories: true)
        // Two placeholders (the engine's bytes carry the agent) and one tile.
        var placeholder = Data("XPLNEDSF".utf8)
        placeholder.append(Data("sim/creation_agent\u{0}\(O4WorldPack.placeholderAgent)\u{0}".utf8))
        try placeholder.write(to: block.appendingPathComponent("+45+008.dsf"))
        try placeholder.write(to: block.appendingPathComponent("+46+007.dsf"))
        try Data(contentsOf: Self.fixtures.appendingPathComponent("mesh_dsf/full_ortho.dsf"))
            .write(to: block.appendingPathComponent("+45+007.dsf"))
        let textures = pack.appendingPathComponent("textures/+45+007")
        let terrain = pack.appendingPathComponent("terrain/+45+007")
        try fm.createDirectory(at: textures, withIntermediateDirectories: true)
        try fm.createDirectory(at: terrain, withIntermediateDirectories: true)
        for i in 0..<24 {
            try Data().write(to: textures.appendingPathComponent("\(23000 + i * 16)_10432_BI16.dds"))
            try Data().write(to: terrain.appendingPathComponent("\(23000 + i * 16)_10432_BI16.ter"))
        }
        #expect(O4WorldPack.isPlaceholder(block.appendingPathComponent("+45+008.dsf"), size: nil))
        #expect(!O4WorldPack.isPlaceholder(block.appendingPathComponent("+45+007.dsf"), size: 99_999))

        let scan = InstallationScanner(root: root).scan(cache: [:])
        let found = try #require(scan.installation.packs.first { $0.name == O4WorldPack.packName })
        #expect(found.tiles == ["+45+007"])
        #expect(found.kind == .ortho)
    }
}
