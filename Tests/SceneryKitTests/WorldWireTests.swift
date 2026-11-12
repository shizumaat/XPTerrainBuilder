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

    /// `world_migrate`'s `WorldReady` (the shared fixture, a dry run of
    /// the owner's Custom Scenery; `test_world_migrate.py` holds its keys
    /// to the engine's) decodes to the sentence and the tiles to move.
    @Test func worldMigrateDecodesThePythonResult() throws {
        let url = Self.fixtures.appendingPathComponent("world/world_migrate_ready.json")
        let object = try #require(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        let result = try OrthoEngineClient.decodeWorldMigrateReady(O4JSON.from(object)).get()
        #expect(result.action == "dry_run" && result.toMove == 2590)
        #expect(result.summary.hasPrefix("2,590 tiles can move") && result.failed.isEmpty)
        #expect(!result.stopped)
        // Convert's three choices (owner 2026-11-11T15:32Z; the fixture's
        // choice figures are illustrative, its lines the engine's
        // `world_retire.choice_line` of them).
        #expect(result.choices.map(\.id) == O4WorldMigrateText.choices.map(\.id))
        #expect(result.toMove(choice: "keep_custom") == 2592)
        #expect(result.choices[2].line.hasSuffix("No other drive is needed afterwards."))
    }

    /// `WorldMigrateProgress` (owner 2026-11-11T15:32Z: a bar and a count
    /// while Convert runs; `test_world_migrate.py` holds the fixture to the
    /// engine's wire) decodes, and the count reads as the Qt window's.
    @Test func worldMigrateProgressDecodesThePythonEvent() throws {
        let url = Self.fixtures.appendingPathComponent("world/world_migrate_progress_event.json")
        let object = try #require(
            JSONSerialization.jsonObject(with: Data(contentsOf: url)) as? [String: Any])
        guard case .worldMigrateProgress(let count) = try #require(O4Event.parse(object: object)) else {
            Issue.record("WorldMigrateProgress did not decode as .worldMigrateProgress")
            return
        }
        #expect(count == O4WorldMigrateProgress(phase: "measure", done: 3, total: 12,
                                                tile: "zOrtho4XP_+45+007"))
        // The same line `test_world_onboard.py` asserts for the Qt window.
        #expect(O4WorldMigrateText.progressLine(count)
                == "Measuring: 3 of 12 tiles · zOrtho4XP_+45+007")
        let moving = O4WorldMigrateProgress(phase: "move", done: 1, total: 4, tile: "")
        #expect(O4WorldMigrateText.progressLine(moving) == "Converting: 1 of 4 tiles")
        #expect(O4WorldMigrateText.stop == "Cancel")
    }

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
        #expect(status.tiles == ["placeholder": 3, "drape": 1, "full": 2, "staged": 1])
        #expect(status.queue == 2 && status.slots == 1 && status.bytes == 1234)
        #expect(status.loaded == ["+53-063"])
        #expect(status.building == [.init(tile: "+53-065", kind: "drape", step: "building",
                                          remainingS: 41)])
        #expect(status.lastSwap == ["+53-064", "drape", "2026-11-10T15:02:24Z"])
        // Build-ahead's tiles: the Fly map's cells in free flight (11j).
        #expect(status.jobs.map { [$0.lat, $0.lon] } == [[53, -65], [53, -64]])
        #expect(status.jobs.map(\.state) == ["building", "swapped"])
        #expect(FlyLayers.corridorCells(plan: nil, corridorKm: 20,
                                        jobs: FlyLayers.mapJobs(flight: [], planned: false,
                                                                ahead: status.jobs))
                == [FlyCell(lat: 53, lon: -65, key: "building"),
                    FlyCell(lat: 53, lon: -64, key: "quick")])
        // Beside a flight (#2019): the flight's tile wins, build-ahead's
        // other tiles around the aircraft are drawn too.
        let flight = [O4FlightStatus.Job(lat: 53, lon: -64, role: "enroute", kind: "drape",
                                         state: "queued", remainingSeconds: nil,
                                         marginSeconds: nil)]
        let both = FlyLayers.mapJobs(flight: flight, planned: true, ahead: status.jobs)
        #expect(both.map { [$0.lat, $0.lon] } == [[53, -64], [53, -65]])
        #expect(both.map(\.state) == ["queued", "building"])
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
