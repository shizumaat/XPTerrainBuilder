import Testing
import Foundation
@testable import SceneryKit

/// Capability flags replace protocol bumps (RULINGS 2026-11-03d (1) item 3).
struct EngineCapabilitiesTests {
    @Test func aNamedFlagIsOffered() {
        let caps = O4EngineCapabilities(protocolVersion: "1.32", flags: ["future_feature"])
        #expect(caps.supports("future_feature"))
        #expect(!caps.supports("another_feature"))
    }

    @Test func aPreFreezeEngineIsReadByItsNumber() {
        let old = O4EngineCapabilities(protocolVersion: "1.24", flags: ["scan", "build"])
        #expect(old.supports(O4EngineCapabilities.insertShape))
        #expect(old.supports(O4EngineCapabilities.insertTunnelRamp))
        #expect(!old.supports(O4EngineCapabilities.objectSeatSet))
        #expect(!O4EngineCapabilities.none.supports(O4EngineCapabilities.insertShape))
    }

    @Test func theHelloCarriesTheFlags() {
        let hello: [String: Any] = ["event": "EngineHello", "ortho4xp_version": "dev",
                                    "protocol": "1.32", "capabilities": ["scan", "object_seat_set"]]
        guard case .hello(_, let version, let flags)? = O4Event.parse(object: hello) else {
            Issue.record("hello did not decode"); return
        }
        let caps = O4EngineCapabilities(protocolVersion: version, flags: flags)
        #expect(caps.supports(O4EngineCapabilities.objectSeatSet))
    }
}
