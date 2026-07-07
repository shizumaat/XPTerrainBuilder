import Testing
import Foundation
@testable import SceneryKit

@Suite struct Phase1Tests {

    static func makeDSF(terrains: [String] = [], objects: [String] = [],
                        properties: [String: String] = [:]) -> Data {
        var body = Data()
        body.append(UnusedResourceTests.atom("TERT", UnusedResourceTests.stringTable(terrains)))
        body.append(UnusedResourceTests.atom("OBJT", UnusedResourceTests.stringTable(objects)))

        var dsf = Data("XPLNEDSF".utf8)
        var version = Int32(1).littleEndian
        withUnsafeBytes(of: &version) { dsf.append(contentsOf: $0) }
        if !properties.isEmpty {
            var propStrings: [String] = []
            for (key, value) in properties { propStrings.append(key); propStrings.append(value) }
            let head = UnusedResourceTests.atom("PROP", UnusedResourceTests.stringTable(propStrings))
            dsf.append(UnusedResourceTests.atom("HEAD", head))
        }
        dsf.append(UnusedResourceTests.atom("DEFN", body))
        dsf.append(Data(repeating: 0, count: 16))
        return dsf
    }

    /// An install with: default library, an installed pack whose DSF has one
    /// good ref, one default-lib ref, one missing ref, one mojibake ref, a
    /// dead object with its texture, and an uninstalled pack.
    func makeInstall() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDPhase1-\(UUID().uuidString)")
        let fm = FileManager.default
        let pack = root.appendingPathComponent("Custom Scenery/Test Airport")

        for sub in ["Earth nav data/+40-080", "objects", "textures"] {
            try fm.createDirectory(at: pack.appendingPathComponent(sub), withIntermediateDirectories: true)
        }

        try Self.makeDSF(
            objects: [
                "objects/good.obj",           // exists
                "lib/airport/default_thing.obj", // default library
                "objects/ghost.obj",          // genuinely missing
                "objects/señal.obj",          // on disk as mojibake
            ],
            properties: ["sim/overlay": "1"]
        ).write(to: pack.appendingPathComponent("Earth nav data/+40-080/+41-073.dsf"))

