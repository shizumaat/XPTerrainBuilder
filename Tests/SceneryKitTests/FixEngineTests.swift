import Testing
import Foundation
@testable import SceneryKit

@Suite struct FixEngineTests {

    // MARK: Bounding box

    @Test func objParserComputesBoundingBox() {
        let text = """
        A
        800
        OBJ

        TEXTURE tex.png
        POINT_COUNTS 3 0 0 3
        VT -10 0 -20 0 1 0 0 0
        VT 10 5 20 0 1 0 0 0
        VT 0 152.5 0 0 1 0 0 0
        IDX 0
        TRIS 0 3
        """
        let info = ObjParser.parse(text: text)
        let dims = info.dimensions
        #expect(dims != nil)
        #expect(dims?.x == 20)
        #expect(dims?.y == 152.5)
        #expect(dims?.z == 40)
        #expect(info.largestDimension == 152.5)
    }

    // MARK: LOD advisor

    @Test func lodDistancesScaleWithSize() {
        // A 1.8 m person: floor kicks in.
        #expect(LODAdvisor.farCullDistance(forLargestDimension: 1.8) == 300)
        // A 30 m hangar: 100x.
        #expect(LODAdvisor.farCullDistance(forLargestDimension: 30) == 3000)
        // A 150 m terminal: capped at the ceiling.
        #expect(LODAdvisor.farCullDistance(forLargestDimension: 152.5) == 15_000)
        // Degenerate: no geometry info -> safe default.
        #expect(LODAdvisor.farCullDistance(forLargestDimension: nil) == 2000)
    }

    // MARK: Insertion

    @Test func insertFarLODLandsBeforeFirstDrawCommand() throws {
        let text = """
        A
        800
        OBJ

        TEXTURE tex.png
        ATTR_layer_group objects 1
        POINT_COUNTS 2 0 0 3
        VT 0 0 0 0 1 0 0 0
        VT 1 1 1 0 1 0 0 0
        IDX 0
        ATTR_no_blend
        TRIS 0 3
        """
        let edited = try #require(FixEngine.insertFarLOD(into: Data(text.utf8), distanceMeters: 4200))
        let lines = String(decoding: edited, as: UTF8.self).components(separatedBy: "\n")
        let lodIndex = try #require(lines.firstIndex(of: "ATTR_LOD 0 4200"))
        let trisIndex = try #require(lines.firstIndex(of: "TRIS 0 3"))
        let headerAttrIndex = try #require(lines.firstIndex(of: "ATTR_layer_group objects 1"))
        let pointCountsIndex = try #require(lines.firstIndex(where: { $0.hasPrefix("POINT_COUNTS") }))
        #expect(lodIndex < trisIndex)
        // Must stay below the header/data sections.
        #expect(lodIndex > headerAttrIndex)
        #expect(lodIndex > pointCountsIndex)

        let info = ObjParser.parse(data: edited)
        #expect(info.hasLOD)
        #expect(info.vertexCount == 2)
    }

    @Test func insertFarLODRefusesFileWithoutCommands() {
        let noCommands = "A\n800\nOBJ\n\nTEXTURE tex.png\n"
        #expect(FixEngine.insertFarLOD(into: Data(noCommands.utf8), distanceMeters: 1000) == nil)
    }

    // MARK: Apply + revert round-trip

