import Testing
import Foundation
@testable import SceneryKit

/// An airport pack with old flat (X-Plane 11) forests (protocol 1.17,
/// issue #1360). The wire names are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` class and field names; these tests
/// are the drift alarm.
struct PackOldForestsTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackOldForests",
            "pack": "Some Pack", "pack_root": "/X/Custom Scenery/Some Pack",
            "lat": 25, "lon": 51, "total": 3, "mapped": 2, "uses": 14,
            "first_paths": ["lib/g8/terrain/wet_hot_flat.for", "lib/g10/forests/AG_trees_EU1.for"],
            "unmapped": 1, "first_unmapped": ["forests/local.for"],
            "can_update": true, "files": [], "state": "found", "error": "",
        ]
    }

    @Test func decodesEveryField() throws {
        guard case .packOldForests(let f)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackOldForests did not decode")
            return
        }
        #expect(f.pack == "Some Pack")
        #expect(f.packRoot == "/X/Custom Scenery/Some Pack")
        #expect(f.lat == 25 && f.lon == 51)
        #expect(f.total == 3 && f.mapped == 2 && f.uses == 14)
        #expect(f.firstPaths.count == 2)
        #expect(f.unmapped == 1 && f.firstUnmapped == ["forests/local.for"])
        #expect(f.canUpdate)
        #expect(f.state == "found")
    }

    @Test func theCopyMatchesTheQtQuestion() throws {
        guard case .packOldForests(let f)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackOldForests did not decode")
            return
        }
        #expect(f.titleText == "3D trees for “Some Pack”")
        #expect(f.bodyText == "This airport’s scenery uses 2 old flat (X-Plane 11) tree "
                + "resources. Switch them to the X-Plane 12 3D trees?\n\n"
                + "The original scenery file is kept as a backup. Undo is on the "
                + "pack’s row under Modified airports.\n\n"
                + "1 other flat tree resource(s) have no X-Plane 12 3D equivalent "
                + "and stay as they are (first: forests/local.for).")
        #expect(O4PackOldForestsCopy.updateButton == "Update")
        #expect(O4PackOldForestsCopy.notNowButton == "Not now")
        #expect(O4PackOldForestsCopy.neverButton == "Never for this pack")
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .packOldForests(let f)? = O4Event.parse(object: ["event": "PackOldForests"]) else {
            Issue.record("PackOldForests did not decode")
            return
        }
        #expect(!f.canUpdate)          // no question without a yes
        #expect(f.state == "found")
        #expect(f.firstPaths.isEmpty && f.files.isEmpty)
    }
}
