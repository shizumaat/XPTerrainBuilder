import Testing
import Foundation
@testable import SceneryKit

/// The About box's build triple (docs/BETA-PLAN-20260916.md §1 B3): app
/// version, engine version, commit. A beta report quoting only "1.0.347"
/// identifies no build, and a triple that GUESSES a commit is worse than one
/// that admits it does not have one — so every unknown component reads "dev".
@Suite struct BuildTripleTests {

    @Test func readsTheStampsMakeAppWrites() {
        let triple = BuildTriple(app: "1.0.347",
                                 infoDictionary: ["XPTBEngineVersion": "1.50.1793",
                                                  "XPTBCommitSHA": "5883949fdeadbeefcafe"])
        #expect(triple.app == "1.0.347")
        #expect(triple.engine == "1.50.1793")
        #expect(triple.commit == "5883949fdeadbeefcafe")
    }

    @Test func anUnstampedDevTreeSaysDevRatherThanGuessing() {
        let triple = BuildTriple(app: "1.0.347", infoDictionary: nil)
        #expect(triple.engine == "dev")
        #expect(triple.commit == "dev")
        #expect(triple.shortCommit == "dev")
    }

    @Test func blankAndPlaceholderStampsAreNotShown() {
        let triple = BuildTriple(app: "1.0.347",
                                 infoDictionary: ["XPTBEngineVersion": "  ",
                                                  "XPTBCommitSHA": "unknown"])
        #expect(triple.engine == "dev")
        #expect(triple.commit == "dev")
    }

    /// `swift run` has no stamp but does have a live engine handshake.
    @Test func theLiveEngineVersionFillsInForAnUnstampedBundle() {
        let triple = BuildTriple(app: "1.0.347", infoDictionary: nil,
                                 engineFallback: "1.50.1793")
        #expect(triple.engine == "1.50.1793")
        #expect(triple.commit == "dev")
    }

    @Test func theStampWinsOverTheLiveEngine() {
        // A release build reports the engine it SHIPPED, before or after one
        // is started, and whatever a user pointed the app at.
        let triple = BuildTriple(app: "1.0.347",
                                 infoDictionary: ["XPTBEngineVersion": "1.50.1793"],
                                 engineFallback: "1.50.9")
        #expect(triple.engine == "1.50.1793")
    }

    @Test func commitIsShownShortButKeepsTheDirtyMarker() {
        #expect(BuildTriple(app: "a", engine: "b", commit: "5883949fdeadbeef")
            .shortCommit == "5883949")
        #expect(BuildTriple(app: "a", engine: "b", commit: "5883949fdeadbeef-dirty")
            .shortCommit == "5883949-dirty")
        #expect(BuildTriple(app: "a", engine: "b", commit: "dev").shortCommit == "dev")
    }

    @Test func everyComponentIsLabelledOnItsOwnLine() {
        let lines = BuildTriple(app: "1.0.347", engine: "1.50.1793",
                                commit: "5883949fdeadbeef").displayLines
        #expect(lines.count == 3)
        #expect(lines[0] == "App version: 1.0.347")
        #expect(lines[1] == "Engine version: 1.50.1793")
        #expect(lines[2] == "Commit: 5883949")
    }
}
