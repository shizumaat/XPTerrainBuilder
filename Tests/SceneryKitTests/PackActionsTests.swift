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

    @Test func tileCoLoadCountsWinnerPlusOverlaysOnly() {
        // X-Plane loads ONE base mesh per tile (highest priority) and merges
        // overlays on top — shadowed bases must not count toward VRAM.
        func base(_ name: String, rank: Int) -> SceneryPack {
            var pack = makePack(name, kind: .ortho)
            pack.iniIndex = rank
            return pack
        }
        var overlay = makePack("Overlay City", kind: .landmark)
        overlay.iniIndex = 0
        let packs = [base("Winning Ortho", rank: 1),
                     base("Shadowed State Ortho", rank: 2),
                     overlay]
        var config = HealthConfig()
        config.vramBudgetBytes = 4_000
        // Each pack ~3,000 bytes VRAM on one tile: winner + overlay = 6,000
        // (over the 3/4 budget threshold of 3,000); all three would be 9,000.
        let findings = Analyzer.tileCoLoadFindings(
            packs: packs,
            packVRAM: ["Winning Ortho": 3_000, "Shadowed State Ortho": 3_000,
                       "Overlay City": 3_000],
            config: config)
        #expect(findings.count == 1)
        let detail = findings.first?.detail ?? ""
        #expect(detail.contains("Winning Ortho"))
        #expect(detail.contains("Overlay City"))
        #expect(!detail.contains("'Shadowed State Ortho'"),
                "the shadowed base never loads and must not be counted")
        #expect(detail.contains("1 lower-priority base pack"))
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
}

@Suite struct PackActionsTests {

    /// Copy the FakeXP fixture into a unique temp dir so actions can mutate it.
    func makeScratchInstall() throws -> URL {
        let source = Bundle.module.url(forResource: "Fixtures/FakeXP", withExtension: nil)!
        let scratch = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPScenerySmithTests-\(UUID().uuidString)")
        try FileManager.default.copyItem(at: source, to: scratch)
        return scratch
    }

    func iniText(_ root: URL) -> String {
        TextFile.contents(of: root.appendingPathComponent("Custom Scenery/scenery_packs.ini")) ?? ""
    }

    @Test func disableRewritesIniLine() throws {
        let root = try makeScratchInstall()
        defer { try? FileManager.default.removeItem(at: root) }

        let outcomes = PackActionService(root: root).apply(.disable, to: ["Another KSEA"])
        #expect(outcomes.allSatisfy { $0.success })

        let ini = iniText(root)
        #expect(ini.contains("SCENERY_PACK_DISABLED Custom Scenery/Another KSEA/"))
        #expect(!ini.contains("SCENERY_PACK Custom Scenery/Another KSEA/"))
        // Other lines untouched.
        #expect(ini.contains("SCENERY_PACK Custom Scenery/KSEA Demo Airport/"))
    }

    @Test func enableRestoresIniLine() throws {
        let root = try makeScratchInstall()
        defer { try? FileManager.default.removeItem(at: root) }
        let service = PackActionService(root: root)

        _ = service.apply(.disable, to: ["Another KSEA"])
        let outcomes = service.apply(.enable, to: ["Another KSEA"])
        #expect(outcomes.allSatisfy { $0.success })
        #expect(iniText(root).contains("SCENERY_PACK Custom Scenery/Another KSEA/"))
        #expect(!iniText(root).contains("SCENERY_PACK_DISABLED Custom Scenery/Another KSEA/"))
    }

    @Test func disableUnlistedPackAppendsLine() throws {
        let root = try makeScratchInstall()
        defer { try? FileManager.default.removeItem(at: root) }

        // OpenSceneryX is in the ini; a brand-new pack is not.
        let newPack = root.appendingPathComponent("Custom Scenery/Brand New Pack")
        try FileManager.default.createDirectory(at: newPack, withIntermediateDirectories: true)

        let outcomes = PackActionService(root: root).apply(.disable, to: ["Brand New Pack"])
        #expect(outcomes.allSatisfy { $0.success })
        #expect(iniText(root).contains("SCENERY_PACK_DISABLED Custom Scenery/Brand New Pack/"))
    }

    @Test func moveToDisabledFolderRelocatesAndDropsIniLine() throws {
        let root = try makeScratchInstall()
        defer { try? FileManager.default.removeItem(at: root) }
        let fm = FileManager.default

        let outcomes = PackActionService(root: root).apply(.uninstall, to: ["Another KSEA"])
        #expect(outcomes.allSatisfy { $0.success })

        #expect(!fm.fileExists(atPath: root.appendingPathComponent("Custom Scenery/Another KSEA").path))
        #expect(fm.fileExists(atPath: root.appendingPathComponent("Custom Scenery (Disabled)/Another KSEA/Earth nav data/apt.dat").path))
        #expect(!iniText(root).contains("Another KSEA"))
    }