    func makeScratch() throws -> (dir: URL, obj: URL, engine: FixEngine) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDFixTests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let obj = dir.appendingPathComponent("tower.obj")
        let text = """
        A
        800
        OBJ

        TEXTURE tex.png
        POINT_COUNTS 2 0 0 3
        VT 0 0 0 0 1 0 0 0
        VT 4 90 6 0 1 0 0 0
        IDX 0
        TRIS 0 3
        """
        try Data(text.utf8).write(to: obj)
        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("modifications.json")))
        return (dir, obj, engine)
    }

    @Test func applyBacksUpEditsAndLogs() throws {
        let (dir, obj, engine) = try makeScratch()
        defer { try? FileManager.default.removeItem(at: dir) }
        let original = try Data(contentsOf: obj)

        let finding = Finding(
            checkID: "C-02", severity: .warning, category: .packageHealth,
            title: "t", detail: "d", path: obj.path,
            fixability: .auto,
            proposedFix: .addFarLOD(objPath: obj.path, distanceMeters: 9000)
        )
        let outcomes = engine.apply([finding])
        #expect(outcomes.count == 1)
        #expect(outcomes[0].success, "\(outcomes[0].message ?? "")")

        // Backup holds the original bytes.
        let backup = try Data(contentsOf: URL(fileURLWithPath: obj.path + FixEngine.backupSuffix))
        #expect(backup == original)

        // File now parses with LOD.
        let info = ObjParser.parse(url: obj)
        #expect(info?.hasLOD == true)
        #expect(info?.vertexCount == 2)

        // Manifest has one record.
        let records = engine.log.load()
        #expect(records.count == 1)
        #expect(records.first?.filePath == obj.path)

        // Applying again is refused (already has LOD), nothing double-logged.
        let second = engine.apply([finding])
        #expect(second.first?.success == false)
        #expect(engine.log.load().count == 1)
    }

    @Test func revertRestoresOriginal() throws {
        let (dir, obj, engine) = try makeScratch()
        defer { try? FileManager.default.removeItem(at: dir) }
        let original = try Data(contentsOf: obj)

        let finding = Finding(
            checkID: "C-02", severity: .warning, category: .packageHealth,
            title: "t", detail: "d", path: obj.path,
            fixability: .auto,
            proposedFix: .addFarLOD(objPath: obj.path, distanceMeters: 9000)
        )
        _ = engine.apply([finding])
        let records = engine.log.load()

        let outcomes = engine.revert(records)
        #expect(outcomes.allSatisfy { $0.success })
        #expect(try Data(contentsOf: obj) == original)
        #expect(!FileManager.default.fileExists(atPath: obj.path + FixEngine.backupSuffix))
        #expect(engine.log.load().isEmpty)
    }

    // MARK: Latin-1 round-trip
    //
    // Files that decode only as ISO-Latin-1 (0xE9 = "é" is invalid UTF-8)
    // must be written back in Latin-1: untouched lines stay byte-identical,
    // per the byte-preservation contract in the FixEngine doc comment.

    func makeLatin1Scratch() throws -> (dir: URL, engine: FixEngine) {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDLatin1Tests-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("modifications.json")))
        return (dir, engine)
    }

    @Test func loadCenterPreservesLatin1Bytes() throws {
        let (dir, engine) = try makeLatin1Scratch()
        defer { try? FileManager.default.removeItem(at: dir) }

        let text = """
        A
        850
        DRAPED_POLYGON

        # Cr\u{E9}\u{E9} par l'a\u{E9}roport
        TEXTURE fa\u{E7}ade.png
        SCALE 25 25
        """
        let pol = dir.appendingPathComponent("apron.pol")
        let original = try #require(text.data(using: .isoLatin1))
        try original.write(to: pol)
        #expect(String(data: original, encoding: .utf8) == nil)

        let finding = Finding(
            checkID: "C-08", severity: .warning, category: .packageHealth,
            title: "t", detail: "d", path: pol.path,
            fixability: .auto,
            proposedFix: .insertLoadCenter(polPath: pol.path, latitude: 47.4, longitude: 8.5,
                                           sizeMeters: 120, resolutionPx: 2048)
        )
        let outcomes = engine.apply([finding])
        #expect(outcomes.first?.success == true, "\(outcomes.first?.message ?? "")")

        var expectedLines = text.components(separatedBy: "\n")
        let textureIndex = expectedLines.firstIndex { $0.hasPrefix("TEXTURE") }!
        expectedLines.insert("LOAD_CENTER 47.400000 8.500000 120 2048", at: textureIndex + 1)
        let expected = try #require(expectedLines.joined(separator: "\n").data(using: .isoLatin1))
        #expect(try Data(contentsOf: pol) == expected)
    }

    @Test func globalPromotionPreservesLatin1Bytes() throws {
        let (dir, engine) = try makeLatin1Scratch()
        defer { try? FileManager.default.removeItem(at: dir) }

        let text = """
        A
        800
        OBJ

        TEXTURE b\u{E2}timent.png
        POINT_COUNTS 2 0 0 3
        VT 0 0 0 0 1 0 0 0
        VT 1 1 1 0 1 0 0 0
        IDX 0
        ATTR_no_blend
        TRIS 0 3
        """
        let obj = dir.appendingPathComponent("hangar.obj")
        let original = try #require(text.data(using: .isoLatin1))
        try original.write(to: obj)
        #expect(String(data: original, encoding: .utf8) == nil)

        let finding = Finding(
            checkID: "C-06", severity: .warning, category: .packageHealth,
            title: "t", detail: "d", path: obj.path,
            fixability: .auto,
            proposedFix: .promoteGlobalNoBlend(objPath: obj.path)
        )
        let outcomes = engine.apply([finding])
        #expect(outcomes.first?.success == true, "\(outcomes.first?.message ?? "")")

        var expectedLines = text.components(separatedBy: "\n").filter { $0 != "ATTR_no_blend" }
        let trisIndex = expectedLines.firstIndex { $0.hasPrefix("TRIS") }!
        expectedLines.insert("GLOBAL_no_blend", at: trisIndex)
        let expected = try #require(expectedLines.joined(separator: "\n").data(using: .isoLatin1))
        #expect(try Data(contentsOf: obj) == expected)
    }

    @Test func controllerRepairPreservesLatin1Bytes() throws {
        let (dir, engine) = try makeLatin1Scratch()
        defer { try? FileManager.default.removeItem(at: dir) }

        let text = """
        I
        1200 Generated by test

        1    12 0 0 LFMN Nice C\u{F4}te d'Azur
        1054 372000 NICE TOUR C\u{D4}T\u{C9}

        99
        """
        let aptURL = dir.appendingPathComponent("apt.dat")
        let original = try #require(text.data(using: .isoLatin1))
        try original.write(to: aptURL)
        #expect(String(data: original, encoding: .utf8) == nil)

        var repairEngine = engine
        repairEngine.frequencyProvider = { _ in
            [LookedUpFrequency(codeSuffix: "4", khz: 118_700, label: "TWR", source: "AirNav")]
        }
        let finding = Finding(
            checkID: "LOG-91", severity: .warning, category: .packageHealth,
            title: "t", detail: "d",
            proposedFix: .repairControllerFrequencies(aptPath: aptURL.path, icao: "LFMN")
        )
        let outcomes = repairEngine.apply([finding])
        #expect(outcomes.first?.success == true, "\(outcomes.first?.message ?? "")")

        var expectedLines = text.components(separatedBy: "\n")
        let towerIndex = expectedLines.firstIndex { $0.hasPrefix("1054") }!
        expectedLines.insert("1054 118700 NICE TOUR C\u{D4}T\u{C9}", at: towerIndex + 1)
        let expected = try #require(expectedLines.joined(separator: "\n").data(using: .isoLatin1))
        #expect(try Data(contentsOf: aptURL) == expected)
    }

    @Test func heavyObjFindingCarriesSizedFix() {
        let fixture = Bundle.module.url(forResource: "Fixtures/FakeXP", withExtension: nil)!
        let installation = InstallationScanner(root: fixture).scan()
        let result = PackageHealthAnalyzer(installation: installation).analyze()
        let c02 = result.findings.first { $0.checkID == "C-02" }
        #expect(c02?.fixability == .auto)
        if case .addFarLOD(let path, let distance)? = c02?.proposedFix {
            #expect(path.hasSuffix("terminal.obj"))
            #expect(distance >= 300 && distance <= 15_000)
        } else {
            Issue.record("C-02 finding should carry an addFarLOD fix")
        }
    }
}
