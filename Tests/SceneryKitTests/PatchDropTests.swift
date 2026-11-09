import Testing
import Foundation
@testable import SceneryKit

/// #1979: the `patch_drop_plan` / `patch_drop_install` reply as the engine
/// sends it (`Ortho4XP/src/o4_engine/patch_drop.py`).
struct PatchDropTests {
    static let reply = """
    {"items": [{"source": "/d/KASE_auto.patch.osm", "name": "KASE_auto.patch.osm",
      "icao": "KASE", "tile": "+39-107", "found_by": "header",
      "destination": "/p/+30-110/+39-107/KASE_auto.patch.osm", "replaces": true,
      "companions": ["KASE.graded.json"],
      "backups": ["/p/+30-110/+39-107/KASE_auto.patch.osm.disabled"]}],
     "skipped": [{"source": "/d/x.txt", "skip": "x.txt is not a patch"}],
     "tiles": ["+39-107"],
     "summary": ["KASE_auto.patch.osm → KASE, tile +39-107", "Skipped: x.txt is not a patch"]}
    """

    @Test func theReplyDecodes() throws {
        let plan = try JSONDecoder().decode(O4PatchDropPlan.self, from: Data(Self.reply.utf8))
        let item = try #require(plan.items.first)
        #expect(item.icao == "KASE" && item.tile == "+39-107" && item.foundBy == "header")
        #expect(item.replaces && item.backups?.count == 1)
        #expect(plan.summary.count == 2)
        #expect(O4PatchDropCopy.installed(item)
                == "Tile +39-107: installed KASE_auto.patch.osm; the next build applies it.")
    }

    @Test func theFlagIsAfterTheFreeze() {
        #expect(!O4EngineCapabilities(protocolVersion: "1.32", flags: [])
                .supports(O4EngineCapabilities.patchDrop))
        #expect(O4EngineCapabilities(protocolVersion: "1.32", flags: ["patch_drop"])
                .supports(O4EngineCapabilities.patchDrop))
    }
}
