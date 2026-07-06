import Testing
import Foundation
@testable import SceneryKit

@Suite struct DSFGeometryTests {

    // MARK: - Synthetic DSF with geometry

    static func atom(_ id: String, _ body: Data) -> Data {
        var data = Data(id.utf8)
        var length = Int32(body.count + 8).littleEndian
        withUnsafeBytes(of: &length) { data.append(contentsOf: $0) }
        data.append(body)
        return data
    }

    static func u16(_ value: Int) -> Data {
        var v = UInt16(value).littleEndian
        return withUnsafeBytes(of: &v) { Data($0) }
    }

    static func u32(_ value: Int) -> Data {
        var v = UInt32(value).littleEndian
        return withUnsafeBytes(of: &v) { Data($0) }
    }

    static func f32(_ value: Float) -> Data {
        var v = value.bitPattern.littleEndian
        return withUnsafeBytes(of: &v) { Data($0) }
    }

    static func stringTable(_ strings: [String]) -> Data {
        var data = Data()
        for s in strings { data.append(Data(s.utf8)); data.append(0) }
        return data
    }

    /// Tile +32-118 with one object def and one polygon def; a 16-bit pool
    /// of three points (raw-encoded lon/lat planes, SCAL 1.0/offset), an
    /// object placed at point 1 and a triangle winding over all three.
    static func makeGeometryDSF() -> Data {
        var head = Data()
        head.append(atom("PROP", stringTable([
            "sim/west", "-118", "sim/east", "-117", "sim/south", "32", "sim/north", "33",
        ])))

        var defn = Data()
        defn.append(atom("TERT", stringTable([])))
        defn.append(atom("OBJT", stringTable(["objects/tower.obj"])))
        defn.append(atom("POLY", stringTable(["polygons/apron.pol"])))
        defn.append(atom("NETW", stringTable([])))

        // Pool: 3 points, 2 planes, both raw (encoding 0).
        var pool = Data()
        pool.append(u32(3))
        pool.append(contentsOf: [2]) // depth
        pool.append(contentsOf: [0]) // plane 0 raw: lon fractions
        pool.append(u16(0)); pool.append(u16(32768)); pool.append(u16(65535))
        pool.append(contentsOf: [0]) // plane 1 raw: lat fractions
        pool.append(u16(65535)); pool.append(u16(32768)); pool.append(u16(0))
        var scal = Data()
        scal.append(f32(1.0)); scal.append(f32(-118)) // lon: raw/65535 + (-118)
        scal.append(f32(1.0)); scal.append(f32(32))   // lat: raw/65535 + 32

        var geod = Data()
        geod.append(atom("POOL", pool))
        geod.append(atom("SCAL", scal))

        var cmds = Data()
        cmds.append(contentsOf: [1]); cmds.append(u16(0))       // POOL SELECT 0
        cmds.append(contentsOf: [3, 0])                          // SET DEFINITION8 0 (object)
        cmds.append(contentsOf: [7]); cmds.append(u16(1))       // OBJECT at point 1
        cmds.append(contentsOf: [3, 0])                          // SET DEFINITION8 0 (polygon)
        cmds.append(contentsOf: [12]); cmds.append(u16(0))      // POLYGON param 0
        cmds.append(contentsOf: [3])                             // 3 indices
        cmds.append(u16(0)); cmds.append(u16(1)); cmds.append(u16(2))
        cmds.append(contentsOf: [32, 2, 0xAA, 0xBB])             // COMMENT8, skipped

        var dsf = Data("XPLNEDSF".utf8)
        dsf.append(u32(1)) // version
        dsf.append(atom("HEAD", head))
        dsf.append(atom("DEFN", defn))
        dsf.append(atom("GEOD", geod))
        dsf.append(atom("CMDS", cmds))
        dsf.append(Data(repeating: 0, count: 16)) // md5 footer
        return dsf
    }

    @Test func decodesPlacementsAndWindings() throws {
        let geo = try #require(DSFGeometryReader.parse(Self.makeGeometryDSF()))
        #expect(geo.definitions.objects == ["objects/tower.obj"])
        #expect(geo.definitions.polygons == ["polygons/apron.pol"])

        let placements = try #require(geo.objectPlacements[0])
        #expect(placements.count == 1)
        #expect(abs(placements[0].lon - (-117.5)) < 0.001)
        #expect(abs(placements[0].lat - 32.5) < 0.001)

        let windings = try #require(geo.polygonWindings[0])
        #expect(windings.count == 1)
        #expect(windings[0].count == 3)
        #expect(abs(windings[0][0].lon - (-118)) < 0.001)
        #expect(abs(windings[0][0].lat - 33) < 0.001)
        #expect(abs(windings[0][2].lon - (-117.0)) < 0.001)
    }

    @Test func rleAndDifferencedPlanesDecode() throws {
        // encoding 3 = RLE + differenced: repeat-run of 5 × delta 100
        // accumulates to 100, 200, 300, 400, 500.
        var pool = Data()
        pool.append(Self.u32(5))
        pool.append(contentsOf: [1])          // one plane
        pool.append(contentsOf: [3])          // RLE + differenced
        pool.append(contentsOf: [0x85])       // repeat run, 5 values
        pool.append(Self.u16(100))
        let planes = try #require(DSFGeometryReader.decodePlanes(pool, is32: false))
        #expect(planes[0] == [100, 200, 300, 400, 500])

        // Individual RLE run (high bit clear).
        var pool2 = Data()
        pool2.append(Self.u32(3))
        pool2.append(contentsOf: [1])
        pool2.append(contentsOf: [2])         // RLE, not differenced
        pool2.append(contentsOf: [3])         // individual run of 3
        pool2.append(Self.u16(7)); pool2.append(Self.u16(8)); pool2.append(Self.u16(9))
        let planes2 = try #require(DSFGeometryReader.decodePlanes(pool2, is32: false))
        #expect(planes2[0] == [7, 8, 9])
    }

    @Test func loadCenterFixInsertsAndReverts() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDLoadCenter-\(UUID().uuidString)")
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        defer { try? FileManager.default.removeItem(at: dir) }

        let pol = dir.appendingPathComponent("apron.pol")
        let original = "A\n850\nDRAPED_POLYGON\n\nTEXTURE_NOWRAP ortho.dds\nSCALE 100 100\n"
        try original.write(to: pol, atomically: true, encoding: .utf8)

        let finding = Finding(
            checkID: "C-13", severity: .warning, category: .performance,
            title: "test", detail: "test",
            proposedFix: .insertLoadCenter(polPath: pol.path, latitude: 32.71,
                                           longitude: -117.19, sizeMeters: 2350,
                                           resolutionPx: 4096)
        )
        let engine = FixEngine(log: ModificationLog(fileURL: dir.appendingPathComponent("mods.json")))
        let outcomes = engine.apply([finding])
        #expect(outcomes.allSatisfy { $0.success }, "\(outcomes.map { $0.message ?? "" })")

        let edited = try String(contentsOf: pol, encoding: .utf8)
        let lines = edited.components(separatedBy: "\n")
        let textureLine = lines.firstIndex { $0.hasPrefix("TEXTURE_NOWRAP") }!
        #expect(lines[textureLine + 1] == "LOAD_CENTER 32.710000 -117.190000 2350 4096")

        // Re-applying refuses (already present).
        let again = engine.apply([finding])
        #expect(again.allSatisfy { !$0.success })

        // Revert restores byte-identical original.
        let reverts = engine.revert(engine.log.load())
        #expect(reverts.allSatisfy { $0.success })
        #expect(try String(contentsOf: pol, encoding: .utf8) == original)
    }
}
