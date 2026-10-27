import XCTest
@testable import SceneryKit

/// The Queue press line (1.0.433: Queue went grey while a 100-airport tile
/// solved): during a run a press is taken at once and asks its own
/// boundary question in turn; idle, a second press is still refused.
final class BoundaryPressQueueTests: XCTestCase {
    func testDuringARunAPressIsTakenWhileAPreflightIsInFlight() {
        XCTAssertTrue(O4BoundaryPressQueue<Int>.acceptsPress(isPreflighting: true, isBuilding: true))
        XCTAssertTrue(O4BoundaryPressQueue<Int>.acceptsPress(isPreflighting: false, isBuilding: false))
        XCTAssertFalse(O4BoundaryPressQueue<Int>.acceptsPress(isPreflighting: true, isBuilding: false))
    }

    func testPressesAskInPressOrderOneAtATime() {
        var queue = O4BoundaryPressQueue<String>()
        XCTAssertEqual(queue.submit("first"), "first")
        XCTAssertTrue(queue.isPreflighting)
        XCTAssertNil(queue.submit("second"))
        XCTAssertNil(queue.submit("third"))
        XCTAssertEqual(queue.waitingCount, 2)
        XCTAssertEqual(queue.settle(), "second")
        XCTAssertTrue(queue.isPreflighting)
        XCTAssertEqual(queue.settle(), "third")
        XCTAssertNil(queue.settle())
        XCTAssertFalse(queue.isPreflighting)
        XCTAssertEqual(queue.submit("later"), "later")
    }
}
