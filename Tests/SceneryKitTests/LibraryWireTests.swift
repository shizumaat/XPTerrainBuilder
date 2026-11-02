import Testing
import Foundation
@testable import SceneryKit

/// The Library's wire (#824): a `LibraryReady` event decodes into the
/// typed scan, and an error or a missing event is the engine's sentence.
struct LibraryWireTests {

    private static var scan: [String: Any] {
        let pack: [String: Any] = ["pack_name": "KPDX Pack", "pack_path": "/p", "objects": 3]
        let ours: [String: Any] = [
            "tile": "+45-123", "lat": 45, "lon": -123, "build_dir": "/t/zOrtho4XP_+45-123",
            "size_bytes": 5_000_000_000, "zl": 17, "provider": "BI", "built": 1.7e9,
            "airports": ["KHIO", "KPDX"], "packs_modified": [pack] as [[String: Any]],
            "link_status": "installed", "in_xplane": true,
            "built_by": "XPTerrainBuilder", "read_only": false,
        ]
        let other: [String: Any] = [
            "tile": "+46-123", "lat": 46, "lon": -123, "build_dir": "/t/zOrtho4XP_+46-123",
            "size_bytes": 10, "zl": NSNull(), "provider": "", "built": NSNull(),
            "airports": [String](), "packs_modified": [[String: Any]](),
            "link_status": "not_installed", "in_xplane": false,
            "built_by": "other", "read_only": true,
        ]
        let cache: [String: Any] = ["kind": "imagery", "label": "Imagery", "path": "/i",
                                    "bytes": 1024, "redownload": "Downloaded again."]
        return ["tiles": [ours, other] as [[String: Any]], "tiles_bytes": 5_000_000_010,
                "caches": [cache] as [[String: Any]]]
    }

    @Test func libraryReadyDecodesTheScan() throws {
        let event = O4JSON.from(["event": "LibraryReady", "request": 3, "command": "library_scan",
                                 "error": "", "result": Self.scan] as [String: Any])
        let scan: O4LibraryScan = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(scan.tilesBytes == 5_000_000_010)
        #expect(scan.tiles.map(\.tile) == ["+45-123", "+46-123"])
        #expect(scan.tiles[0].packsModified.first?.packName == "KPDX Pack")
        #expect(scan.tiles[0].inXPlane && !scan.tiles[0].readOnly)
        #expect(scan.tiles[1].zl == nil && scan.tiles[1].built == nil && scan.tiles[1].readOnly)
        #expect(scan.caches.first?.bytes == 1024)
    }

    @Test func searchMatchesAnyListedField() throws {
        let event = O4JSON.from(["event": "LibraryReady", "error": "", "result": Self.scan] as [String: Any])
        let scan: O4LibraryScan = try OrthoEngineClient.decodeLibraryReady(event).get()
        #expect(scan.tiles.filter { $0.matches("kpdx") }.map(\.tile) == ["+45-123"])
        #expect(scan.tiles.filter { $0.matches("read-only") }.map(\.tile) == ["+46-123"])
        #expect(scan.tiles.filter { $0.matches("") }.count == 2)
    }

    @Test func anErrorOrNoEventIsTheEnginesSentence() {
        let failed = O4JSON.from(["event": "LibraryReady", "error": "no folder",
                                  "result": NSNull()] as [String: Any])
        #expect(throws: O4CommandError.self) {
            let _: O4LibraryScan = try OrthoEngineClient.decodeLibraryReady(failed).get()
        }
        #expect(throws: O4CommandError.self) {
            let _: O4LibraryFreed = try OrthoEngineClient.decodeLibraryReady(nil).get()
        }
    }

    /// #1699 phase 1: the export and import results, as the engine sends
    /// them (`tile_bundle.export` / `tile_bundle.importer`; the import's
    /// object-stage counts and stale reasons ride along undecoded).
    @Test func bundleResultsDecode() throws {
        let exported = O4JSON.from(["event": "LibraryReady", "command": "library_export_bundle",
                                    "error": "", "result": [
                                        "path": "/out/XPTerrainBuilder_+45-123.xptbundle",
                                        "bytes": 72_801_612, "key": "c5ec45c2", "files": 37,
                                        "seconds": 119.2] as [String: Any]] as [String: Any])
        let done: O4LibraryBundleExport = try OrthoEngineClient.decodeLibraryReady(exported).get()
        #expect(done.bytes == 72_801_612 && done.files == 37)
        let imported = O4JSON.from(["event": "LibraryReady", "command": "library_import_bundle",
                                    "error": "", "result": [
                                        "tile": "+45-123", "key": "c5ec45c2", "airports": ["KPDX"],
                                        "bytes": 282_662_654, "reused": ["vector", "mesh", "masks"],
                                        "object_stage": ["airports": 7] as [String: Any],
                                        "stale": ["vector": NSNull()] as [String: Any],
                                        "seconds": 34.3] as [String: Any]] as [String: Any])
        let got: O4LibraryBundleImport = try OrthoEngineClient.decodeLibraryReady(imported).get()
        #expect(got.tile == "+45-123" && got.reused == ["vector", "mesh", "masks"])
    }
}
