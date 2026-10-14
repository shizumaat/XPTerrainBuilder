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
            "notes": [entry("elevation_substituted",
                            what: "Tile +45-123 was built with stand-in elevation for cell +45-124.")],
        ]
        guard case .buildDone(let lat, let lon, let ok, _, let failures, let warnings,
                              let unpatched, let notes)?
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
        #expect(notes.map(\.code) == ["elevation_substituted"])
        #expect(notes[0].consoleLines(isWarning: false, isNote: true)[0].hasPrefix("Note: Tile"))
    }

    @Test func anOlderEngineDecodesToNoMessages() throws {
        let object: [String: Any] = ["event": "BuildDone", "lat": 1, "lon": 2,
                                     "ok": false, "error": "the mesh step failed"]
        #expect(O4Event.parse(object: object)
                == .buildDone(lat: 1, lon: 2, ok: false, error: "the mesh step failed",
                              failures: [], warnings: [], unpatchedAirports: [],
                              notes: []))
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

/// One report per run, and only that run's tiles.
struct RunIssueLogTests {
    private func failed(_ key: String) -> O4TileIssues {
        O4TileIssues(tileKey: key, built: false,
                     failures: [O4TileFailure(code: "c", what: key, why: "", remedy: "")],
                     warnings: [])
    }

    @Test func aRunThatDiedLeavesNothingInTheNextRunsReport() throws {
        var log = O4RunIssueLog()
        log.begin()
        log.add(failed("+45-123"))
        // The engine died: no RunDone, no finish(). The next run begins.
        log.begin()
        log.add(failed("+47-123"))
        let finished = log.finish()
        let report = try #require(finished)
        #expect(report.tiles.map(\.tileKey) == ["+47-123"])
    }

    @Test func finishEmptiesTheLogAndNumbersTheReports() throws {
        var log = O4RunIssueLog()
        log.add(failed("+10+020"))
        let firstReport = log.finish()
        let first = try #require(firstReport)
        #expect(log.tiles.isEmpty)
        let clean = log.finish()
        #expect(clean == nil)                       // a clean run: no sheet
        log.add(O4TileIssues(
            tileKey: "+11+021", built: true, failures: [],
            warnings: [O4TileFailure(code: "w", what: "W", why: "", remedy: "")]))
        #expect(log.warnedCount == 1)
        // a tile with only a NOTE (stand-in elevation) is in the sheet too
        log.add(O4TileIssues(
            tileKey: "+12+022", built: true, failures: [], warnings: [],
            notes: [O4TileFailure(code: "n", what: "N", why: "", remedy: "")]))
        #expect(log.warnedCount == 2)
        let thirdReport = log.finish()
        let third = try #require(thirdReport)
        #expect(third.id != first.id)               // a new sheet, not the old one
    }
}

/// #668: the "Remove the link…" choice of the run report.
struct UnmountedLinkTests {
    private func entry(_ code: String, what: String) -> [String: Any] {
        ["code": code, "what": what, "why": "Why.", "remedy": "Do this.",
         "airports": [String](), "detail": "", "log_path": ""]
    }

    /// #668: a tile whose Custom Scenery folder is a link to a drive that
    /// is not mounted offers "Remove the link…" — and nothing else does.
    @Test func anUnmountedOutputLinkOffersRemoval() throws {
        var raw = entry("output_link_unmounted",
                        what: "Tile -12-078 was not built: its folder in Custom Scenery could not be reached.")
        raw["link"] = "/XP/Custom Scenery/zOrtho4XP_-12-078"
        let failures = O4TileFailure.parseList([raw, entry("disk_full", what: "Full.")])
        #expect(failures[0].link == "/XP/Custom Scenery/zOrtho4XP_-12-078")
        #expect(failures[0].offersLinkRemoval && !failures[1].offersLinkRemoval)
        let failed = O4TileIssues(tileKey: "-12-078", lat: -12, lon: -78, built: false,
                                  failures: failures, warnings: [])
        #expect(failed.removableLink == "/XP/Custom Scenery/zOrtho4XP_-12-078")
        // an older engine sends no link: no button
        let old = O4TileIssues(tileKey: "-12-078", built: false,
                               failures: O4TileFailure.parseList([entry(
                                   "output_link_unmounted", what: "W.")]),
                               warnings: [])
        #expect(old.removableLink == nil)
        // a READ pack on the drive is a warning on a built tile: no button
        var read = entry("airport_pack_unmounted", what: "Tile -12-078 was built, but …")
        read["link"] = ""
        let built = O4TileIssues(tileKey: "-12-078", built: true, failures: [],
                                 warnings: O4TileFailure.parseList([read]))
        #expect(built.removableLink == nil)
        #expect(O4TileFailureCopy.removeLinkButton
                == "Remove the link and build on this Mac's drive")
    }
}

