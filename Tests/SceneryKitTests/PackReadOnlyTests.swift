import Testing
import Foundation
@testable import SceneryKit

/// A read-only airport pack (capability pack_readonly, issue #2174). The
/// wire names are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` class and field names; these tests
/// are the drift alarm.
struct PackReadOnlyTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackReadOnly",
            "pack": "KSBN - Alpine Aviation",
            "pack_root": "/X/Custom Scenery/KSBN - Alpine Aviation",
            "lat": 41, "lon": -87,
            "folders": ["KSBN - Alpine Aviation", "KSBN - Alpine Aviation/Earth nav data"],
            "changed": 0, "rebuild": false, "state": "found", "error": "",
        ]
    }

    @Test func decodesEveryField() throws {
        guard case .packReadOnly(let r)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackReadOnly did not decode")
            return
        }
        #expect(r.pack == "KSBN - Alpine Aviation")
        #expect(r.packRoot == "/X/Custom Scenery/KSBN - Alpine Aviation")
        #expect(r.lat == 41 && r.lon == -87)
        #expect(r.folders.count == 2)
        #expect(r.state == "found" && r.asks)
        #expect(r.id == r.packRoot)
        #expect(r.bodyText.hasPrefix(
            "KSBN - Alpine Aviation is read-only (as it was downloaded), so "
                + "XPTerrainBuilder can't adjust it. Make it writable?"))
        #expect(r.bodyText.contains("Read-only: KSBN - Alpine Aviation, "))
    }

    @Test func outcomeDecodesAndDoesNotAsk() throws {
        var event = fullEvent
        event["state"] = "writable"
        event["changed"] = 3
        event["rebuild"] = true
        guard case .packReadOnly(let r)? = O4Event.parse(object: event) else {
            Issue.record("PackReadOnly did not decode")
            return
        }
        #expect(!r.asks && r.changed == 3 && r.rebuild)
    }

    @Test func absentFieldsDefault() throws {
        guard case .packReadOnly(let r)? = O4Event.parse(object: ["event": "PackReadOnly"]) else {
            Issue.record("PackReadOnly did not decode")
            return
        }
        #expect(r.state == "found" && r.folders.isEmpty && !r.rebuild)
    }

    @Test func copyIsTheOwners() {
        #expect(O4PackReadOnlyCopy.writableButton == "Make writable")
        #expect(O4PackReadOnlyCopy.notNowButton == "Not now")
        #expect(O4PackReadOnlyCopy.rowStatus == "read-only — not adjusted")
        #expect(O4EngineCapabilities.packReadOnly == "pack_readonly")
    }
}
