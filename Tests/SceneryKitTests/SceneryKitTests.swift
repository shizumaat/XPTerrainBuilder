import Testing
import Foundation
@testable import SceneryKit

@Suite struct SceneryKitTests {

    var fixtureRoot: URL {
        guard let url = Bundle.module.url(forResource: "Fixtures/FakeXP", withExtension: nil) else {
            fatalError("FakeXP fixture missing from test bundle")
        }
        return url
    }

    func scannedInstallation() -> Installation {
        InstallationScanner(root: fixtureRoot).scan()
    }

    // MARK: Installation scanning

    @Test func scannerFindsPacksAndLibrary() {
        let installation = scannedInstallation()
        #expect(installation.packs.count == 3)
        let library = installation.packs.first { $0.name == "OpenSceneryX" }
        #expect(library?.isLibrary == true)
        #expect(installation.libraryIndex.exportCount == 4)
    }

    @Test func aptDatParsing() {
        let installation = scannedInstallation()
        let demo = installation.packs.first { $0.name == "KSEA Demo Airport" }
        #expect(demo?.airports["KSEA"]?.name == "Seattle Tacoma Intl")
        // Position from the runway row (no datum rows in the fixture).
        #expect(abs((demo?.airports["KSEA"]?.latitude ?? 0) - 47.46) < 0.01)
        #expect(abs((demo?.airports["KSEA"]?.longitude ?? 0) - (-122.30)) < 0.01)
        #expect(demo?.iniIndex == 0)
        #expect(demo?.isEnabled == true)
    }

    // MARK: Library index

    @Test func caseInsensitiveMatch() {
        let index = scannedInstallation().libraryIndex
        let match = index.caseInsensitiveMatch(for: "opensceneryx/objects/airport/vehicles/Fuel_Truck.obj")
        #expect(match?.virtualPath == "opensceneryx/objects/airport/vehicles/fuel_truck.obj")
    }

    @Test func nearestExportsCatchesTypo() {
        let index = scannedInstallation().libraryIndex
        let near = index.nearestExports(to: "opensceneryx/objects/airport/vehicles/bagage_cart.obj")
        #expect(near.first?.virtualPath == "opensceneryx/objects/airport/vehicles/baggage_cart.obj")
    }

    @Test func editDistance() {
        #expect(LibraryIndex.editDistance("kitten", "sitting", max: 5) == 3)
        #expect(LibraryIndex.editDistance("same", "same", max: 2) == 0)
        #expect(LibraryIndex.editDistance("short", "muchlongerstring", max: 3) > 3)
    }

    @Test func packKindIsContentFirst() {
        func pack(_ name: String, overlay: Bool?, terrain: Bool = false,
                  photo: Bool = false) -> SceneryPack {
            SceneryPack(name: name, url: URL(fileURLWithPath: "/tmp/\(name)"),
                        status: .enabled, iniIndex: 0, isLibrary: false, airports: [:],
                        tiles: ["+36-002"], isOverlay: overlay, isLaminar: false,
                        signature: "", hasTerrain: terrain, isPhotoTextured: photo)
        }
        // z_SpainUHDv2: ortho tiles with no "ortho" in the name, photo .dds
        // beside each .ter in terrain/, and (until 7z support) an unreadable
        // sample DSF — content must classify it, not the name.
        #expect(pack("z_SpainUHDv2_+36-002", overlay: nil, terrain: true, photo: true).kind == .ortho)
        #expect(pack("z_SpainUHDv2_+36-002", overlay: false, terrain: true, photo: true).kind == .ortho)
        // Elevation mesh: .ter but only a handful of textures.
        #expect(pack("UHD Mesh Scenery v4", overlay: false, terrain: true).kind == .mesh)
        // Name breaks the tie for small ortho tile packs.
        #expect(pack("zOrtho4XP_+41-073", overlay: false, terrain: true).kind == .ortho)
        // Overlays without terrain are landmarks; base mesh without .ter is mesh.
        #expect(pack("SFD Golden Gate", overlay: true).kind == .landmark)
        #expect(pack("Some Base", overlay: false).kind == .mesh)
        // Unknown overlay flag, no content signals: name hint or landmark.
        #expect(pack("Some Mesh Pack", overlay: nil).kind == .mesh)
        #expect(pack("Mystery Overlay", overlay: nil).kind == .landmark)
    }

    // MARK: Log parsing + diagnosis

    @Test func logParserExtractsMissingResources() throws {
        let text = try String(contentsOf: fixtureRoot.appendingPathComponent("Log.txt"), encoding: .utf8)
        let scan = LogAnalyzer.parseLog(text: text)
        #expect(scan.missing.count == 6)
        #expect(scan.missing.first?.virtualPath == "opensceneryx/objects/airport/vehicles/Fuel_Truck.obj")
        #expect(scan.missing.first?.referencedFrom == "KSEA Demo Airport")
        #expect(!scan.otherSceneryErrors.isEmpty) // the E/DSF line
    }

