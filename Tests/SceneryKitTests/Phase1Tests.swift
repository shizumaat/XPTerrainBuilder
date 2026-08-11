import Testing
import Foundation
@testable import SceneryKit

@Suite struct Phase1Tests {

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

    /// Minimal structurally-valid DSF: magic + version, an optional HEAD
    /// property atom, a DEFN atom with the given terrain/object tables, and
    /// the 16-byte footer.
    static func makeDSF(terrains: [String] = [], objects: [String] = [],
                        properties: [String: String] = [:]) -> Data {
        var body = Data()
        body.append(atom("TERT", stringTable(terrains)))
        body.append(atom("OBJT", stringTable(objects)))

        var dsf = Data("XPLNEDSF".utf8)
        var version = Int32(1).littleEndian
        withUnsafeBytes(of: &version) { dsf.append(contentsOf: $0) }
        if !properties.isEmpty {
            var propStrings: [String] = []
            for (key, value) in properties { propStrings.append(key); propStrings.append(value) }
            dsf.append(atom("HEAD", atom("PROP", stringTable(propStrings))))
        }
        dsf.append(atom("DEFN", body))
        dsf.append(Data(repeating: 0, count: 16))
        return dsf
    }

    /// An install with an installed overlay pack (DSF carrying sim/overlay)
    /// and an uninstalled pack that has an apt.dat.
    func makeInstall() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("XPSDPhase1-\(UUID().uuidString)")
        let fm = FileManager.default
        let pack = root.appendingPathComponent("Custom Scenery/Test Airport")

        for sub in ["Earth nav data/+40-080", "objects", "textures"] {
            try fm.createDirectory(at: pack.appendingPathComponent(sub), withIntermediateDirectories: true)
        }

        try Self.makeDSF(
            objects: ["objects/good.obj"],
            properties: ["sim/overlay": "1"]
        ).write(to: pack.appendingPathComponent("Earth nav data/+40-080/+41-073.dsf"))

        try "A\n800\nOBJ\n\nTEXTURE ../textures/good.png\nVT 0 0 0 0 1 0 0 0\nTRIS 0 1\n"
            .write(to: pack.appendingPathComponent("objects/good.obj"), atomically: true, encoding: .utf8)
        try Data(repeating: 1, count: 64).write(to: pack.appendingPathComponent("textures/good.png"))

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

    @Test func uninstalledPacksScannedWithStatus() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }

        let installation = InstallationScanner(root: root).scan()
        let shelved = installation.packs.first { $0.name == "Shelved Pack" }
        #expect(shelved?.status == .uninstalled)
        #expect(shelved?.airports["KPDX"] != nil)
        #expect(installation.packs.first { $0.name == "Test Airport" }?.status == .enabled)
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

    @Test func tileMathRoundTrips() {
        #expect(TileMath.key(lat: 41, lon: -73) == "+41-073")
        #expect(TileMath.key(lat: -9, lon: 8) == "-09+008")
        #expect(TileMath.key(latitude: 47.46, longitude: -122.31) == "+47-123")
        #expect(TileMath.parse("+41-073")! == (41, -73))
        #expect(TileMath.parse("-09+008")! == (-9, 8))
        #expect(TileMath.parse("garbage") == nil)
        // Malformed keys the persisted selection can hand back: empty,
        // a foreign spelling, an out-of-range latitude.
        #expect(TileMath.parse("") == nil)
        #expect(TileMath.parse("35,-81") == nil)
        #expect(TileMath.parse("+91-000") == nil)
        // Round trip every plausible tile format.
        for (lat, lon) in [(0, 0), (89, 179), (89, -180), (-90, -180), (-1, -1)] {
            let key = TileMath.key(lat: lat, lon: lon)
            let parsed = TileMath.parse(key)
            #expect(parsed?.lat == lat && parsed?.lon == lon, "\(key)")
        }
    }
}
