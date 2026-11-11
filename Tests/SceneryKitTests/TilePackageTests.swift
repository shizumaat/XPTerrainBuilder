import Testing
import Foundation
@testable import SceneryKit

/// #2014: the package commands' results as the engine sends them
/// (`tile_bundle.install` / `.package`), and the drop's routing.
struct TilePackageTests {

    private static var plan: [String: Any] {
        let airport: [String: Any] = ["icao": "HECA", "pack": "HECA Cairo", "installed_pack": "",
                                      "match": "absent"]
        let conflict: [String: Any] = ["tile": "+30+031", "icao": "HECA", "kind": "custom",
                                       "installed": "your own patch", "choice": "keep",
                                       "backup": "/p/HECA_edited.patch.osm.disabled"]
        return ["path": "/d/XPTerrainBuilder_+30+031.xptb", "format": "xptb-2", "legacy": false,
                "key": "b0da81c1", "title": "Cairo", "creator": "Dev", "notes": "", "url": "",
                "created": "2026-11-11T15:42:02Z", "engine_version": "1.50.1901",
                "airports_only": NSNull(),
                "tiles": [["tile": "+30+031", "airports": [airport]] as [String: Any]],
                "sources": [] as [Any], "licence": "ODbL-1.0", "noncommercial": false,
                "bytes": 21_166_728, "data_bytes": 51_372_998, "files": 158,
                "counts": ["new": 158] as [String: Any], "kept_patches": [] as [Any],
                "conflicts": [conflict], "summary": ["Cairo by Dev", "Imagery is not included."],
                "installed": 158, "downloads_left": ["+30+031": [] as [String]] as [String: Any],
                "seconds": 1.1]
    }

    @Test func planDecodes() throws {
        let event = O4JSON.from(["event": "LibraryReady", "command": "package_install",
                                 "error": "", "result": Self.plan] as [String: Any])
        let got: O4PackagePlan = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(got.tiles.first?.airports.first?.match == "absent")
        #expect(got.conflicts.first?.kind == "custom" && got.conflicts.first?.choice == "keep")
        #expect(got.installed == 158 && got.downloadsLeft?["+30+031"] == [])
        #expect(O4TilePackageCopy.installed(got).contains("downloads only imagery"))
    }

    @Test func savedDecodes() throws {
        let event = O4JSON.from(["event": "LibraryReady", "command": "package_save", "error": "",
                                 "result": ["path": "/o/x.xptb", "bytes": 21_166_728,
                                            "data_bytes": 51_372_998, "key": "k", "files": 158,
                                            "tiles": ["+30+031"], "noncommercial": false,
                                            "seconds": 12.6] as [String: Any]] as [String: Any])
        let got: O4PackageSaved = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(got.tiles == ["+30+031"] && got.files == 158)
    }

    @Test func packagesAreRoutedBySuffix() {
        #expect(O4TilePackage.isPackage(URL(fileURLWithPath: "/a/b.XPTB")))
        #expect(O4TilePackage.isPackage(URL(fileURLWithPath: "/a/b.xptbundle")))
        #expect(!O4TilePackage.isPackage(URL(fileURLWithPath: "/a/KXXX.patch.osm")))
    }
}
