import Testing
import Foundation
@testable import SceneryKit
@testable import XPTerrainBuilder

/// Convert existing tiles' run (owner 2026-11-11T15:32Z): the count shows
/// only while a step runs, Cancel is offered for the measure and the move,
/// and the onboarding's Done waits for the step's result line. The Qt
/// twin is `Ortho4XP/tests/test_world_onboard.py`.
@MainActor
@Suite struct WorldMigrateRunTests {
    @Test func theMeasureCountsAndHoldsDone() {
        let run = WorldMigrateRun()
        #expect(WorldOnboardDone.enabled(moving: false, run: run))   // Not now stands
        run.begin(.measure)
        #expect(run.isRunning && run.canCancel && run.fraction == nil)
        #expect(!WorldOnboardDone.enabled(moving: true, run: run))
        run.show(O4WorldMigrateProgress(phase: "measure", done: 3, total: 12,
                                        tile: "zOrtho4XP_+45+007"))
        #expect(run.fraction == 0.25)
        #expect(run.status == "Measuring: 3 of 12 tiles · zOrtho4XP_+45+007")
        #expect(!WorldOnboardDone.enabled(moving: true, run: run))
        let result = O4WorldMigrateResult(action: "dry_run", summary: "3 tiles can move.",
                                          failed: [], stopped: false, toMove: 3)
        run.finish(.success(result))
        #expect(!run.isRunning && run.hasResult && run.status == "3 tiles can move.")
        #expect(run.measured == result && run.progress == nil)
        #expect(WorldOnboardDone.enabled(moving: true, run: run))
    }

    /// The three choices (owner 2026-11-11T15:32Z): each shows its hint
    /// until a measure, then the engine's line; Convert counts the chosen
    /// choice's tiles (kept + dynamic).
    @Test func eachChoiceShowsItsHintThenTheMeasuredLine() {
        let run = WorldMigrateRun()
        #expect(run.choice == "keep_all" && run.toMove == 0)
        #expect(run.line(for: "dynamic") == O4WorldMigrateText.dynamicHint)
        run.begin(.measure)
        let choices = [O4WorldMigrateChoice(id: "keep_all", line: "Keeps 2.", kept: 2, dynamic: 0),
                       O4WorldMigrateChoice(id: "dynamic", line: "Makes all 3.", kept: 0, dynamic: 3)]
        run.finish(.success(O4WorldMigrateResult(action: "dry_run", summary: "", failed: [],
                                                 stopped: false, toMove: 2, choices: choices)))
        #expect(run.line(for: "dynamic") == "Makes all 3." && run.toMove == 2)
        run.choice = "dynamic"
        #expect(run.toMove == 3)
        #expect(run.line(for: "keep_custom") == O4WorldMigrateText.keepCustomHint)
    }

    @Test func aCancelledMeasureEndsWithItsSentence() {
        let run = WorldMigrateRun()
        run.begin(.measure)
        run.markCancelling()
        #expect(run.cancelling)
        run.finish(.failure(O4CommandError("Measuring cancelled: nothing was moved.")))
        #expect(!run.isRunning && run.hasResult && run.measured == nil && !run.cancelling)
        #expect(run.status.contains("cancelled"))
        #expect(WorldOnboardDone.enabled(moving: true, run: run))
    }

    @Test func countsOutsideARunAreIgnoredAndUndoHasNoCancel() {
        let run = WorldMigrateRun()
        run.show(O4WorldMigrateProgress(phase: "move", done: 1, total: 4, tile: ""))
        #expect(run.progress == nil && run.status.isEmpty)
        run.begin(.undo)
        #expect(run.isRunning && !run.canCancel)
    }
}
