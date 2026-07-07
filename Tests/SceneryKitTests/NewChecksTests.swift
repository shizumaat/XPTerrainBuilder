import Testing
import Foundation
@testable import SceneryKit

/// Coverage for the July-2026 check batch: spill radii (C-10 fixable),
/// dead-alpha DDS (C-18), apt.dat pavement lint (APT-01..03), and the
/// placement-count / exclusion / facade checks (C-09/C-15/C-16/C-17).
@Suite struct NewChecksTests {

    // MARK: - Spill radii (ObjParser + clamp fix)

    @Test func spillRadiusParsing() {
        let text = """
        A
        800
        OBJ

        LIGHT_SPILL_CUSTOM 1 2 3 1.0 0.9 0.8 1.0 85.5 0 -1 0 1.0 sim/graphics/animation/lights/airport_beacon
        LIGHT_SPILL_CUSTOM 1 2 3 1.0 0.9 0.8 1.0 12 0 -1 0 1.0 NULL
        LIGHT_PARAM full_custom_halo 10 0 10 1 1 1 1 95 0 -1 0 1
        LIGHT_PARAM taxi_b 10 0 10 1 0.5
        VT 0 0 0 0 1 0 0 0
        TRIS 0 1
        """
        let info = ObjParser.parse(text: text)
        #expect(info.spillLightCount == 4)
        // taxi_b's layout is unknown — its size must NOT be guessed.
        #expect(info.spillRadii.sorted() == [12, 85.5, 95])
        #expect(info.maxSpillRadius == 95)
        // Only the beacon light is dataref-driven; NULL doesn't count.
        #expect(info.datarefSpillCount == 1)
    }

    @Test func spillClampFixAndRevert() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDSpill-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let obj = dir.appendingPathComponent("apron_lights.obj")
        let original = """
        A
        800
        OBJ

        VT 0 0 0 0 1 0 0 0
        LIGHT_SPILL_CUSTOM 1 2 3 1.0 0.9 0.8 1.0 85.5 0 -1 0 1.0 NULL
        LIGHT_PARAM full_custom_halo 10 0 10 1 1 1 1 95 0 -1 0 1
        LIGHT_SPILL_CUSTOM 4 5 6 1.0 0.9 0.8 1.0 40 0 -1 0 1.0 NULL
        TRIS 0 1
        """
        try original.write(to: obj, atomically: true, encoding: .utf8)

        let finding = Finding(
            checkID: "C-10", severity: .warning, category: .packageHealth,
            title: "test", detail: "test",
            proposedFix: .reduceSpillRadius(objPath: obj.path, maxRadiusMeters: 60)
        )
        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        let outcomes = engine.apply([finding])
        #expect(outcomes.allSatisfy { $0.success }, "\(outcomes.map { $0.message ?? "" })")

        let after = ObjParser.parse(url: obj)!
        #expect(after.spillRadii.sorted() == [40, 60, 60], "oversized clamped, small one untouched")
        #expect(after.vertexCount == 1)

        // The in-bounds light's line must be byte-identical.
        let edited = try String(contentsOf: obj, encoding: .utf8)
        #expect(edited.contains("LIGHT_SPILL_CUSTOM 4 5 6 1.0 0.9 0.8 1.0 40 0 -1 0 1.0 NULL"))

        // Re-applying refuses (nothing exceeds the cap anymore).
        #expect(engine.apply([finding]).allSatisfy { !$0.success })

