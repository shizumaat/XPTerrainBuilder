import Testing
import Foundation
@testable import SceneryKit

@Suite struct PathRepairTests {

    @Test func skeletonCollapsesNonASCIIRuns() {
        // One damaged char, two damaged chars, and the true spelling all
        // collapse to the same skeleton.
        #expect(PathRepair.skeleton("baños") == PathRepair.skeleton("ba§os"))
        #expect(PathRepair.skeleton("baños") == PathRepair.skeleton("baÃ±os"))
        // ASCII differences never collapse.
        #expect(PathRepair.skeleton("banda") != PathRepair.skeleton("bandy"))
    }

    @Test func matchingRules() {
        // Mojibake matches.
        #expect(PathRepair.matches(reference: "baños_2.obj", onDisk: "ba§os_2.obj"))
        #expect(PathRepair.matches(reference: "baños_2.obj", onDisk: "baÃ±os_2.obj"))
        // Case + NFD (decomposed ñ) match.
        #expect(PathRepair.matches(reference: "Baños.obj", onDisk: "ban\u{0303}os.obj"))
        // Pure-ASCII typos never match — that would be guessing.
        #expect(!PathRepair.matches(reference: "banos.obj", onDisk: "bands.obj"))
        #expect(!PathRepair.matches(reference: "banos.obj", onDisk: "baños.obj"))
    }

    @Test func resolveFindsMojibakeFile() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDPath-\(UUID().uuidString)")
        try FileManager.default.createDirectory(
            at: dir.appendingPathComponent("Modulos"), withIntermediateDirectories: true)
        let damaged = dir.appendingPathComponent("Modulos/ba§os_2.obj")
        try Data("x".utf8).write(to: damaged)
        defer { try? FileManager.default.removeItem(at: dir) }

        let resolution = PathRepair.resolve(relativePath: "Modulos/baños_2.obj", under: dir)
        #expect(resolution != nil)
        #expect(resolution?.isExact == false)
        #expect(resolution?.mismatches.count == 1)
        #expect(resolution?.mismatches.first?.expectedName == "baños_2.obj")
    }

    @Test func resolveRefusesAmbiguity() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDPath-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        // Two different damaged spellings both matching the reference.
        try Data("a".utf8).write(to: dir.appendingPathComponent("ba§os.obj"))
        try Data("b".utf8).write(to: dir.appendingPathComponent("baÂ§os.obj"))

        #expect(PathRepair.resolve(relativePath: "baños.obj", under: dir) == nil)
    }

    @Test func renameFixApplyAndRevert() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDRename-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let damaged = dir.appendingPathComponent("ba§os.obj")
        let corrected = dir.appendingPathComponent("baños.obj")
        try Data("payload".utf8).write(to: damaged)

        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        let finding = Finding(
            checkID: "LOG-08", severity: .error, category: .missingResource,
            title: "t", detail: "d", fixability: .auto,
            proposedFix: .renameFile(fromPath: damaged.path, toPath: corrected.path)
        )
        let outcomes = engine.apply([finding])
        #expect(outcomes.allSatisfy { $0.success }, "\(outcomes.map { $0.message ?? "" })")
        #expect(FileManager.default.fileExists(atPath: corrected.path))
        #expect(!FileManager.default.fileExists(atPath: damaged.path))

        let reverts = engine.revert(engine.log.load())
        #expect(reverts.allSatisfy { $0.success })
        #expect(FileManager.default.fileExists(atPath: damaged.path))
        #expect(!FileManager.default.fileExists(atPath: corrected.path))
    }
}
