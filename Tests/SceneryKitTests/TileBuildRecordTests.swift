import Testing
import Foundation
@testable import SceneryKit

/// The build record, console prefix, date ranges and "Built by" wording —
/// the same cases as the engine twin's `Ortho4XP/tests/test_tile_build_log.py`,
/// read from the shared fixture `Ortho4XP/tests/fixtures/build_record_v1.json`.
@Suite struct TileBuildRecordTests {

    static let fixture: URL = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
        .appendingPathComponent("Ortho4XP/tests/fixtures/build_record_v1.json")

    private func scratchBuildDir() throws -> URL {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("tile-build-record-\(UUID().uuidString)", isDirectory: true)
        let logs = dir.appendingPathComponent(TileBuildLogs.directoryName, isDirectory: true)
        try FileManager.default.createDirectory(at: logs, withIntermediateDirectories: true)
        try FileManager.default.copyItem(
            at: Self.fixture, to: logs.appendingPathComponent(TileBuildLogs.recordName))
        try "line one\nline two\n".write(
            to: logs.appendingPathComponent("20261026T170000Z_+47-123.log"),
            atomically: true, encoding: .utf8)
        return dir
    }

    @Test func readsTheEnginesRecordFile() throws {
        let dir = try scratchBuildDir()
        let records = TileBuildLogs.records(buildDir: dir.path, tile: "+47-123")
        #expect(records.count == 1)
        let record = try #require(records.first)
        #expect(record.outcome == "warnings" && record.warnings == 1)
        #expect(record.end > record.start && record.duration == 1834.2)
        #expect(record.builder?.appVersion == "1.0.430")
        #expect(record.builtBy == "XPTerrainBuilder 1.0.430, engine 1.50.1880")
        #expect(TileBuildLogs.logText(buildDir: dir.path, name: record.log)
                == "line one\nline two\n")
        #expect(TileBuildLogs.records(buildDir: dir.path, tile: "+48-123").isEmpty)
    }

    @Test func decodesTheScansLastBuild() throws {
        let data = try Data(contentsOf: Self.fixture)
        let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        let row = try #require((object?["builds"] as? [Any])?.first)
        let record = try #require(TileBuildRecord(json: O4JSON.from(row)))
        #expect(record.tile == "+47-123" && record.log == "20261026T170000Z_+47-123.log")
        let info = try #require(O4TileInfo(json: .object([
            "lat": .int(47), "lon": .int(-123), "last_build": O4JSON.from(row),
            "built_by": .string(record.builtBy),
        ])))
        #expect(info.lastBuild == record)
        #expect(info.builtBy == "XPTerrainBuilder 1.0.430, engine 1.50.1880")
        let older = try #require(O4TileInfo(json: .object(["lat": .int(1), "lon": .int(2)])))
        #expect(older.lastBuild == nil && older.builtBy == nil)
    }

    @Test func builtByFromTheDSFAgent() {
        #expect(TileBuildLogs.builtByText(record: nil, agent: "Ortho4XP")
                == "Ortho4XP (older build, version unknown)")
        #expect(TileBuildLogs.builtByText(record: nil, agent: "WorldEditor 2.5") == "WorldEditor 2.5")
        #expect(TileBuildLogs.builtByText(record: nil, agent: nil) == "")
    }

    @Test func tileOfLine() {
        let cases: [(line: String, tile: String?, text: String)] = [
            ("[+47-123] Step 1 done", "+47-123", "Step 1 done"),
            ("[-01+005] x", "-01+005", "x"),
            ("[worker 2] boom", nil, "[worker 2] boom"),
            ("=== Run complete ===", nil, "=== Run complete ==="),
        ]
        for c in cases {
            let parsed = TileBuildLogs.tileOfLine(c.line)
            #expect(parsed.tile == c.tile, "\(c.line)")
            #expect(parsed.text == c.text, "\(c.line)")
        }
    }

    @Test func dateRanges() {
        let now = Date(timeIntervalSince1970: 1_800_000_000)
        let t = now.timeIntervalSince1970
        #expect(BuildDateRange.all.contains(nil, now: now))
        #expect(!BuildDateRange.last7Days.contains(nil, now: now))
        #expect(BuildDateRange.last48Hours.contains(t - 47 * 3600, now: now))
        #expect(!BuildDateRange.last48Hours.contains(t - 49 * 3600, now: now))
        #expect(BuildDateRange.last7Days.contains(t - 6 * 86400, now: now))
        #expect(!BuildDateRange.last30Days.contains(t - 31 * 86400, now: now))
        #expect(BuildDateRange.today.contains(t, now: now))
        #expect(!BuildDateRange.today.contains(t - 86400, now: now))
        #expect(BuildDateRange.allCases.map(\.rawValue) == ["today", "48h", "7d", "30d", "all"])
    }

    @Test func logEventCarriesItsTile() {
        let event = O4Event.parse(object: [
            "event": "Log", "level": "warning", "text": "loud", "tile": [47, -123],
        ])
        #expect(event == .log(level: "warning", text: "loud", tile: "+47-123"))
        let runLevel = O4Event.parse(object: ["event": "Log", "level": "info", "text": "x"])
        #expect(runLevel == .log(level: "info", text: "x", tile: nil))
    }
}
