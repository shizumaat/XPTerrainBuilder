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

    @Test func planCarriesKindAndStillNeeds() throws {
        var plan = Self.plan
        plan["kind"] = "patch"
        plan["still_needs"] = [["what": "data", "text": "Elevation and map data for the tile (about 237.7 MB)",
                                "bytes": 237_654_132] as [String: Any],
                               ["what": "imagery", "text": "Imagery", "bytes": NSNull()] as [String: Any]]
        plan["estimate"] = ["build_seconds": 634.3, "download_bytes": 237_654_132] as [String: Any]
        let event = O4JSON.from(["event": "LibraryReady", "command": "package_plan",
                                 "error": "", "result": plan] as [String: Any])
        let got: O4PackagePlan = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(got.kind == "patch")
        #expect(got.stillNeeds?.map(\.what) == ["data", "imagery"])
        #expect(got.stillNeeds?.last?.bytes == nil)
        #expect(got.estimate?.downloadBytes == 237_654_132)
        // A package saved before kinds: empty kind, no rows, an empty estimate.
        var old = Self.plan
        old["kind"] = ""
        old["still_needs"] = [] as [Any]
        old["estimate"] = [:] as [String: Any]
        let before: O4PackagePlan = try OrthoEngineClient.decodeLibraryReady(O4JSON.from(
            ["event": "LibraryReady", "command": "package_plan", "error": "",
             "result": old] as [String: Any])).get()
        #expect(before.kind == "" && before.estimate == nil)
    }

    @Test func estimateAndAirportsDecode() throws {
        let row: [String: Any] = ["kind": "exact", "title": "Exact match",
                                  "explanation": "The airport with …", "available": true,
                                  "why": "", "files": 40, "data_bytes": 120_000_000,
                                  "bytes": 104_000_000, "download_bytes": 135_000_000,
                                  "build_seconds": 583.1,
                                  "still_needs": [["what": "imagery", "text": "Imagery",
                                                   "bytes": NSNull()] as [String: Any]],
                                  "figures": "about 104.0 MB · recipient downloads about 135.0 MB plus imagery · builds in about 10 min (estimate)"]
        let patch: [String: Any] = row.merging(["kind": "patch", "available": false,
                                                "why": "KLAX has no custom patch or edits on this tile."]) { $1 }
        let event = O4JSON.from(["event": "LibraryReady", "command": "package_estimate", "error": "",
                                 "result": ["airport": "KLAX", "tiles": ["+33-119"],
                                            "kinds": [row, patch]] as [String: Any]] as [String: Any])
        let got: O4PackageEstimate = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(got.kinds.map(\.kind) == ["exact", "patch"])
        #expect(got.kinds[0].figures.hasSuffix("(estimate)") && !got.kinds[1].available)
        let airports: O4PackageAirports = try OrthoEngineClient.decodeLibraryReady(O4JSON.from(
            ["event": "LibraryReady", "command": "package_airports", "error": "",
             "result": ["tiles": ["+33-119": ["KLAX", "KSMO"], "+34-119": ["KSMO"]],
                        "custom": ["+33-119": ["KLAX"]], "default": "KLAX"] as [String: Any]]
            as [String: Any])).get()
        #expect(airports.all == ["KLAX", "KSMO"] && airports.default == "KLAX")
    }

    @Test func packagesAreRoutedBySuffix() {
        #expect(O4TilePackage.isPackage(URL(fileURLWithPath: "/a/b.XPTB")))
        #expect(O4TilePackage.isPackage(URL(fileURLWithPath: "/a/b.xptbundle")))
        #expect(!O4TilePackage.isPackage(URL(fileURLWithPath: "/a/KXXX.patch.osm")))
    }
}
