import Testing
import Foundation
@testable import SceneryKit

/// RULINGS 2026-11-12g/h (`Ortho4XP/tests/test_world_home.py`): the
/// `world_onboard` reply's `home` and the `storage_tiers` reply decode as
/// the engine writes them; an older engine's reply without `home` still
/// decodes.
@Suite struct WorldHomeWireTests {
    @Test func onboardCarriesTheHome() throws {
        let json = """
        {"created": false, "offer": 0, "restart_needed": false,
         "home": {"active": true, "moved": 3, "left": 0, "conflicts": 0,
                  "world": "/X/Custom Scenery/zXPTerrainBuilder World",
                  "tiles_dir": "/X/Custom Scenery/zXPTerrainBuilder World/XPTerrainBuilder_tiles",
                  "packages_dir": "/X/Custom Scenery/zXPTerrainBuilder World/XPTerrainBuilder_packages"}}
        """
        let done = try JSONDecoder().decode(O4WorldOnboard.self, from: Data(json.utf8))
        let home = try #require(done.home)
        #expect(home.active && home.moved == 3 && home.left == 0)
        #expect(home.tilesDir.hasSuffix("XPTerrainBuilder_tiles"))
        let old = try JSONDecoder().decode(
            O4WorldOnboard.self, from: Data(#"{"created": true, "offer": 1, "restart_needed": false}"#.utf8))
        #expect(old.home == nil)
    }

    @Test func tiersDecode() throws {
        let json = """
        {"volumes": [{"mount": "/Volumes/A", "name": "A", "total_bytes": 100,
                      "free_bytes": 40, "size_gb": 50, "used_bytes": 7, "mounted": true},
                     {"mount": "/Volumes/B", "name": "B", "total_bytes": 0,
                      "free_bytes": 0, "size_gb": 20, "used_bytes": 0, "mounted": false}]}
        """
        let tiers = try JSONDecoder().decode(O4StorageTiers.self, from: Data(json.utf8))
        #expect(tiers.volumes.map(\.mount) == ["/Volumes/A", "/Volumes/B"])
        #expect(tiers.volumes[0].sizeGb == 50 && !tiers.volumes[1].mounted)
    }
}
