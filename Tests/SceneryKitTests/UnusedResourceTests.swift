import Testing
import Foundation
@testable import SceneryKit

@Suite struct UnusedResourceTests {

    // MARK: - Synthetic DSF construction

    static func atom(_ id: String, _ body: Data) -> Data {
        var data = Data(id.utf8)
        var length = Int32(body.count + 8).littleEndian
        withUnsafeBytes(of: &length) { data.append(contentsOf: $0) }
        data.append(body)
        return data
    }

    static func stringTable(_ strings: [String]) -> Data {
        var data = Data()
        for string in strings {
            data.append(Data(string.utf8))
            data.append(0)
        }
        return data
    }

    /// Minimal structurally-valid DSF: magic + version, DEFN atom with the
    /// given terrain/object tables, plus a dummy atom and a 16-byte footer.
    static func makeDSF(terrains: [String], objects: [String] = []) -> Data {
        var body = Data()
        body.append(atom("TERT", stringTable(terrains)))
        body.append(atom("OBJT", stringTable(objects)))

        var dsf = Data("XPLNEDSF".utf8)
        var version = Int32(1).littleEndian
        withUnsafeBytes(of: &version) { dsf.append(contentsOf: $0) }
        dsf.append(atom("DEFN", body))
        dsf.append(atom("XXXX", Data(repeating: 0xAB, count: 64))) // opaque atom to skip
        dsf.append(Data(repeating: 0, count: 16)) // fake md5 footer
        return dsf
    }

    @Test func dsfReaderParsesDefinitions() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDDSF-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let dsfURL = dir.appendingPathComponent("+47-123.dsf")
        try Self.makeDSF(
            terrains: ["terrain/12345_BI16.ter", "terrain_Water"],
            objects: ["objects/tower.obj", "lib/airport/thing.obj"]
        ).write(to: dsfURL)

