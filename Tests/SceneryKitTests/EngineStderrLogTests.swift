import Testing
import Foundation
@testable import SceneryKit

/// One engine-stderr.log per build run, five previous runs kept — the same
/// cases as the Qt twin's `Ortho4XP/tests/test_engine_stderr_log.py`.
@Suite struct EngineStderrLogTests {

    private func scratch() -> URL {
        FileManager.default.temporaryDirectory
            .appendingPathComponent("engine-stderr-log-tests-\(UUID().uuidString)", isDirectory: true)
            .appendingPathComponent("logs", isDirectory: true)
    }

    private func text(_ dir: URL, _ name: String) -> String {
        (try? String(contentsOf: dir.appendingPathComponent(name), encoding: .utf8)) ?? ""
    }

    private func names(_ dir: URL) -> [String] {
        ((try? FileManager.default.contentsOfDirectory(atPath: dir.path)) ?? []).sorted()
    }

    @Test func linesBetweenRunsLandUnderASessionHeader() {
        let dir = scratch()
        EngineStderrLog(directory: dir).append("first")
        EngineStderrLog(directory: dir).append("second")
        let body = text(dir, "engine-stderr.log")
        #expect(body.hasPrefix("=== engine session "))
        #expect(body.contains("first\n") && body.contains("second\n"))
        #expect(body.components(separatedBy: "=== engine session ").count == 3)
    }

    @Test func aRunStartsAFreshFileUnderTheRunHeader() {
        let dir = scratch()
        let log = EngineStderrLog(directory: dir)
        log.append("start-up warning")
        log.startRun(appVersion: "1.0.378", engineVersion: "1.50.1815",
                     tiles: ["+30+031", "+25+051"])
        log.append("RuntimeWarning: from this run")
        let lines = text(dir, "engine-stderr.log").components(separatedBy: "\n")
        #expect(lines[0].hasPrefix("=== engine run "))
        #expect(lines[0].hasSuffix("=== app 1.0.378 | engine 1.50.1815 | 2 tiles: +30+031 +25+051"))
        #expect(lines[1] == "RuntimeWarning: from this run")
        #expect(text(dir, "engine-stderr.1.log").contains("start-up warning"))
    }

    @Test func theHeaderTextIsTheQtTwins() {
        #expect(EngineStderrLog.runHeader(appVersion: "1.0.378", engineVersion: "",
                                          tiles: ["+38-009"], stamp: "T")
                == "=== engine run T === app 1.0.378 | engine unknown | 1 tile: +38-009")
        #expect(EngineStderrLog.queuedLine(tiles: ["+38-009", "+38-010"], stamp: "T")
                == "=== queued into this run T === 2 tiles: +38-009 +38-010")
    }

    @Test func fiveRunsAreKeptAndTheOldestIsDropped() {
        let dir = scratch()
        let log = EngineStderrLog(directory: dir)
        for run in 1...8 {
            log.startRun(appVersion: "a", engineVersion: "e", tiles: ["+00+000"])
            log.append("run \(run)")
        }
        #expect(names(dir) == ["engine-stderr.1.log", "engine-stderr.2.log",
                               "engine-stderr.3.log", "engine-stderr.4.log",
                               "engine-stderr.5.log", "engine-stderr.log"])
        #expect(text(dir, "engine-stderr.log").contains("run 8\n"))
        for index in 1...5 {
            #expect(text(dir, "engine-stderr.\(index).log").contains("run \(8 - index)\n"))
        }
    }

    @Test func theSizeGuardShiftsInsideARunAndTheRunContinues() {
        let dir = scratch()
        let log = EngineStderrLog(directory: dir, maxBytes: 200)
        log.startRun(appVersion: "a", engineVersion: "e", tiles: ["+00+000"])
        for _ in 0..<40 { log.append(String(repeating: "x", count: 40)) }
        log.append("after the guard")
        let live = text(dir, "engine-stderr.log")
        #expect(live.contains("=== engine run continued "))
        #expect(live.contains("engine-stderr.1.log"))
        #expect(live.utf8.count < 600)
        #expect(names(dir).count == 6, "a runaway run is bounded to the kept files")
    }

    @Test func theCapAndTheCountAreTheQtTwins() {
        #expect(EngineStderrLog.maxBytes == 20 * 1024 * 1024)
        #expect(EngineStderrLog.keptRuns == 5)
    }

    @Test func anUnwritableLogNeverThrowsAndTheNextRunTriesAgain() throws {
        let dir = scratch()
        let parent = dir.deletingLastPathComponent()
        try FileManager.default.createDirectory(at: parent, withIntermediateDirectories: true)
        // `logs` is a FILE: the directory cannot be created.
        try Data("not a directory".utf8).write(to: dir)
        let log = EngineStderrLog(directory: dir)
        log.append("dropped")
        log.startRun(appVersion: "a", engineVersion: "e", tiles: [])
        log.append("dropped too")
        try FileManager.default.removeItem(at: dir)
        log.append("still disabled for this run")
        #expect(names(dir).isEmpty)
        log.startRun(appVersion: "a", engineVersion: "e", tiles: ["+00+000"])
        log.append("persisted again")
        #expect(text(dir, "engine-stderr.log").contains("persisted again\n"))
    }
}