        // Revert restores byte-identical original.
        let reverts = engine.revert(engine.log.load())
        #expect(reverts.allSatisfy { $0.success })
        #expect(try String(contentsOf: obj, encoding: .utf8) == original)
    }

    @Test func spillClampSurvivesCRLF() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDSpillCRLF-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        // Windows-authored file: CRLF line endings throughout.
        let obj = dir.appendingPathComponent("crlf.obj")
        let original = "A\r\n800\r\nOBJ\r\n\r\nVT 0 0 0 0 1 0 0 0\r\n"
            + "LIGHT_PARAM full_custom_halo 10 0 10 1 1 1 1 95 0 -1 0 1\r\nTRIS 0 1\r\n"
        try Data(original.utf8).write(to: obj)

        let finding = Finding(
            checkID: "C-10", severity: .warning, category: .packageHealth,
            title: "t", detail: "t",
            proposedFix: .reduceSpillRadius(objPath: obj.path, maxRadiusMeters: 60))
        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        #expect(engine.apply([finding]).allSatisfy { $0.success })

        let edited = try String(contentsOf: obj, encoding: .utf8)
        #expect(edited.contains("1 1 1 1 60 0 -1 0 1\r\n"), "clamped line keeps its CRLF ending")
        #expect(edited.contains("VT 0 0 0 0 1 0 0 0\r\n"), "untouched lines keep CRLF")
        #expect(ObjParser.parse(url: obj)?.maxSpillRadius == 60)
    }

    // MARK: - Dead alpha (DDSAlpha + strip fix)

    /// 8×8 single-mip DXT5 with four hand-built blocks exercising every
    /// color-endpoint case the BC1 rewrite must handle.
    static func makeOpaqueDXT5() -> Data {
        var dds = DDSEncoder.header(width: 8, height: 8, mipCount: 1, dxt5: true)
        // Block A: a0=a1=255 (opaque via the <= mode palette), c0 > c1.
        dds.append(contentsOf: [255, 255, 0, 0, 0, 0, 0, 0])
        dds.append(contentsOf: [0x00, 0xF8, 0x00, 0x00, 0xE4, 0xE4, 0xE4, 0xE4])
        // Block B: c0 < c1 — needs endpoint swap + index remap.
        dds.append(contentsOf: [255, 255, 0, 0, 0, 0, 0, 0])
        dds.append(contentsOf: [0x00, 0x00, 0x00, 0xF8, 0x1B, 0x2C, 0x00, 0xFF])
        // Block C: c0 == c1 — BC1 3-color mode would make index 3 transparent.
        dds.append(contentsOf: [255, 255, 0, 0, 0, 0, 0, 0])
        dds.append(contentsOf: [0x21, 0x84, 0x21, 0x84, 0xFF, 0xFF, 0xFF, 0xFF])
        // Block D: a0 > a1 with a1 still opaque (fast path).
        dds.append(contentsOf: [255, 250, 0, 0, 0, 0, 0, 0])
        dds.append(contentsOf: [0x00, 0xF8, 0x1F, 0x00, 0x00, 0x00, 0x00, 0x00])
        return dds
    }

    @Test func deadAlphaStripConvertsOpaqueDXT5() throws {
        let dds = Self.makeOpaqueDXT5()
        #expect({ if case .opaqueBC3 = DDSAlpha.analyze(data: dds) { return true }; return false }())

        let stripped = try #require(DDSAlpha.stripToBC1(dds))
        #expect(stripped.count == 128 + 4 * 8)
        #expect(String(decoding: stripped[84..<88], as: UTF8.self) == "DXT1")

        // Block A copied verbatim.
        let blockA: [UInt8] = [0x00, 0xF8, 0x00, 0x00, 0xE4, 0xE4, 0xE4, 0xE4]
        #expect(Array(stripped[128..<136]) == blockA)
        // Block B: endpoints swapped, 2-bit indices remapped (XOR 0x55).
        let blockB: [UInt8] = [0x00, 0xF8, 0x00, 0x00,
                               0x1B ^ 0x55, 0x2C ^ 0x55, 0x00 ^ 0x55, 0xFF ^ 0x55]
        #expect(Array(stripped[136..<144]) == blockB)
        // Block C: equal endpoints, indices forced to 0 (index 3 would be
        // transparent in BC1's 3-color mode).
        let blockC: [UInt8] = [0x21, 0x84, 0x21, 0x84, 0, 0, 0, 0]
        #expect(Array(stripped[144..<152]) == blockC)
    }

    @Test func deadAlphaLeavesRealAlphaAlone() {
        var dds = DDSEncoder.header(width: 4, height: 4, mipCount: 1, dxt5: true)
        // a0=255 > a1=0, and pixel 0's index points at a1 (translucent).
        dds.append(contentsOf: [255, 0, 0b001, 0, 0, 0, 0, 0])
        dds.append(contentsOf: [0x00, 0xF8, 0x00, 0x00, 0, 0, 0, 0])
        #expect({ if case .hasRealAlpha = DDSAlpha.analyze(data: dds) { return true }; return false }())
        #expect(DDSAlpha.stripToBC1(dds) == nil)
    }

    @Test func deadAlphaFixEndToEnd() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDAlpha-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let dds = dir.appendingPathComponent("apron.dds")
        try Self.makeOpaqueDXT5().write(to: dds)

        let finding = Finding(
            checkID: "C-18", severity: .warning, category: .packageHealth,
            title: "test", detail: "test",
            proposedFix: .stripDeadAlpha(ddsPath: dds.path)
        )
        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        #expect(engine.apply([finding]).allSatisfy { $0.success })

        let info = try #require(TextureInspector.inspect(url: dds))
        #expect(info.ddsFourCC == "DXT1")
        #expect(info.width == 8 && info.height == 8)

        // Re-applying refuses (it's DXT1 now); revert restores the original.
        #expect(engine.apply([finding]).allSatisfy { !$0.success })
        #expect(engine.revert(engine.log.load()).allSatisfy { $0.success })
        #expect(try Data(contentsOf: dds) == Self.makeOpaqueDXT5())
    }

    // MARK: - apt.dat pavement lint

    static func square(_ code110Description: String, minLat: Double, minLon: Double,
                       side: Double) -> String {
        """
        110 1 0.25 0 \(code110Description)
        111 \(minLat) \(minLon)
        111 \(minLat + side) \(minLon)
        111 \(minLat + side) \(minLon + side)
        113 \(minLat) \(minLon + side)
        """
    }

    static func makeAptDat() -> String {
        var text = """
        I
        1200 Generated for test

        1 100 0 0 KTST Test Field
        1302 icao_code KTST

        """
        // Big apron with a smaller polygon fully inside it (layered pavement).
        text += square("Main Apron", minLat: 40.0, minLon: -75.0, side: 0.01) + "\n"
        text += square("Stacked Patch", minLat: 40.002, minLon: -74.998, side: 0.002) + "\n"
        // A polygon with excessive nodes (spiral of 305 points, closed).
        text += "110 1 0.25 0 Node Monster\n"
        for i in 0..<304 {
            let angle = Double(i) / 304 * 2 * Double.pi
            let r = 0.001 + Double(i) * 1e-7
            text += "111 \(40.05 + r * sin(angle)) \(-75.05 + r * cos(angle))\n"
        }
        text += "113 40.051 -75.05\n"
        // A linear feature whose nodes must NOT count as pavement.
        text += "120 centerline\n111 40.0 -75.0\n115 40.001 -75.001\n"
        return text
    }

    @Test func aptPavementParsing() {
        let polygons = AptDatAnalyzer.parsePavement(text: Self.makeAptDat())
        #expect(polygons.count == 3, "the 120 linear feature must not become a polygon")
        #expect(polygons.map { $0.airport } == ["KTST", "KTST", "KTST"])
        #expect(polygons[2].nodeCount == 305)
    }

    @Test func aptLintFindings() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDApt-\(UUID().uuidString)")
        let pack = dir.appendingPathComponent("Custom Scenery/Test Airport")
        try FileManager.default.createDirectory(
            at: pack.appendingPathComponent("Earth nav data"), withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }
        try Self.makeAptDat().write(
            to: pack.appendingPathComponent("Earth nav data/apt.dat"),
            atomically: true, encoding: .utf8)

        let sceneryPack = SceneryPack(
            name: "Test Airport", url: pack, status: .enabled, iniIndex: 0,
            isLibrary: false,
            airports: ["KTST": AirportInfo(name: "Test Field", latitude: 40, longitude: -75)],
            tiles: [], isOverlay: true, isLaminar: false)

        let findings = AptDatAnalyzer.scanPack(sceneryPack)
        let ids = findings.map { $0.checkID }
        #expect(ids.contains("APT-01"), "305-node polygon should be flagged: \(ids)")
        #expect(ids.contains("APT-03"), "stacked patch should be flagged: \(ids)")

        let overlap = findings.first { $0.checkID == "APT-03" }
        #expect(overlap?.severity == .warning)
        #expect(overlap?.detail.contains("Stacked Patch") == true)
        // The two big polygons only share edge territory — exactly one
        // layered pair must be reported.
        #expect(overlap?.title.contains("1 stacked polygon") == true)
    }

    // MARK: - Placement counts, exclusions, facade rings (synthetic DSF)

    /// Overlay tile placing one animated object 30× and one 120-node facade
    /// ring, with NO exclusion properties.
    static func makePlacementDSF() -> Data {
        typealias G = DSFGeometryTests
        var head = Data()
        head.append(G.atom("PROP", G.stringTable([
            "sim/overlay", "1",
            "sim/west", "-118", "sim/east", "-117", "sim/south", "32", "sim/north", "33",
        ])))

        var defn = Data()
        defn.append(G.atom("TERT", G.stringTable([])))
        defn.append(G.atom("OBJT", G.stringTable(["objects/tower.obj"])))
        defn.append(G.atom("POLY", G.stringTable(["facades/wall.fac"])))
        defn.append(G.atom("NETW", G.stringTable([])))

        // Pool of 130 raw-encoded points.
        let pointCount = 130
        var pool = Data()
        pool.append(G.u32(pointCount))
        pool.append(contentsOf: [2]) // depth
        pool.append(contentsOf: [0]) // lon plane raw
        for i in 0..<pointCount { pool.append(G.u16((i * 503) % 65536)) }
        pool.append(contentsOf: [0]) // lat plane raw
        for i in 0..<pointCount { pool.append(G.u16((i * 251) % 65536)) }
        var scal = Data()
        scal.append(G.f32(1.0)); scal.append(G.f32(-118))
        scal.append(G.f32(1.0)); scal.append(G.f32(32))

        var geod = Data()
        geod.append(G.atom("POOL", pool))
        geod.append(G.atom("SCAL", scal))

        var cmds = Data()
        cmds.append(contentsOf: [1]); cmds.append(G.u16(0)) // POOL SELECT 0
        cmds.append(contentsOf: [3, 0])                      // SET DEFINITION 0
        for i in 0..<30 {                                    // 30 object placements
            cmds.append(contentsOf: [7]); cmds.append(G.u16(i % pointCount))
        }
        // One facade ring with 120 nodes (POLYGON, param 0).
        cmds.append(contentsOf: [12]); cmds.append(G.u16(0))
        cmds.append(contentsOf: [120])
        for i in 0..<120 { cmds.append(G.u16(i)) }

        var dsf = Data("XPLNEDSF".utf8)
        dsf.append(G.u32(1))
        dsf.append(G.atom("HEAD", head))
        dsf.append(G.atom("DEFN", defn))
        dsf.append(G.atom("GEOD", geod))
        dsf.append(G.atom("CMDS", cmds))
        dsf.append(Data(repeating: 0, count: 16))
        return dsf
    }

    @Test func placementExclusionAndFacadeChecks() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDPlace-\(UUID().uuidString)")
        let pack = root.appendingPathComponent("Custom Scenery/Test Landmark")
        let fm = FileManager.default
        for sub in ["Earth nav data/+30-120", "objects", "facades"] {
            try fm.createDirectory(at: pack.appendingPathComponent(sub), withIntermediateDirectories: true)
        }
        defer { try? fm.removeItem(at: root) }

        try Self.makePlacementDSF()
            .write(to: pack.appendingPathComponent("Earth nav data/+30-120/+32-118.dsf"))
        try """
        A
        800
        OBJ

        TEXTURE tower.png
        VT 0 0 0 0 1 0 0 0
        VT 0 5 0 0 1 0 0 0
        ANIM_begin
        TRIS 0 2
        ANIM_end
        """.write(to: pack.appendingPathComponent("objects/tower.obj"), atomically: true, encoding: .utf8)
        try "A\n800\nFACADE\n".write(
            to: pack.appendingPathComponent("facades/wall.fac"), atomically: true, encoding: .utf8)

        let installation = InstallationScanner(root: root).scan()
        let scanned = try #require(installation.packs.first { $0.name == "Test Landmark" })
        #expect(scanned.kind == .landmark, "overlay DSF + no airports should classify as landmark")

        let result = PlacementAnalyzer(installation: installation).scanPack(scanned)
        let ids = result.findings.map { $0.checkID }

        let c09 = result.findings.first { $0.checkID == "C-09" }
        #expect(c09 != nil, "animated object placed 30x should be flagged: \(ids)")
        #expect(c09?.title.contains("30×") == true)
        #expect(c09?.severity == .info, "warning tier starts at 100 placements")

        let c15 = result.findings.first { $0.checkID == "C-15" }
        #expect(c15 != nil, "overlay with clutter and no exclusions should be flagged: \(ids)")

        let c16 = result.findings.first { $0.checkID == "C-16" }
        #expect(c16 != nil, "120-node facade ring should be flagged: \(ids)")
        #expect(c16?.title.contains("120") == true)
    }
}