        try "A\n800\nOBJ\n\nTEXTURE ../textures/good.png\nVT 0 0 0 0 1 0 0 0\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/good.obj"), atomically: true, encoding: .utf8)
        try Data(repeating: 1, count: 64).write(to: pack.appendingPathComponent("textures/good.png"))

        // Mojibake: disk name has 'Ã±' where the DSF says 'ñ'.
        try "A\n800\nOBJ\n\nVT 0 0 0 0 1 0 0 0\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/se\u{00C3}\u{00B1}al.obj"),
                   atomically: true, encoding: .utf8)

        // Dead object and its texture: nothing references either.
        try "A\n800\nOBJ\n\nTEXTURE ../textures/dead.png\nVT 0 0 0 0 1 0 0 0\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/dead.obj"), atomically: true, encoding: .utf8)
        try Data(repeating: 2, count: 128).write(to: pack.appendingPathComponent("textures/dead.png"))

        // Default library.
        let defaultLib = root.appendingPathComponent("Resources/default scenery/900 US")
        try fm.createDirectory(at: defaultLib, withIntermediateDirectories: true)
        try "A\n800\nLIBRARY\n\nEXPORT lib/airport/default_thing.obj objects/thing.obj\n"
            .write(to: defaultLib.appendingPathComponent("library.txt"), atomically: true, encoding: .utf8)

        // Uninstalled pack.
        let uninstalled = root.appendingPathComponent("Custom Scenery (Disabled)/Shelved Pack/Earth nav data")
        try fm.createDirectory(at: uninstalled, withIntermediateDirectories: true)
        try "A\n1100 x\n\n1 433 0 0 KPDX Portland Intl\n99\n"
            .write(to: uninstalled.appendingPathComponent("apt.dat"), atomically: true, encoding: .utf8)

        try "I\n1000 Version\nSCENERY\n\nSCENERY_PACK Custom Scenery/Test Airport/\n"
            .write(to: root.appendingPathComponent("Custom Scenery/scenery_packs.ini"),
                   atomically: true, encoding: .utf8)
        return root
    }

    @Test func proactiveMissingResourceAudit() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }

        let installation = InstallationScanner(root: root).scan()
        #expect(installation.defaultLibraryIndex.exportCount == 1)

        let (findings, groups) = ResourceAuditAnalyzer(installation: installation).analyze()
        let ids = findings.map { $0.checkID }

        // ghost.obj: missing. default_thing: resolved via default library (no finding).
        let missing = findings.filter { $0.checkID == "RES-01" }
        #expect(missing.count == 1, "\(ids)")
        #expect(missing.first?.title.contains("ghost.obj") == true)

        // señal.obj: mojibake rename with auto fix.
        let rename = findings.first { $0.checkID == "RES-02" }
        #expect(rename != nil, "\(ids)")
        if case .renameFile(_, let to)? = rename?.proposedFix {
            #expect(URL(fileURLWithPath: to).lastPathComponent == "señal.obj")
        } else {
            Issue.record("RES-02 should carry a renameFile fix")
        }

        // dead.obj AND its texture are unreachable (transitive).
        let unusedNames = Set(groups.flatMap { $0.files }
            .map { URL(fileURLWithPath: $0.path).lastPathComponent })
        #expect(unusedNames.contains("dead.obj"))
        #expect(unusedNames.contains("dead.png"))
        #expect(!unusedNames.contains("good.png"))
    }

    @Test func uninstalledPacksScannedWithStatus() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }

        let installation = InstallationScanner(root: root).scan()
        let shelved = installation.packs.first { $0.name == "Shelved Pack" }
        #expect(shelved?.status == .uninstalled)
        #expect(shelved?.airports["KPDX"] != nil)
        #expect(installation.packs.first { $0.name == "Test Airport" }?.status == .enabled)
    }

    @Test func installActionRoundTrip() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }
        let fm = FileManager.default
        let service = PackActionService(root: root)

        let outcomes = service.apply(.install, to: ["Shelved Pack"])
        #expect(outcomes.allSatisfy { $0.success }, "\(outcomes.map { $0.message ?? "" })")
        #expect(fm.fileExists(atPath: root.appendingPathComponent("Custom Scenery/Shelved Pack/Earth nav data/apt.dat").path))
        #expect(!fm.fileExists(atPath: root.appendingPathComponent("Custom Scenery (Disabled)/Shelved Pack").path))
        let ini = TextFile.contents(of: root.appendingPathComponent("Custom Scenery/scenery_packs.ini")) ?? ""
        #expect(ini.contains("SCENERY_PACK Custom Scenery/Shelved Pack/"))

        // And back out.
        let uninstall = service.apply(.uninstall, to: ["Shelved Pack"])
        #expect(uninstall.allSatisfy { $0.success })
        #expect(fm.fileExists(atPath: root.appendingPathComponent("Custom Scenery (Disabled)/Shelved Pack").path))
    }

    @Test func overlayPropertyParsed() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }

        let installation = InstallationScanner(root: root).scan()
        let pack = installation.packs.first { $0.name == "Test Airport" }
        #expect(pack?.isOverlay == true)
        // No apt.dat in this fixture pack: overlay DSF without airports = landmark.
        #expect(pack?.kind == .landmark)
        // The shelved pack has an apt.dat: airport.
        #expect(installation.packs.first { $0.name == "Shelved Pack" }?.kind == .airport)
    }

    @Test func globalNoBlendPromotion() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDPromote-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let obj = dir.appendingPathComponent("fence.obj")
        let text = """
        A
        800
        OBJ

        TEXTURE tex.png
        POINT_COUNTS 2 0 0 3
        VT 0 0 0 0 1 0 0 0
        VT 1 1 1 0 1 0 0 0
        IDX 0
        ATTR_no_blend
        TRIS 0 3
        """
        try Data(text.utf8).write(to: obj)
        let original = try Data(contentsOf: obj)

        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        let finding = Finding(
            checkID: "C-03", severity: .info, category: .packageHealth,
            title: "t", detail: "d", fixability: .auto,
            proposedFix: .promoteGlobalNoBlend(objPath: obj.path)
        )
        let outcomes = engine.apply([finding])
        #expect(outcomes.allSatisfy { $0.success }, "\(outcomes.map { $0.message ?? "" })")

        let info = try #require(ObjParser.parse(url: obj))
        #expect(info.hasGlobalNoBlend)
        #expect(info.perMeshNoBlend == 0)
        #expect(info.vertexCount == 2)

        // Revert restores byte-identical original.
        let reverts = engine.revert(engine.log.load())
        #expect(reverts.allSatisfy { $0.success })
        #expect(try Data(contentsOf: obj) == original)
    }

    @Test func crlfAndTabLibraryFilesParse() throws {
        // Swift treats "\r\n" as ONE grapheme, so split(separator: "\n")
        // never splits CRLF text — the bug that zeroed every Windows-authored
        // library index. Tabs as separators are the same family.
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDCRLF-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let crlf = "A\r\n800\r\nLIBRARY\r\n\r\nEXPORT Foo/a.obj\tobjects/a.obj\r\nEXPORT Foo/b.obj  objects/b.obj\r\n"
        try Data(crlf.utf8).write(to: dir.appendingPathComponent("library.txt"))

        var index = LibraryIndex()
        index.indexLibrary(at: dir, packName: "test")
        #expect(index.exportCount == 2)
        #expect(index.caseInsensitiveMatch(for: "Foo/a.obj") != nil)
        #expect(index.caseInsensitiveMatch(for: "foo/B.OBJ") != nil)

        // TextFile.lines handles every newline convention.
        #expect(TextFile.lines("a\r\nb\nc\rd").count == 4)

        // Backslash separators (RD_Library style) resolve to slash queries.
        let bs = "A\r\n800\r\nLIBRARY\r\n\r\nEXPORT RD_Lib\\Veg\\Pine.obj Veg\\Pine.obj\r\n"
        let bsDir = dir.appendingPathComponent("bs")
        try FileManager.default.createDirectory(at: bsDir, withIntermediateDirectories: true)
        try Data(bs.utf8).write(to: bsDir.appendingPathComponent("library.txt"))
        var bsIndex = LibraryIndex()
        bsIndex.indexLibrary(at: bsDir, packName: "bs")
        let export = bsIndex.caseInsensitiveMatch(for: "RD_Lib/Veg/Pine.obj")
        #expect(export != nil)
        #expect(export?.realPath == "Veg/Pine.obj")
    }

    @Test func seasonExportKeywordsParse() throws {
        // XP12's default libraries remap legacy XP8–XP11 paths (lib/g8/…)
        // through EXPORT_SEASON / EXPORT_EXCLUDE_SEASON, whose extra season
        // token ("sum" / "spr,sum") precedes the virtual path. Mis-parsing
        // it as the virtual path made those resources look uninstalled and
        // false-alarmed RES-01 on paths the sim substitutes automatically.
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDSeason-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let text = """
        A
        800
        LIBRARY

        EXPORT_SEASON sum\tlib/g8/coni_vcld_sdry.for\t\tsum/coni_vcld.for
        EXPORT_SEASON win\tlib/g8/coni_vcld_sdry.for\t\twin/coni_vcld.for
        EXPORT_EXCLUDE_SEASON spr,sum\tlib/g10/autogen/natural.ags\tEU/sub_Resid02.ags
        EXPORT_RATIO 0.5 lib/trees/oak.obj trees/oak.obj
        """
        try Data(text.utf8).write(to: dir.appendingPathComponent("library.txt"))

        var index = LibraryIndex()
        index.indexLibrary(at: dir, packName: "1000 world terrain")
        #expect(index.caseInsensitiveMatch(for: "lib/g8/coni_vcld_sdry.for") != nil)
        #expect(index.caseInsensitiveMatch(for: "lib/g10/autogen/natural.ags") != nil)
        #expect(index.caseInsensitiveMatch(for: "lib/trees/oak.obj") != nil)
        // The season token must not be indexed as a virtual path.
        #expect(index.caseInsensitiveMatch(for: "sum") == nil)
        #expect(index.caseInsensitiveMatch(for: "spr,sum") == nil)
    }

    @Test func controllerLossParsingAndDiagnosis() throws {
        // Log line extraction.
        let log = """
        0:00:00.000 E/APT: The airport KBNA (Nashville) has lost some controllers due to bad frequencies.  Each controller needs at least one frequency in the range of 118.00 to 136.990 mhz.
        0:00:00.000 E/APT: The airport EEEI (Ämari AB) has lost some controllers due to bad frequencies.  Each controller needs at least one frequency in the range of 118.00 to 136.990 mhz.
        """
        let scan = LogAnalyzer.parseLog(text: log)
        #expect(scan.controllerLosses.map { $0.icao } == ["KBNA", "EEEI"])
        #expect(scan.controllerLosses[1].name == "Ämari AB")
        #expect(scan.otherSceneryErrors.isEmpty) // not double-reported as noise

        // apt.dat diagnosis: UHF-only groups flagged; mixed groups not;
        // legacy 2-digit rows are in 10 kHz units; whitespace variants in
        // names split groups exactly as X-Plane sees them.
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDApt-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        let apt = """
        I
        1200 Generated by test

        1    599 0 0 KBNA Nashville
        1054 118600 NASHVILLE TOWER
        1054 257800 NASHVILLE TOWER
        1055 118400 NASHVILLE APPROACH (EAST)
        1055 372000 NASHVILLE APPROACH (WEST)
        54 25780 OLD  TOWER
        54 11860 OLD TOWER
        1    10 0 0 KOTH Other
        1054 999000 GHOST TOWER

        99
        """
        let aptURL = dir.appendingPathComponent("apt.dat")
        try apt.write(to: aptURL, atomically: true, encoding: .utf8)

        let bad = LogAnalyzer.outOfBandControllers(icao: "KBNA", aptURL: aptURL)
        let controllers = bad.map { $0.controller }
        #expect(controllers.contains("NASHVILLE APPROACH (WEST)"))
        #expect(!controllers.contains("NASHVILLE TOWER"))          // has 118.600
        #expect(!controllers.contains("NASHVILLE APPROACH (EAST)"))
        #expect(controllers.contains("OLD  TOWER"))                // 257.800, split by double space
        #expect(!controllers.contains("OLD TOWER"))                // 118.600 via legacy units
        #expect(bad.first { $0.controller == "NASHVILLE APPROACH (WEST)" }?.frequencies == "372.000 MHz")
        // Other airports' rows don't leak in.
        #expect(!controllers.contains("GHOST TOWER"))
    }

    @Test func deprecationMarkersScopeExports() throws {
        // Bare PUBLIC / PRIVATE / DEPRECATED / SEMI_DEPRECATED lines scope
        // every EXPORT after them (WED semantics). Laminar's default
        // libraries mark legacy art this way — RES-05 flags references to
        // paths whose every export is deprecated, and nothing else.
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDDeprecated-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let text = """
        A
        800
        LIBRARY

        DEPRECATED
        EXPORT lib/ships/Carrier.obj dynamic/blank.obj
        SEMI_DEPRECATED
        EXPORT lib/dynamic/balloon1.obj dynamic/balloon1.obj
        PUBLIC 20240630
        EXPORT lib/airport/windsock.obj landscape/windsock.obj
        DEPRECATED
        EXPORT lib/mixed/asset.obj old/asset.obj
        PUBLIC
        EXPORT lib/mixed/asset.obj new/asset.obj
        """
        try Data(text.utf8).write(to: dir.appendingPathComponent("library.txt"))

        var index = LibraryIndex()
        index.indexLibrary(at: dir, packName: "sim objects")
        #expect(index.caseInsensitiveMatch(for: "lib/ships/Carrier.obj")?.status == .deprecated)
        #expect(index.caseInsensitiveMatch(for: "lib/dynamic/balloon1.obj")?.status == .semiDeprecated)
        #expect(index.caseInsensitiveMatch(for: "lib/airport/windsock.obj")?.status == .public)
        #expect(index.fullyDeprecatedMatch(for: "lib/ships/Carrier.obj") != nil)
        #expect(index.fullyDeprecatedMatch(for: "lib/dynamic/balloon1.obj") != nil)
        #expect(index.fullyDeprecatedMatch(for: "lib/airport/windsock.obj") == nil)
        // One public export keeps a mixed-status path off the deprecated list.
        #expect(index.fullyDeprecatedMatch(for: "lib/mixed/asset.obj") == nil)
    }

    @Test func tileMathRoundTrips() {
        #expect(TileMath.key(lat: 41, lon: -73) == "+41-073")
        #expect(TileMath.key(lat: -9, lon: 8) == "-09+008")
        #expect(TileMath.key(latitude: 47.46, longitude: -122.31) == "+47-123")
        #expect(TileMath.parse("+41-073")! == (41, -73))
        #expect(TileMath.parse("-09+008")! == (-9, 8))
        #expect(TileMath.parse("garbage") == nil)
        // Round trip every plausible tile format.
        for (lat, lon) in [(0, 0), (89, 179), (-90, -180), (-1, -1)] {
            let key = TileMath.key(lat: lat, lon: lon)
            let parsed = TileMath.parse(key)
            #expect(parsed?.lat == lat && parsed?.lon == lon, "\(key)")
        }
    }

    @Test func nonPOTResampledToPowerOfTwo() throws {
        #expect(DDSEncoder.nearestPowerOfTwo(100) == 128)
        #expect(DDSEncoder.nearestPowerOfTwo(60) == 64)
        #expect(DDSEncoder.nearestPowerOfTwo(64) == 64)
        #expect(DDSEncoder.nearestPowerOfTwo(1500) == 1024)
    }
}
