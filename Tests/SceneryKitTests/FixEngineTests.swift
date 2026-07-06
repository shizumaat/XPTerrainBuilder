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
