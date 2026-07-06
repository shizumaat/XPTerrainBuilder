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
