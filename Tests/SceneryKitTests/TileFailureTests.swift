import Testing
import Foundation
@testable import SceneryKit

/// A tile that was not built, or was built without an airport patch
/// (protocol 1.10; issue #562, owner RULINGS 2026-10-12a / #564). The JSON
/// keys are STRING LITERALS matched against
/// `Ortho4XP/src/O4_Tile_Failures.py` and `o4_engine/events.py`; these
/// tests are the drift alarm.
struct TileFailureTests {

    private func entry(_ code: String, what: String, airports: [String] = [],
                       detail: String = "") -> [String: Any] {
        ["code": code, "what": what, "why": "Why.", "remedy": "Do this.",
         "airports": airports, "detail": detail, "log_path": "/tmp/Ortho4XP.log"]
    }

    @Test func buildDoneDecodesFailuresAndWarnings() throws {
        let object: [String: Any] = [
            "event": "BuildDone", "lat": 45, "lon": -123, "ok": false,
            "error": "Tile +45-123 was not built: the disk is full.",
            "failures": [entry("disk_full",
                               what: "Tile +45-123 was not built: the disk is full.",
                               detail: "OSError: [Errno 28]")],
            "warnings": [entry("airport_geometry",
                               what: "Tile +45-123 was built, but airport AAAA could not be processed.",
                               airports: ["AAAA"])],
            "unpatched_airports": [entry("airport_geometry", what: "One.", airports: ["AAAA"])],
        ]
        guard case .buildDone(let lat, let lon, let ok, _, let failures, let warnings,
                              let unpatched)?
                = O4Event.parse(object: object) else {
            Issue.record("BuildDone did not decode")
            return
        }
        #expect(lat == 45 && lon == -123 && !ok)
        #expect(failures.count == 1 && warnings.count == 1)
        let failure = failures[0]
        #expect(failure.code == "disk_full")
        #expect(failure.what == "Tile +45-123 was not built: the disk is full.")
        #expect(failure.why == "Why." && failure.remedy == "Do this.")
        #expect(failure.detail == "OSError: [Errno 28]")
        #expect(failure.logPath == "/tmp/Ortho4XP.log")
        #expect(warnings[0].airports == ["AAAA"])
        #expect(unpatched.map(\.airports) == [["AAAA"]])
    }

    @Test func anOlderEngineDecodesToNoMessages() throws {
        let object: [String: Any] = ["event": "BuildDone", "lat": 1, "lon": 2,
                                     "ok": false, "error": "the mesh step failed"]
        #expect(O4Event.parse(object: object)
                == .buildDone(lat: 1, lon: 2, ok: false, error: "the mesh step failed",
                              failures: [], warnings: [], unpatchedAirports: []))
        let failed: [String: Any] = ["event": "AutoPatchFailed", "airport": "AAAA",
                                     "stage": "build", "error": "x", "lat": 1, "lon": 2]
        #expect(O4Event.parse(object: failed)
                == .autoPatchFailed(airport: "AAAA", stage: "build", error: "x",
                                    lat: 1, lon: 2, code: ""))
    }

    @Test func autoPatchFailedCarriesItsCode() throws {
        let failed: [String: Any] = ["event": "AutoPatchFailed", "airport": "AAAA",
                                     "stage": "verify", "error": "x", "lat": 1, "lon": 2,
                                     "code": "airport_verify"]
        #expect(O4Event.parse(object: failed)
                == .autoPatchFailed(airport: "AAAA", stage: "verify", error: "x",
                                    lat: 1, lon: 2, code: "airport_verify"))
    }

    @Test func malformedEntriesAreDropped() throws {
        #expect(O4TileFailure.parseList(nil).isEmpty)
        #expect(O4TileFailure.parseList("nonsense").isEmpty)
        #expect(O4TileFailure.parseList([["code": "x"]]).isEmpty)
    }

    @Test func theConsoleBlockKeepsTheDetailBelowTheMessage() throws {
        let failure = O4TileFailure(code: "c", what: "What.", why: "Why.", remedy: "Do.",
                                    detail: "line one\nline two")
        #expect(failure.consoleLines(isWarning: false)
                == ["*** What.", "    Why.", "    Do.",
                    "      detail: line one", "      detail: line two"])
        #expect(failure.consoleLines(isWarning: true)[0] == "Warning: What.")
        #expect(failure.message == "What.\nWhy.\nDo.")
    }

    @Test func oneReportPerRunOnlyWhenThereIsSomethingToSay() throws {
        let clean = O4TileIssues(tileKey: "+10+020", built: true, failures: [], warnings: [])
        #expect(O4RunIssues(id: 1, tiles: [clean]) == nil)
        let failed = O4TileIssues(
            tileKey: "+45-123", built: false,
            failures: [O4TileFailure(code: "c", what: "A.", why: "", remedy: "", detail: "d1")],
            warnings: [])
        let warned = O4TileIssues(
            tileKey: "+47-123", built: true, failures: [],
            warnings: [O4TileFailure(code: "w", what: "B.", why: "", remedy: "")])
        let issues = try #require(O4RunIssues(id: 2, tiles: [clean, failed, warned]))
        #expect(issues.title == "1 tile was not built, 1 built with warnings")
        #expect(issues.entries.map(\.code) == ["c", "w"])
        #expect(issues.detail == "A.\nd1")
    }
}

/// The report buttons are offered only to an engine that has the
/// `failure_report` command (protocol 1.10, issue #565).
struct FailureReportSupportTests {
    @Test func theButtonsNeedProtocolOneTen() throws {
        #expect(O4FailureReport.supported(protocolVersion: "1.10"))
        #expect(O4FailureReport.supported(protocolVersion: "1.11"))
        #expect(O4FailureReport.supported(protocolVersion: "2.0"))
        #expect(!O4FailureReport.supported(protocolVersion: "1.9"))
        #expect(!O4FailureReport.supported(protocolVersion: "1.1"))
        #expect(!O4FailureReport.supported(protocolVersion: ""))
    }

    @Test func anEntryGoesBackToTheEngineUnchanged() throws {
        let entry: [String: Any] = [
            "code": "disk_full", "what": "W", "why": "Y", "remedy": "R",
            "airports": ["AAAA"], "detail": "d", "log_path": "/l"]
        let failure = try #require(O4TileFailure.parseList([entry]).first)
        let wire = failure.wireObject
        for key in ["code", "what", "why", "remedy", "detail"] {
            #expect(wire[key] as? String == entry[key] as? String)
        }
        #expect(wire["airports"] as? [String] == ["AAAA"])
    }
}