    @Test func diagnosisBuckets() {
        let installation = scannedInstallation()
        let (findings, _) = LogAnalyzer(installation: installation).analyze()
        let ids = findings.map { $0.checkID }

        #expect(ids.contains("LOG-01"), "case mismatch should be detected: \(ids)")
        #expect(ids.contains("LOG-04"), "typo should be detected: \(ids)")
        #expect(ids.contains("LOG-06"), "known missing library should be detected: \(ids)")
        #expect(ids.contains("LOG-07"), "unknown missing library should be detected: \(ids)")
        #expect(ids.contains("LOG-02"), "broken export (file absent) should be detected: \(ids)")
        #expect(ids.contains("LOG-08"), "mojibake filename should be detected: \(ids)")

        let mojibake = findings.first { $0.checkID == "LOG-08" }
        #expect(mojibake?.fixability == .auto)
        if case .renameFile(let from, let to)? = mojibake?.proposedFix {
            #expect(URL(fileURLWithPath: to).lastPathComponent == "señal_1.obj")
            #expect(from.contains("se"))
        } else {
            Issue.record("LOG-08 should carry a renameFile fix")
        }

        let known = findings.first { $0.checkID == "LOG-06" }
        #expect(known?.url?.absoluteString.contains("x-plane.org") == true)
    }

    // MARK: Duplicates

    @Test func duplicateAirportDetection() throws {
        let installation = scannedInstallation()
        let (findings, _) = DuplicateAnalyzer(installation: installation).analyze()
        let dup = try #require(findings.first { $0.checkID == "DUP-01" })
        #expect(dup.title.contains("KSEA"))
        #expect(dup.detail.contains("KSEA Demo Airport"), "winner should be the higher-priority pack")
        #expect(dup.severity == .warning)
    }

    // MARK: OBJ parsing + health checks

    @Test func objParser() {
        let text = """
        A
        800
        OBJ

        TEXTURE tex.png
        ATTR_no_blend
        VT 0 0 0 0 0 1 0 0
        VT 0 0 0 0 0 1 0 0
        ATTR_LOD 0 2000
        TRIS 0 2
        """
        let info = ObjParser.parse(text: text)
        #expect(info.vertexCount == 2)
        #expect(info.hasLOD)
        #expect(info.textures == ["tex.png"])
        #expect(info.perMeshNoBlend == 1)
    }

    @Test func blendPingPongCounting() {
        let text = """
        ATTR_no_blend
        TRIS 0 3
        ATTR_blend
        TRIS 3 3
        ATTR_no_blend
        TRIS 6 3
        ATTR_blend
        TRIS 9 3
        """
        let info = ObjParser.parse(text: text)
        #expect(info.blendStateChanges == 3)
    }

    @Test func healthChecksFireOnFixture() {
        let installation = scannedInstallation()
        let result = PackageHealthAnalyzer(installation: installation).analyze()
        let ids = result.findings.map { $0.checkID }
        #expect(ids.contains("C-02"), "heavy no-LOD OBJ should be flagged: \(ids)")
        #expect(ids.contains("C-03"), "promotable ATTR_no_blend should be flagged: \(ids)")
        #expect(ids.contains("C-04"), "oversized texture should be flagged: \(ids)")
    }

    @Test func textureInspectorPNG() {
        let png = fixtureRoot.appendingPathComponent("Custom Scenery/KSEA Demo Airport/objects/big_texture.png")
        let info = TextureInspector.inspect(url: png)
        #expect(info?.format == .png)
        #expect(info?.width == 8192)
        #expect(info?.height == 100)
        #expect(info?.isPowerOfTwo == false)
    }

    // MARK: End-to-end

    @Test func streamingEventsMatchFinalReport() {
        final class EventLog: @unchecked Sendable {
            let lock = NSLock()
            var findings: [Finding] = []
            var stages: [String] = []
            var groups: [DuplicateGroup] = []
        }
        let log = EventLog()

        let report = Analyzer(root: fixtureRoot).run { event in
            log.lock.lock()
            defer { log.lock.unlock() }
            switch event {
            case .findings(let new): log.findings.append(contentsOf: new)
            case .stage(let stage): log.stages.append(stage.label)
            case .duplicateGroups(let groups): log.groups = groups
            case .unusedResources, .packSizes: break
            }
        }

        // Every finding was streamed, and nothing extra.
        #expect(Set(log.findings.map { $0.id }) == Set(report.findings.map { $0.id }))
        #expect(log.groups.map { $0.icao } == report.duplicateGroups.map { $0.icao })
        #expect(log.stages.first?.contains("Scanning") == true)
        #expect(log.stages.last == "Done")
    }

    @Test func fullAnalyzerRun() throws {
        let report = Analyzer(root: fixtureRoot).run()
        #expect(report.findings.count > 5)
        #expect(report.stats.packsScanned == 3)
        #expect(report.errorCount > 0)

        // Findings sorted errors-first.
        let severities = report.findings.map { $0.severity }
        #expect(severities == severities.sorted())

        // JSON round-trips.
        let data = try report.jsonData()
        let object = try JSONSerialization.jsonObject(with: data) as? [String: Any]
        #expect(object?["findings"] != nil)
    }
}
