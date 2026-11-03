import Testing
import Foundation
@testable import SceneryKit

/// An airport pack "Optimise pack" can lighten (protocol 1.24, issue
/// #1707). The wire names are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` class and field names; these tests
/// are the drift alarm.
struct PackOptimiseTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackOptimise",
            "pack": "Some Pack", "pack_root": "/X/Custom Scenery/Some Pack",
            "lat": 29, "lon": -96, "dedupe": 2720,
            "est_tris_before": 275_462_078, "est_tris_after": 222_000_000,
            "can_optimise": true, "files": [], "state": "found", "error": "",
        ]
    }

    @Test func decodesEveryField() throws {
        guard case .packOptimise(let o)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackOptimise did not decode")
            return
        }
        #expect(o.pack == "Some Pack" && o.packRoot == "/X/Custom Scenery/Some Pack")
        #expect(o.lat == 29 && o.lon == -96 && o.dedupe == 2720)
        #expect(o.estTrisBefore == 275_462_078 && o.estTrisAfter == 222_000_000)
        #expect(o.canOptimise && o.state == "found")
    }

    @Test func theCopyMatchesTheQtQuestion() throws {
        guard case .packOptimise(let o)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackOptimise did not decode")
            return
        }
        #expect(o.titleText == "Optimise “Some Pack”?")
        #expect(o.bodyText == "This airport’s objects draw 275.5 million triangles "
                + "on this tile, enough to cost frame rate. 2720 of its object "
                + "placements repeat another on the same spot. Optimise removes "
                + "them (222.0 million triangles).\n\n"
                + "The original scenery file is kept as a backup, and the "
                + "optimisation is applied again whenever the app rewrites this "
                + "pack. Undo is on the pack’s row under Modified airports.")
        #expect(O4PackOptimiseCopy.optimiseButton == "Optimise")
        #expect(O4PackOptimiseCopy.notNowButton == "Not now")
        #expect(O4PackOptimiseCopy.neverButton == "Never for this pack")
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .packOptimise(let o)? = O4Event.parse(object: ["event": "PackOptimise"]) else {
            Issue.record("PackOptimise did not decode")
            return
        }
        #expect(!o.canOptimise)        // no question without a yes
        #expect(o.state == "found" && o.files.isEmpty)
    }
}
