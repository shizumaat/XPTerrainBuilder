import Testing
import Foundation
@testable import SceneryKit

/// The tile info's imagery check (protocol 1.27, #1666): the
/// `ImageryFreshnessReady` decode. The words are the engine's
/// (`Ortho4XP/tests/test_imagery_freshness.py` pins the shared strings).
struct ImageryFreshnessTests {

    @Test func imageryFreshnessReadyDecodesTheAnswerOrTheError() throws {
        let event = O4JSON.from([
            "event": "ImageryFreshnessReady", "request": 3, "error": "",
            "result": ["status": "newer", "label": "Newer imagery available",
                       "detail": "2 of 16 sampled spots differ.", "sampled": 16,
                       "changed": 2, "checked_at": 1000.0] as [String: Any],
        ] as [String: Any])
        let answer = try OrthoEngineClient.decodeImageryFreshnessReady(event).get()
        #expect(answer.isNewer)
        #expect(answer.label == "Newer imagery available")
        let failed = O4JSON.from(["event": "ImageryFreshnessReady", "request": 3,
                                  "error": "boom", "result": NSNull()] as [String: Any])
        #expect(throws: O4CommandError.self) { try OrthoEngineClient.decodeImageryFreshnessReady(failed).get() }
        #expect(throws: O4CommandError.self) { try OrthoEngineClient.decodeImageryFreshnessReady(nil).get() }
    }
}
