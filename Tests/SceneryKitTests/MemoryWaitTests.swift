import XCTest
@testable import SceneryKit

/// The `MemoryWait` event (#2101) read off the wire.
final class MemoryWaitTests: XCTestCase {
    func testParsesTheHeldStep() {
        let object: [String: Any] = [
            "event": "MemoryWait", "lat": 47, "lon": 12, "step_key": "vector",
            "needed_gb": 57.4, "free_gb": 30.2, "reason": "machine",
            "message": "Waiting for memory: needs about 57 GB, 30 GB free.",
            "resolved": false, "attempt": 2,
        ]
        guard case .memoryWait(let wait)? = O4Event.parse(object: object) else {
            return XCTFail("not a memoryWait")
        }
        XCTAssertEqual(wait.lat, 47)
        XCTAssertEqual(wait.lon, 12)
        XCTAssertEqual(wait.stepKey, "vector")
        XCTAssertEqual(wait.neededGB, 57.4)
        XCTAssertEqual(wait.freeGB, 30.2)
        XCTAssertEqual(wait.reason, "machine")
        XCTAssertTrue(wait.message.hasPrefix("Waiting for memory"))
        XCTAssertFalse(wait.resolved)
        XCTAssertEqual(wait.attempt, 2)
    }

    func testAResolvedWaitCarriesNoWords() {
        guard case .memoryWait(let wait)? = O4Event.parse(object: [
            "event": "MemoryWait", "lat": 1, "lon": 2, "step_key": "mesh",
            "resolved": true]) else {
            return XCTFail("not a memoryWait")
        }
        XCTAssertTrue(wait.resolved)
        XCTAssertEqual(wait.message, "")
    }
}