    @Test func moveFailsCleanlyWhenDestinationOccupied() throws {
        let root = try makeScratchInstall()
        defer { try? FileManager.default.removeItem(at: root) }
        let fm = FileManager.default

        let occupied = root.appendingPathComponent("Custom Scenery (Disabled)/Another KSEA")
        try fm.createDirectory(at: occupied, withIntermediateDirectories: true)

        let outcomes = PackActionService(root: root).apply(.uninstall, to: ["Another KSEA"])
        #expect(outcomes.count == 1)
        #expect(outcomes[0].success == false)
        // Source untouched on failure.
        #expect(fm.fileExists(atPath: root.appendingPathComponent("Custom Scenery/Another KSEA").path))
        #expect(iniText(root).contains("SCENERY_PACK Custom Scenery/Another KSEA/"))
    }

    @Test func reorderPermutesOnlyOccupiedSlots() throws {
        // A drag in the (filtered) inspector must not haul a pack across the
        // ini's airports/libraries/ortho regions — the reordered packs swap
        // among their own line slots and everything else stays byte-identical.
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDReorder-\(UUID().uuidString)")
        let customScenery = root.appendingPathComponent("Custom Scenery")
        try FileManager.default.createDirectory(at: customScenery, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: root) }

        let ini = """
        I
        1000 Version
        SCENERY

        SCENERY_PACK Custom Scenery/Airport A/
        SCENERY_PACK *GLOBAL_AIRPORTS*
        SCENERY_PACK Custom Scenery/Library L/
        SCENERY_PACK_DISABLED Custom Scenery/Ortho One/
        SCENERY_PACK Custom Scenery/Ortho Two/
        SCENERY_PACK Custom Scenery/Mesh M/
        """
        try Data(ini.utf8).write(to: customScenery.appendingPathComponent("scenery_packs.ini"))
        let service = PackActionService(root: root)

        // User drags Ortho Two above Ortho One; Airport A stays first in the
        // visible order. Even though Ortho Two sits right below Airport A in
        // the on-screen list, it must only rise to Ortho One's old slot.
        let error = service.reorder(packNames: ["Airport A", "Ortho Two", "Ortho One"])
        #expect(error == nil)

        let lines = iniText(root).components(separatedBy: "\n")
        #expect(lines[4] == "SCENERY_PACK Custom Scenery/Airport A/")
        #expect(lines[5] == "SCENERY_PACK *GLOBAL_AIRPORTS*")           // untouched
        #expect(lines[6] == "SCENERY_PACK Custom Scenery/Library L/")   // untouched
        #expect(lines[7] == "SCENERY_PACK Custom Scenery/Ortho Two/")   // swapped in
        // The disabled keyword travels with the pack, not the slot.
        #expect(lines[8] == "SCENERY_PACK_DISABLED Custom Scenery/Ortho One/")
        #expect(lines[9] == "SCENERY_PACK Custom Scenery/Mesh M/")      // untouched

        // Unlisted packs are appended enabled, in the requested order.
        let error2 = service.reorder(packNames: ["Mesh M", "Fresh Pack"])
        #expect(error2 == nil)
        let after = iniText(root)
        #expect(after.contains("SCENERY_PACK Custom Scenery/Fresh Pack/"))
        #expect(service.iniOrder()["Airport A"] == 0)
        #expect(service.iniOrder()["Ortho Two"] == 2)
        #expect(service.iniOrder()["Fresh Pack"] == 5)
    }

    @Test func iniLineParsing() {
        #expect(PackActionService.packName(fromIniLine: "SCENERY_PACK Custom Scenery/Foo Bar/") == "Foo Bar")
        #expect(PackActionService.packName(fromIniLine: "SCENERY_PACK_DISABLED Custom Scenery/Baz/") == "Baz")
        #expect(PackActionService.packName(fromIniLine: "SCENERY_PACK *GLOBAL_AIRPORTS*") == nil)
        #expect(PackActionService.packName(fromIniLine: "1000 Version") == nil)
    }

    @Test func duplicateGroupsProduced() {
        let source = Bundle.module.url(forResource: "Fixtures/FakeXP", withExtension: nil)!
        let installation = InstallationScanner(root: source).scan()
        let (_, groups) = DuplicateAnalyzer(installation: installation).analyze()
        let ksea = groups.first { $0.icao == "KSEA" }
        #expect(ksea != nil)
        #expect(ksea?.packs.count == 2)
        #expect(ksea?.packs.first { $0.isWinner }?.name == "KSEA Demo Airport")
    }
}
