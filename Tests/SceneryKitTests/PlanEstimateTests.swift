import Testing
import Foundation
@testable import SceneryKit

/// The build-cost estimate (protocol 1.15, #820): the `PlanEstimateReady`
/// decode, the disk verdict, and the panel lines — the same strings
/// `Ortho4XP/tests/test_qt_plan_estimate.py` expects of the Qt window.
struct PlanEstimateTests {

    private func event(verdict: String = "ok", reason: String = "") -> O4JSON {
        O4JSON.from([
            "event": "PlanEstimateReady", "request": 7, "error": "",
            "result": [
                "tiles": [["lat": 45, "lon": -123, "download_gb": [0.5, 2.7],
                           "disk_gb": [1.8, 8.5], "time_s": [500, 2500],
                           "textures": ["count": [117, 234]], "has_history": false] as [String: Any]],
                "total": ["download_gb": [0.5, 2.7], "disk_gb": [1.8, 8.5],
                          "time_s": [500, 2500]] as [String: Any],
                "free_gb": 27.3, "cache_free_gb": NSNull(),
                "verdict": verdict, "reason": reason,
            ] as [String: Any],
        ] as [String: Any])
    }

    @Test func planEstimateReadyDecodesTheResultOrTheError() throws {
        let estimate = try OrthoEngineClient.decodePlanEstimateReady(event()).get()
        #expect(estimate.tiles.count == 1)
        #expect(estimate.tiles[0].id == "+45-123")
        #expect(estimate.tiles[0].downloadGB == O4Range(0.5, 2.7))
        #expect(estimate.total.timeS == O4Range(500, 2500))
        #expect(estimate.freeGB == 27.3)
        #expect(estimate.cacheFreeGB == nil)
        #expect(estimate.blockingReason == nil && estimate.verdictLine == nil)
        let failed = O4JSON.from(["event": "PlanEstimateReady", "request": 7, "error": "boom",
                                  "result": NSNull()] as [String: Any])
        #expect(throws: O4CommandError.self) { try OrthoEngineClient.decodePlanEstimateReady(failed).get() }
        #expect(throws: O4CommandError.self) { try OrthoEngineClient.decodePlanEstimateReady(nil).get() }
    }

    @Test func aRefusalBlocksBuildWithTheReasonAndAWarningDoesNot() throws {
        let refuse = try OrthoEngineClient.decodePlanEstimateReady(
            event(verdict: "refuse", reason: "needs at least 1.8 GB")).get()
        #expect(refuse.blockingReason == "needs at least 1.8 GB")
        #expect(refuse.verdictLine == "needs at least 1.8 GB")
        let warn = try OrthoEngineClient.decodePlanEstimateReady(
            event(verdict: "warn", reason: "may need up to 8.5 GB")).get()
        #expect(warn.blockingReason == nil)
        #expect(warn.verdictLine == "may need up to 8.5 GB")
    }

    @Test func thePanelLinesMatchTheQtWindow() throws {
        let estimate = try OrthoEngineClient.decodePlanEstimateReady(event()).get()
        #expect(PlanEstimateText.total(estimate)
                == "Download 0.5–2.7 GB · Disk 1.8–8.5 GB of 27.3 GB free · 8–42 min")
        #expect(PlanEstimateText.tile(estimate.tiles[0])
                == "+45-123  ↓ 0.5–2.7 GB · disk 1.8–8.5 GB · 8–42 min")
        #expect(PlanEstimateText.time(O4Range(60, 70)) == "1–2 min")
        #expect(PlanEstimateText.time(O4Range(3600, 3 * 3600)) == "1.0–3.0 h")
        #expect(PlanEstimateText.gb(O4Range(0, 0.01)) == "none")
    }

    @Test func theCommandExistsFromProtocol115() {
        #expect(!O4ProtocolVersion.supportsPlanEstimate("1.14"))
        #expect(O4ProtocolVersion.supportsPlanEstimate("1.15"))
        #expect(O4ProtocolVersion.supportsPlanEstimate("2.0"))
    }
}