        guard case .ok(let defs) = DSFReader.readDefinitions(url: dsfURL) else {
            Issue.record("expected .ok")
            return
        }
        #expect(defs.terrains == ["terrain/12345_BI16.ter", "terrain_Water"])
        #expect(defs.objects == ["objects/tower.obj", "lib/airport/thing.obj"])
    }

    @Test func dsfReaderHandles7z() throws {
        // Real 7z DSFs decode in-process (libarchive lives in the dyld cache
        // on every supported macOS; Global Forests ships 37k such tiles).
        #expect(SevenZip.available)

        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDDSF-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        // 7z magic followed by garbage is a corrupt archive, not "compressed".
        let url = dir.appendingPathComponent("corrupt.dsf")
        var data = Data([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C])
        data.append(Data(repeating: 0x42, count: 100))
        try data.write(to: url)
        guard case .invalid = DSFReader.readDefinitions(url: url) else {
            Issue.record("expected .invalid for a corrupt 7z archive")
            return
        }

        // A genuine 7z-wrapped DSF (bsdtar writes 7z via the same libarchive).
        let rawURL = dir.appendingPathComponent("+41-073.raw")
        try Self.makeDSF(terrains: ["terrain/live.ter"], objects: ["objects/a.obj"]).write(to: rawURL)
        let sevenURL = dir.appendingPathComponent("+41-073.dsf")
        let tar = Process()
        tar.executableURL = URL(fileURLWithPath: "/usr/bin/tar")
        tar.arguments = ["-cf", sevenURL.path, "--format", "7zip", "-C", dir.path, "+41-073.raw"]
        try tar.run()
        tar.waitUntilExit()
        try #require(tar.terminationStatus == 0)

        guard case .ok(let defs) = DSFReader.readDefinitions(url: sevenURL) else {
            Issue.record("expected .ok for a 7z-wrapped DSF")
            return
        }
        #expect(defs.terrains == ["terrain/live.ter"])
        #expect(defs.objects == ["objects/a.obj"])
    }

    @Test func parseAtomsHandlesTruncation() {
        let full = Self.makeDSF(terrains: ["terrain/a.ter"], objects: ["objects/b.obj"])
        let defs = DSFReader.parseAtoms(in: full)
        #expect(defs?.terrains == ["terrain/a.ter"])
        // Cut inside the DEFN atom: parse must fail (retry with more data),
        // never return a partial definition table as if complete.
        let truncated = full.prefix(20)
        #expect(DSFReader.parseAtoms(in: Data(truncated)) == nil)
    }

    // MARK: - Orphan detection

    /// Ortho pack with a live imagery set (GO16) and a leftover one (BI16):
    /// the DSF only references the GO16 .ter.
    func makeOrthoPack() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDUnused-\(UUID().uuidString)")
        let pack = root.appendingPathComponent("Custom Scenery/zOrtho Test")
        let fm = FileManager.default

        for sub in ["Earth nav data/+40-080", "terrain", "textures", "objects"] {
            try fm.createDirectory(at: pack.appendingPathComponent(sub), withIntermediateDirectories: true)
        }

        try Self.makeDSF(terrains: ["terrain/12345_GO16.ter"], objects: ["objects/pier.obj"])
            .write(to: pack.appendingPathComponent("Earth nav data/+40-080/+41-073.dsf"))

        // Live set. Note: .ter references .png while the file on disk is .dds
        // (X-Plane substitutes extensions) — must still count as referenced.
        try "A\n800\nTERRAIN\n\nBASE_TEX_NOWRAP ../textures/12345_GO16.png\n"
            .write(to: pack.appendingPathComponent("terrain/12345_GO16.ter"), atomically: true, encoding: .utf8)
        try Data(repeating: 1, count: 512)
            .write(to: pack.appendingPathComponent("textures/12345_GO16.dds"))

        // Leftover set: identical shape, but no DSF references its .ter.
        try "A\n800\nTERRAIN\n\nBASE_TEX_NOWRAP ../textures/12345_BI16.png\n"
            .write(to: pack.appendingPathComponent("terrain/12345_BI16.ter"), atomically: true, encoding: .utf8)
        try Data(repeating: 2, count: 2048)
            .write(to: pack.appendingPathComponent("textures/12345_BI16.dds"))

        // Object with its texture and _LIT companion — all alive.
        try "A\n800\nOBJ\n\nTEXTURE ../textures/pier.png\nVT 0 0 0 0 1 0 0 0\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/pier.obj"), atomically: true, encoding: .utf8)
        try Data(repeating: 3, count: 64).write(to: pack.appendingPathComponent("textures/pier.png"))
        try Data(repeating: 4, count: 64).write(to: pack.appendingPathComponent("textures/pier_LIT.png"))

        // Truly orphaned image + an excluded preview.
        try Data(repeating: 5, count: 4096).write(to: pack.appendingPathComponent("textures/leftover_scratch.png"))
        try Data(repeating: 6, count: 64).write(to: pack.appendingPathComponent("preview.png"))

        return root
    }

    @Test func orphanDetectionFindsLeftoverOrthoSet() throws {
        let root = try makeOrthoPack()
        defer { try? FileManager.default.removeItem(at: root) }

        let installation = InstallationScanner(root: root).scan()
        let (_, candidates) = ResourceAuditAnalyzer(installation: installation).analyze()
        // Candidates only become reportable after the every-pack cross-check.
        let groups = ResourceAuditAnalyzer.verifyUnused(candidates: candidates,
                                                        allPacks: installation.packs)

        #expect(groups.count == 1)
        let files = Set(groups[0].files.map { URL(fileURLWithPath: $0.path).lastPathComponent })
        #expect(files == ["12345_BI16.ter", "12345_BI16.dds", "leftover_scratch.png"], "\(files)")
        #expect(groups[0].totalBytes >= 2048 + 4096) // dds + png + the small .ter text
        let finding = ResourceAuditAnalyzer.unusedFinding(for: groups[0], packKind: .ortho)
        #expect(finding.checkID == "UNUSED-01")
        #expect(finding.category == .unusedResources)
    }

    @Test func crossPackReferenceProtectsCandidatesAndTheirChains() throws {
        let root = try makeOrthoPack()
        defer { try? FileManager.default.removeItem(at: root) }

        // A neighbor pack escapes into the ortho pack with a ../ reference to
        // the "leftover" .ter. Deleting that .ter — or its texture, which
        // only the .ter itself references — would break the neighbor.
        let neighbor = root.appendingPathComponent("Custom Scenery/Neighbor Overlay")
        try FileManager.default.createDirectory(at: neighbor.appendingPathComponent("objects"),
                                                withIntermediateDirectories: true)
        try "A\n800\nOBJ\n\nATTR_custom ../zOrtho Test/terrain/12345_BI16.ter\n"
            .write(to: neighbor.appendingPathComponent("objects/ref.obj"),
                   atomically: true, encoding: .utf8)

        let installation = InstallationScanner(root: root).scan()
        let orthoPack = installation.packs.first { $0.name == "zOrtho Test" }!
        let result = ResourceAuditAnalyzer(installation: installation).scanPack(orthoPack)
        let candidates = [result?.1].compactMap { $0 }
        let groups = ResourceAuditAnalyzer.verifyUnused(candidates: candidates,
                                                        allPacks: installation.packs)

        // The externally referenced .ter AND its texture chain survive; the
        // genuinely orphaned scratch file is still reported.
        let files = Set(groups.flatMap { $0.files.map { URL(fileURLWithPath: $0.path).lastPathComponent } })
        #expect(files == ["leftover_scratch.png"], "\(files)")
    }

    @Test func libraryExportsAreRootsEvenWithTabsAndAlternates() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDLibRoots-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: root) }
        let pack = root.appendingPathComponent("Custom Scenery/Tab Library")
        let fm = FileManager.default
        for sub in ["Earth nav data/+40-080", "objects", "textures"] {
            try fm.createDirectory(at: pack.appendingPathComponent(sub), withIntermediateDirectories: true)
        }
        try Self.makeDSF(terrains: ["terrain_Water"])
            .write(to: pack.appendingPathComponent("Earth nav data/+40-080/+41-073.dsf"))

        // Tab-separated + CRLF, exactly how simHeaven ships. The old space-
        // split parser dropped every line and flagged all exports unused.
        let library = "A\r\n800\r\nLIBRARY\r\n\r\nEXPORT_EXCLUDE\tsim/x.obj\tobjects/exported.obj\r\n"
        try Data(library.utf8).write(to: pack.appendingPathComponent("library.txt"))
        // Alternate config, activated by renaming — its exports count too.
        try "A\n800\nLIBRARY\n\nEXPORT sim/y.obj\tobjects/alt.obj\n"
            .write(to: pack.appendingPathComponent("library - orthos.txt"),
                   atomically: true, encoding: .utf8)

        try "A\n800\nOBJ\n\nTEXTURE ../textures/exp.png\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/exported.obj"),
                   atomically: true, encoding: .utf8)
        try Data(repeating: 1, count: 64).write(to: pack.appendingPathComponent("textures/exp.dds"))
        try "A\n800\nOBJ\n\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/alt.obj"),
                   atomically: true, encoding: .utf8)
        try Data(repeating: 2, count: 64).write(to: pack.appendingPathComponent("textures/orphan.png"))

        let installation = InstallationScanner(root: root).scan()
        let (_, candidates) = ResourceAuditAnalyzer(installation: installation).analyze()
        let groups = ResourceAuditAnalyzer.verifyUnused(candidates: candidates,
                                                        allPacks: installation.packs)
        let files = Set(groups.flatMap { $0.files.map { URL(fileURLWithPath: $0.path).lastPathComponent } })
        #expect(files == ["orphan.png"], "\(files)")
    }

    @Test func compressedDSFDisablesPackVerification() throws {
        let root = try makeOrthoPack()
        defer { try? FileManager.default.removeItem(at: root) }

        // Add one opaque (7z) DSF: the pack must be skipped, not guessed at.
        let pack = root.appendingPathComponent("Custom Scenery/zOrtho Test")
        var sevenZip = Data([0x37, 0x7A, 0xBC, 0xAF, 0x27, 0x1C])
        sevenZip.append(Data(repeating: 0, count: 64))
        try sevenZip.write(to: pack.appendingPathComponent("Earth nav data/+40-080/+42-073.dsf"))

        let installation = InstallationScanner(root: root).scan()
        let (findings, groups) = ResourceAuditAnalyzer(installation: installation).analyze()
        #expect(groups.isEmpty)
        #expect(findings.contains { $0.checkID == "UNUSED-00" })
    }

    @Test func cachedRunReusesUnchangedPacksAndCatchesChanges() throws {
        let root = try makeOrthoPack()
        defer { try? FileManager.default.removeItem(at: root) }
        let cacheURL = root.appendingPathComponent("cache.json")

        let first = Analyzer(root: root).run(options: .init(cacheURL: cacheURL))
        #expect(first.stats.packsFromCache == 0)
        #expect(!first.unusedResources.isEmpty)

        // Nothing changed: everything is served from the cache, results equal.
        let second = Analyzer(root: root).run(options: .init(cacheURL: cacheURL))
        #expect(second.stats.packsFromCache == 1)
        #expect(second.unusedResources.map { $0.files.count } == first.unusedResources.map { $0.files.count })
        #expect(Set(second.findings.map { $0.title }) == Set(first.findings.map { $0.title }))

        // A replaced DSF (in-place write, deep in Earth nav data) must
        // invalidate: the new tile references the leftover set, so the
        // "unused" files disappear.
        let pack = root.appendingPathComponent("Custom Scenery/zOrtho Test")
        try Self.makeDSF(terrains: ["terrain/12345_GO16.ter", "terrain/12345_BI16.ter"],
                         objects: ["objects/pier.obj"])
            .write(to: pack.appendingPathComponent("Earth nav data/+40-080/+41-073.dsf"))

        let third = Analyzer(root: root).run(options: .init(cacheURL: cacheURL))
        #expect(third.stats.packsFromCache == 0)
        let files = Set(third.unusedResources.flatMap { $0.files.map { ($0.path as NSString).lastPathComponent } })
        #expect(files == ["leftover_scratch.png"], "\(files)")

        // forceFresh bypasses a valid cache entry.
        let fourth = Analyzer(root: root).run(options: .init(forceFresh: ["zOrtho Test"], cacheURL: cacheURL))
        #expect(fourth.stats.packsFromCache == 0)
    }

    // MARK: - Trash + restore cycle

    @Test func trashAndRevertRoundTrip() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDTrash-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let victim = dir.appendingPathComponent("orphan.dds")
        let payload = Data(repeating: 0x77, count: 256)
        try payload.write(to: victim)

        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        let outcomes = engine.trashFiles([victim.path], checkID: "UNUSED-01", summary: "test trash")
        #expect(outcomes.allSatisfy { $0.success })
        #expect(!FileManager.default.fileExists(atPath: victim.path))

        let records = engine.log.load()
        #expect(records.count == 1)
        #expect(FileManager.default.fileExists(atPath: records[0].backupPath), "trashed copy should exist in Trash")

        let reverts = engine.revert(records)
        #expect(reverts.allSatisfy { $0.success })
        #expect(try Data(contentsOf: victim) == payload)
        #expect(engine.log.load().isEmpty)
    }

    // MARK: - Helpers

    @Test func pathNormalization() {
        #expect(ResourceAuditAnalyzer.normalize("terrain/../textures/Foo.DDS") == "textures/foo.dds")
        #expect(ResourceAuditAnalyzer.strippedKey("/a/b/Tex.PNG") == "a/b/tex")
        #expect(ResourceAuditAnalyzer.companionBase(of: "a/b/tex_lit") == "a/b/tex")
        #expect(ResourceAuditAnalyzer.companionBase(of: "a/b/tex") == nil)
    }
}
