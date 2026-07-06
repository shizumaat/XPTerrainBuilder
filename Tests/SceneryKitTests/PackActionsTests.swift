import Testing
import Foundation
@testable import SceneryKit

@Suite struct PackActionsTests {

    /// Copy the FakeXP fixture into a unique temp dir so actions can mutate it.
    func makeScratchInstall() throws -> URL {
        let source = Bundle.module.url(forResource: "Fixtures/FakeXP", withExtension: nil)!
        let scratch = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSceneryDoctorTests-\(UUID().uuidString)")
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
