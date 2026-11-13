import XCTest
@testable import SceneryKit

/// #2055: a launch scan's ~10 Hz batches reach the screen at most once per
/// second (each publication re-renders the whole window). Twin of
/// `Ortho4XP/tests/test_scan_stream_throttle.py`: both feed
/// `Ortho4XP/tests/fixtures/scan_stream_throttle_cases.json` to a fresh
/// throttle, so both apps publish a streaming scan on the same rule.
final class ScanStreamThrottleTests: XCTestCase {
    func testTheSharedCases() throws {
        let url = URL(fileURLWithPath: #filePath)
            .deletingLastPathComponent().deletingLastPathComponent().deletingLastPathComponent()
            .appendingPathComponent("Ortho4XP/tests/fixtures/scan_stream_throttle_cases.json")
        let root = try XCTUnwrap(JSONSerialization.jsonObject(with: Data(contentsOf: url))
            as? [String: Any])
        let cases = try XCTUnwrap(root["cases"] as? [[String: Any]])
        XCTAssertFalse(cases.isEmpty)
        for test in cases {
            let name = test["name"] as? String ?? ""
            var throttle = ScanStreamThrottle(interval: test["interval"] as? Double ?? 1.0)
            for step in test["steps"] as? [[String: Any]] ?? [] {
                if step["reset"] as? Bool == true {
                    throttle.reset()
                } else {
                    let at = try XCTUnwrap(step["at"] as? Double)
                    XCTAssertEqual(throttle.shouldPublish(now: at), step["publish"] as? Bool, name)
                }
            }
        }
    }

    func testA25SecondScanAt10HzPublishesAbout25Times() {
        var throttle = ScanStreamThrottle()
        let published = (0..<250).map { Double($0) / 10 }.filter { throttle.shouldPublish(now: $0) }
        XCTAssertEqual(published.first, 0.0)
        XCTAssertTrue((24...26).contains(published.count), "\(published.count)")
    }
}
