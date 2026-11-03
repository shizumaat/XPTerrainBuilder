import XCTest
@testable import SceneryKit

/// The `SlowStep` event (protocol 1.26, #1351) read off the wire.
final class SlowStepTests: XCTestCase {
    func testParsesTheEnginesWordsAndAnswers() {
        let object: [String: Any] = [
            "event": "SlowStep", "lat": 56, "lon": -4, "step_key": "vector",
            "title": "Tile +56-004: the vector data step is slow",
            "message": "Downloading…", "reason": "remote_fine_elevation",
            "options": ["continue", "coarser", "cancel"],
            "option_labels": ["Continue", "Use coarser data", "Cancel this tile"],
            "eta_seconds": 600.0, "resolved": false,
        ]
        guard case .slowStep(let step)? = O4Event.parse(object: object) else {
            return XCTFail("not a slowStep")
        }
        XCTAssertEqual(step.id, "56|-4|vector")
        XCTAssertEqual(step.buttons.map(\.label),
                       ["Continue", "Use coarser data", "Cancel this tile"])
        XCTAssertEqual(step.buttons.map(\.choice), ["continue", "coarser", "cancel"])
        XCTAssertEqual(step.etaSeconds, 600.0)
        XCTAssertFalse(step.resolved)
    }

    func testAResolvedEventHasNoEta() {
        guard case .slowStep(let step)? = O4Event.parse(object: [
            "event": "SlowStep", "lat": 1, "lon": 2, "step_key": "mesh",
            "eta_seconds": NSNull(), "resolved": true]) else {
            return XCTFail("not a slowStep")
        }
        XCTAssertTrue(step.resolved)
        XCTAssertNil(step.etaSeconds)
        XCTAssertTrue(step.buttons.isEmpty)
    }
}
