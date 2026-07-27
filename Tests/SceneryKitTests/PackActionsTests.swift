import Testing
import Foundation
@testable import SceneryKit

@Suite struct IniReconcileTests {
    func makePack(_ name: String, kind: PackKind, status: PackStatus = .enabled,
                  signature: String = "") -> SceneryPack {
        // Kind is computed from content flags — synthesize the right ones.
        SceneryPack(
            name: name, url: URL(fileURLWithPath: "/tmp/CS/\(name)"), status: status,
            iniIndex: nil, isLibrary: kind == .library,
            airports: kind == .airport ? ["XTST": AirportInfo(name: "T", latitude: 1, longitude: 1)] : [:],
            tiles: kind == .airport || kind == .library ? [] : ["+10+010"],
            isOverlay: kind == .landmark ? true : (kind == .mesh ? false : nil),
            isLaminar: false, signature: signature,
            hasTerrain: kind == .ortho || kind == .mesh,
            isPhotoTextured: kind == .ortho)
    }

    func makeService(ini: String) throws -> (PackActionService, URL) {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDReconcile-\(UUID().uuidString)")
        let customScenery = root.appendingPathComponent("Custom Scenery")
        try FileManager.default.createDirectory(at: customScenery, withIntermediateDirectories: true)
        let iniURL = customScenery.appendingPathComponent("scenery_packs.ini")
        try ini.write(to: iniURL, atomically: true, encoding: .utf8)
        return (PackActionService(root: root), root)
    }

    @Test func additionsLandInTheirKindGroups() throws {
        let ini = """
        I
        1000 Version
        SCENERY

        SCENERY_PACK Custom Scenery/Alpha Airport/
        SCENERY_PACK *GLOBAL_AIRPORTS*
        SCENERY_PACK Custom Scenery/City Landmark/
        SCENERY_PACK Custom Scenery/Some Library/
        SCENERY_PACK Custom Scenery/zOrtho A/
        SCENERY_PACK Custom Scenery/zzz Mesh/
        """
        let (service, root) = try makeService(ini: ini)
        defer { try? FileManager.default.removeItem(at: root) }

        let installed = [
            makePack("Alpha Airport", kind: .airport),
            makePack("City Landmark", kind: .landmark),
            makePack("Some Library", kind: .library),
            makePack("zOrtho A", kind: .ortho),
            makePack("zzz Mesh", kind: .mesh),
            // The new arrivals:
            makePack("Beta Airport", kind: .airport),
            makePack("New Overlay", kind: .landmark),
            makePack("aOrtho New", kind: .ortho),
        ]
        let result = service.reconcile(installedPacks: installed, previousPacks: [])
        #expect(result.added.sorted() == ["Beta Airport", "New Overlay", "aOrtho New"].sorted())
        #expect(result.removed.isEmpty)

        let lines = try String(contentsOf: service.iniURL, encoding: .utf8)
            .components(separatedBy: "\n")
        func index(of fragment: String) -> Int {
            lines.firstIndex { $0.contains(fragment) } ?? -1
        }
        // New airport just above Global Airports.
        #expect(index(of: "Beta Airport") == index(of: "*GLOBAL_AIRPORTS*") - 1)
        #expect(index(of: "Beta Airport") > index(of: "Alpha Airport"))
        // New landmark with the landmarks, before the library.
        #expect(index(of: "New Overlay") > index(of: "City Landmark"))
        #expect(index(of: "New Overlay") < index(of: "Some Library"))
        // New ortho with the orthos, above the mesh.
        #expect(index(of: "aOrtho New") > index(of: "Some Library"))
        #expect(index(of: "aOrtho New") < index(of: "zzz Mesh"))
    }

    @Test func removalsAndRenames() throws {
        let ini = """
        I
        1000 Version
        SCENERY

        SCENERY_PACK Custom Scenery/Keeper/
        SCENERY_PACK_DISABLED Custom Scenery/Old Name/
        SCENERY_PACK Custom Scenery/Gone Forever/
        """
        let (service, root) = try makeService(ini: ini)
        defer { try? FileManager.default.removeItem(at: root) }

        let previous = [
            makePack("Keeper", kind: .airport, signature: "aaa"),
            makePack("Old Name", kind: .landmark, status: .disabled, signature: "bbb"),
            makePack("Gone Forever", kind: .landmark, signature: "ccc"),
        ]
        let installed = [
            makePack("Keeper", kind: .airport, signature: "aaa"),
            makePack("New Name", kind: .landmark, signature: "bbb"), // renamed
            // "Gone Forever" deleted in Finder.
        ]
        let result = service.reconcile(installedPacks: installed, previousPacks: previous)
        #expect(result.renamed == ["Old Name → New Name"])
        #expect(result.removed == ["Gone Forever"])
        #expect(result.added.isEmpty)

        let text = try String(contentsOf: service.iniURL, encoding: .utf8)
        // Rename keeps the slot AND the disabled keyword.
        #expect(text.contains("SCENERY_PACK_DISABLED Custom Scenery/New Name/"))
        #expect(!text.contains("Old Name"))
        #expect(!text.contains("Gone Forever"))
    }

    @Test func noChangesMeansNoWrite() throws {
        let ini = "I\n1000 Version\nSCENERY\n\nSCENERY_PACK Custom Scenery/Keeper/\n"
        let (service, root) = try makeService(ini: ini)
        defer { try? FileManager.default.removeItem(at: root) }
        let before = Date(timeIntervalSince1970: 1000)
        try FileManager.default.setAttributes(
            [.modificationDate: before], ofItemAtPath: service.iniURL.path)

        let result = service.reconcile(
            installedPacks: [makePack("Keeper", kind: .airport)], previousPacks: [])
        #expect(!result.changed)
        let mtime = try FileManager.default
            .attributesOfItem(atPath: service.iniURL.path)[.modificationDate] as? Date
        #expect(mtime == before, "an unchanged ini must not be rewritten")
    }

    /// The cheap status/order refresh the scan uses after reconcile rewrote
    /// the ini: line order is the load rank, and only the DISABLED keyword
    /// makes a pack disabled.
    @Test func iniOrderAndStatusesFollowLineOrder() throws {
        let ini = """
        I
        1000 Version
        SCENERY

        SCENERY_PACK Custom Scenery/Airport A/
        SCENERY_PACK *GLOBAL_AIRPORTS*
        SCENERY_PACK_DISABLED Custom Scenery/Ortho One/
        SCENERY_PACK Custom Scenery/Mesh M/
        """
        let (service, root) = try makeService(ini: ini)
        defer { try? FileManager.default.removeItem(at: root) }

        // *GLOBAL_AIRPORTS* is not a Custom Scenery path, so it takes no rank.
        #expect(service.iniOrder() == ["Airport A": 0, "Ortho One": 1, "Mesh M": 2])
        #expect(service.iniStatuses() == ["Airport A": true, "Ortho One": false, "Mesh M": true])
    }

    @Test func iniLineParsing() {
        #expect(PackActionService.packName(fromIniLine: "SCENERY_PACK Custom Scenery/Foo Bar/") == "Foo Bar")
        #expect(PackActionService.packName(fromIniLine: "SCENERY_PACK_DISABLED Custom Scenery/Baz/") == "Baz")
        #expect(PackActionService.packName(fromIniLine: "SCENERY_PACK *GLOBAL_AIRPORTS*") == nil)
        #expect(PackActionService.packName(fromIniLine: "1000 Version") == nil)
    }
}
