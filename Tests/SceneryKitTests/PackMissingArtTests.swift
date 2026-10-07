import Testing
import Foundation
@testable import SceneryKit

/// A pack X-Plane will not load (protocol 1.9, owner RULINGS 2026-10-06c,
/// issue #433). The wire names are STRING LITERALS matched against
/// `Ortho4XP/src/o4_engine/events.py` class and field names; these tests
/// are the drift alarm.
struct PackMissingArtTests {

    private var fullEvent: [String: Any] {
        [
            "event": "PackMissingArt",
            "pack": "Some Pack", "pack_root": "/X/Custom Scenery/Some Pack",
            "lat": 25, "lon": 51, "total": 108,
            "kinds": ["polygon": 108], "uses": 108,
            "first_paths": ["Imagery/a.pol", "Imagery/b.pol"],
            "can_omit": true, "state": "found", "error": "",
        ]
    }

    @Test func decodesEveryField() throws {
        guard case .packMissingArt(let art)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackMissingArt did not decode")
            return
        }
        #expect(art.pack == "Some Pack")
        #expect(art.packRoot == "/X/Custom Scenery/Some Pack")
        #expect(art.lat == 25 && art.lon == 51)
        #expect(art.total == 108 && art.uses == 108)
        #expect(art.kinds == ["polygon": 108])
        #expect(art.firstPaths == ["Imagery/a.pol", "Imagery/b.pol"])
        #expect(art.canOmit)
        #expect(art.state == "found")
    }

    @Test func theCopyIsTheOwnersVerbatim() throws {
        guard case .packMissingArt(let art)? = O4Event.parse(object: fullEvent) else {
            Issue.record("PackMissingArt did not decode")
            return
        }
        #expect(art.titleText == "X-Plane will not load “Some Pack”")
        #expect(art.bodyText == "Its scenery file refers to 108 file(s) that are not "
                + "installed (first: Imagery/a.pol). X-Plane skips a scenery pack "
                + "entirely when any file it refers to is missing, so this airport’s "
                + "buildings and ground would not appear in the simulator.")
        #expect(O4PackMissingArtCopy.primaryButton == "Build without the missing items")
        #expect(O4PackMissingArtCopy.secondaryButton == "Leave the pack as it is")
        #expect(O4PackMissingArtCopy.detail
                == "The original scenery file is kept as a backup and can be restored.")
    }

    @Test func absentFieldsDefaultSafely() {
        guard case .packMissingArt(let art)? = O4Event.parse(object: ["event": "PackMissingArt"]) else {
            Issue.record("PackMissingArt did not decode")
            return
        }
        #expect(!art.canOmit)          // no primary button without a yes
        #expect(art.state == "found")
        #expect(art.firstPaths.isEmpty)
    }
}
