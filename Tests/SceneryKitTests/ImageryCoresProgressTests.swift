import Testing
import Foundation
@testable import SceneryKit

/// A background core sharpening's Activity row (#2039): the engine's
/// `ImageryCoresProgress` parses into its row, worded as the Qt window
/// words it (`O4_Imagery_OnDemand_Text.cores_row_status`).
struct ImageryCoresProgressTests {
    @Test func theEventParsesIntoItsRow() throws {
        let event = try #require(O4Event.parse(object: [
            "event": "ImageryCoresProgress", "lat": 37, "lon": -123,
            "state": "active", "done": 12, "failed": 1, "total": 40,
        ]))
        guard case .imageryCoresProgress(let progress) = event else {
            Issue.record("not an imageryCoresProgress: \(event)")
            return
        }
        #expect(progress == O4ImageryCoresProgress(
            lat: 37, lon: -123, state: "active", done: 12, failed: 1, total: 40))
        #expect(progress.running)
        #expect(abs(progress.fraction - 13.0 / 40.0) < 1e-9)
        #expect(O4OnDemandText.coresRowStatus(progress)
                == "Sharpening airport imagery · 12 of 40 squares")
    }

    @Test func eachOutcomeHasItsWords() {
        func row(_ state: String) -> O4ImageryCoresProgress {
            O4ImageryCoresProgress(lat: 0, lon: 0, state: state, done: 38, failed: 2, total: 40)
        }
        #expect(O4OnDemandText.coresRowStatus(row("done")) == "Airport imagery sharp · 38 of 40 squares")
        #expect(O4OnDemandText.coresRowStatus(row("error"))
                == "Sharpening airport imagery failed · 2 of 40 squares failed")
        #expect(O4OnDemandText.coresRowStatus(row("stopped"))
                == "Sharpening airport imagery stopped · 38 of 40 squares")
        #expect(!row("done").running)
    }
}