/// #695: a fixable failure is asked AS SOON AS its tile fails — from the
/// tile's own BuildDone, before the run's RunDone — one choice at a time.
struct LinkFixQueueTests {
    private func failedTile(_ key: String, lat: Int, lon: Int, link: String) -> O4TileIssues {
        let raw: [String: Any] = [
            "code": "output_link_unmounted",
            "what": "Tile \(key) was not built: its folder in Custom Scenery could not be reached.",
            "why": "Why.", "remedy": "Do this.", "airports": [String](),
            "detail": "", "log_path": "", "link": link]
        return O4TileIssues(tileKey: key, lat: lat, lon: lon, built: false,
                            failures: O4TileFailure.parseList([raw]), warnings: [])
    }

    /// The tile's BuildDone event alone produces the pending choice.
    @Test func aMidRunBuildDoneProducesTheChoiceBeforeRunDone() throws {
        let object: [String: Any] = [
            "event": "BuildDone", "lat": -12, "lon": -78, "ok": false, "error": "E.",
            "failures": [["code": "output_link_unmounted", "what": "Tile -12-078 was not built.",
                          "why": "Why.", "remedy": "Do this.", "airports": [String](),
                          "detail": "", "log_path": "", "link": "/XP/CS/zOrtho4XP_-12-078"]]]
        guard case .buildDone(let lat, let lon, let ok, _, let failures, _, _, _)?
                = O4Event.parse(object: object) else {
            Issue.record("BuildDone did not decode"); return
        }
        var queue = O4LinkFixQueue()
        let offered = queue.offer(O4TileIssues(tileKey: "-12-078", lat: lat, lon: lon,
                                               built: ok, failures: failures, warnings: []))
        #expect(offered)
        let current = try #require(queue.current)
        #expect(current.link == "/XP/CS/zOrtho4XP_-12-078")
        #expect(current.title == "Tile -12-078 was not built.")
        #expect(current.message == "Why.\n\nDo this.")
    }

    /// Two fixable failures in one run: the second waits behind the first.
    @Test func twoFailuresQueueOneAtATime() {
        var queue = O4LinkFixQueue()
        let first = failedTile("-12-078", lat: -12, lon: -78, link: "/a")
        let second = failedTile("-13-078", lat: -13, lon: -78, link: "/b")
        queue.offer(first)
        queue.offer(second)
        let again = queue.offer(first)
        #expect(!again)                              // never asked twice at once
        #expect(queue.current?.link == "/a" && queue.waiting.count == 1)
        let a = queue.answer()
        #expect(a?.link == "/a" && queue.current?.link == "/b")
        let b = queue.answer()
        let none = queue.answer()
        #expect(b?.link == "/b" && queue.isIdle && none == nil)
        // a cause the user cannot fix here is never asked
        let full = O4TileIssues(tileKey: "-14-078", built: false,
                                failures: O4TileFailure.parseList([[
                                    "code": "disk_full", "what": "Full."]]), warnings: [])
        let unfixable = queue.offer(full)
        #expect(!unfixable && queue.isIdle)
    }

    /// A re-queued tile shows "fixed and re-queued" in the run's report
    /// and offers no button; a later failure of it arrives unmarked.
    @Test func reQueueMarksTheReport() throws {
        var log = O4RunIssueLog()
        log.add(failedTile("-12-078", lat: -12, lon: -78, link: "/a"))
        log.add(failedTile("-13-078", lat: -13, lon: -78, link: "/b"))
        log.markRequeued(tileKey: "-12-078")
        let finished = log.finish()
        var report = try #require(finished)
        #expect(report.tiles.count == 2)               // every failure still listed
        #expect(report.tiles[0].requeued && report.tiles[0].removableLink == nil)
        #expect(!report.tiles[1].requeued && report.tiles[1].removableLink == "/b")
        report.markRequeued(tileKey: "-13-078")        // fixed after the report was made
        #expect(report.tiles[1].requeued)
        #expect(O4TileFailureCopy.requeuedLine == "Fixed and re-queued.")
    }
}
