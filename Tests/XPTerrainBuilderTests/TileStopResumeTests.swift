import XCTest
import SceneryKit
@testable import XPTerrainBuilder

/// Per-tile stop / resume / re-queue during a running build (#1326) and the
/// patch box's "Rebuild tile" during one (#1322): the pure rules
/// `BuildModel` applies to every engine event and every enqueue. The Qt
/// twins are `Ortho4XP/tests/test_qt_stop_resume.py`.
@MainActor
final class TileStopResumeTests: XCTestCase {
    private typealias Model = BuildModel
    private let tile = BuildModel.TileCoord(lat: 48, lon: -6)
    private let other = BuildModel.TileCoord(lat: 49, lon: -6)

    private func row(_ state: TileProgress.State, _ label: String = "",
                     _ percent: Double = 0) -> TileProgress {
        TileProgress(state: state, label: label.isEmpty ? state.rawValue : label,
                     percent: percent)
    }

    // MARK: Telling a stopped attempt from the one that re-queued the tile

    func testUnconfirmedStopMakesEveryEventTheStoppedAttempts() {
        XCTAssertTrue(Model.isStoppedAttempt(0, staleThrough: nil, stopPending: true))
        XCTAssertTrue(Model.isStoppedAttempt(5, staleThrough: 2, stopPending: true))
    }

    func testAfterTheStopTheAttemptNumberDecides() {
        XCTAssertTrue(Model.isStoppedAttempt(2, staleThrough: 2, stopPending: false))
        XCTAssertTrue(Model.isStoppedAttempt(1, staleThrough: 2, stopPending: false))
        XCTAssertFalse(Model.isStoppedAttempt(3, staleThrough: 2, stopPending: false))
        XCTAssertFalse(Model.isStoppedAttempt(0, staleThrough: 2, stopPending: false))
        XCTAssertFalse(Model.isStoppedAttempt(4, staleThrough: nil, stopPending: false))
    }

    func testOldAttemptIsDroppedAndNewAttemptShownOverARequeuedRow() {
        let queued = row(.queued)
        let progress = row(.active, "mesh", 61)
        // The stopped attempt's straggler does not move the re-queued row …
        XCTAssertNil(Model.resolving(progress, over: queued, stoppedAttempt: true))
        // … the new attempt's progress does.
        XCTAssertEqual(Model.resolving(progress, over: queued, stoppedAttempt: false), progress)
    }

    func testAStoppedAttemptStillLandsAsATerminal() {
        let done = row(.done, "", 100)
        XCTAssertEqual(Model.resolving(done, over: row(.queued), stoppedAttempt: true), done)
        XCTAssertEqual(Model.resolving(done, over: row(.stopped), stoppedAttempt: true), done)
    }

    func testTheStopNoticeStillGivesAStoppedRowItsDetail() {
        var notice = row(.queued, "stopped")
        notice.detail = "What the tile is left with."
        let kept = Model.resolving(notice, over: row(.stopped, "stopped", 42), stoppedAttempt: true)
        XCTAssertEqual(kept?.state, .stopped)
        XCTAssertEqual(kept?.percent, 42)
        XCTAssertEqual(kept?.detail, "What the tile is left with.")
        // Over a row already re-queued it changes nothing.
        XCTAssertNil(Model.resolving(notice, over: row(.queued), stoppedAttempt: true))
    }

    // MARK: Clocks

    func testAQueuedRowRunsNoClockAndAStoppedOneStaysFrozen() {
        let engine = O4TileClock(lat: 48, lon: -6, elapsedSeconds: 7200,
                                 remainingSeconds: 300, finished: false)
        let frozen = O4TileClock(lat: 48, lon: -6, elapsedSeconds: 30,
                                 remainingSeconds: nil, finished: true)
        XCTAssertEqual(Model.displayedClock(engine, state: .queued, previous: nil),
                       O4TileClock(lat: 48, lon: -6, elapsedSeconds: 0,
                                   remainingSeconds: 300, finished: false))
        XCTAssertEqual(Model.displayedClock(engine, state: .stopped, previous: frozen), frozen)
        XCTAssertNil(Model.displayedClock(engine, state: .stopped, previous: nil))
        XCTAssertEqual(Model.displayedClock(engine, state: .active, previous: nil), engine)
    }

    // MARK: Resume / Queue while building

    func testResumeWhileBuildingIsSentAtOnceUnlessItsStopIsUnconfirmed() {
        let sent = Model.splitHeld([tile, other], stopPending: [])
        XCTAssertEqual(sent.send, [tile, other])
        XCTAssertEqual(sent.hold, [])
        let held = Model.splitHeld([tile, other], stopPending: [tile])
        XCTAssertEqual(held.send, [other])
        XCTAssertEqual(held.hold, [tile])
    }

    func testAHeldTileIsNotInTheRunSoQueueStaysUsable() {
        XCTAssertTrue(Model.isInRun(.queued, held: false))
        XCTAssertFalse(Model.isInRun(.queued, held: true))
        XCTAssertTrue(Model.isInRun(.active, held: false))
        XCTAssertTrue(Model.isInRun(.indeterminate, held: false))
        XCTAssertFalse(Model.isInRun(.stopped, held: false))
        XCTAssertFalse(Model.isInRun(.done, held: false))
        XCTAssertFalse(Model.isInRun(nil, held: false))
    }

    // MARK: Rebuild tile (#1322)

    func testRebuildStartsARunQueuesIntoOneOrSaysAlreadyInRun() {
        XCTAssertEqual(Model.rebuildDecision(isBuilding: false, row: nil, held: false), .startRun)
        XCTAssertEqual(Model.rebuildDecision(isBuilding: true, row: nil, held: false), .queueIntoRun)
        XCTAssertEqual(Model.rebuildDecision(isBuilding: true, row: .done, held: false), .queueIntoRun)
        XCTAssertEqual(Model.rebuildDecision(isBuilding: true, row: .stopped, held: false), .queueIntoRun)
        XCTAssertEqual(Model.rebuildDecision(isBuilding: true, row: .queued, held: false), .alreadyInRun)
        XCTAssertEqual(Model.rebuildDecision(isBuilding: true, row: .active, held: false), .alreadyInRun)
        XCTAssertEqual(Model.rebuildDecision(isBuilding: true, row: .queued, held: true), .queueIntoRun)
    }
}
