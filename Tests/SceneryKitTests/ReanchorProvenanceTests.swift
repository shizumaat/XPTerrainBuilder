import Testing
import Foundation
@testable import SceneryKit

@Suite struct ReanchorProvenanceTests {
    /// A throwaway pack folder with one reseated object (live + backup)
    /// and a version-1 sidecar recording it for tile +46+008.
    func makePack(sidecar: String?) throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("reanchor-\(UUID().uuidString)")
        let objDir = root.appendingPathComponent("objects")
        try FileManager.default.createDirectory(at: objDir,
                                                withIntermediateDirectories: true)
        try "VT 0 5.0 0\n".write(to: objDir.appendingPathComponent("tower.obj"),
                                 atomically: true, encoding: .utf8)
        try "VT 0 0.0 0\n".write(
            to: objDir.appendingPathComponent("tower.obj.anchor_bak"),
            atomically: true, encoding: .utf8)
        if let sidecar {
            try sidecar.write(
                to: root.appendingPathComponent(ReanchorProvenance.sidecarName),
                atomically: true, encoding: .utf8)
        }
        return root
    }

    @Test func readsVersion1SidecarKeyedByTile() throws {
        let root = try makePack(sidecar: """
        {"version": 1, "meshes": {}, "objects": {
            "objects/tower.obj": {"tile": "+46+008", "anchor": [46.5, 8.4]},
            "objects/hangar.obj": {"tile": "+46+007"}
        }}
        """)
        defer { try? FileManager.default.removeItem(at: root) }
        let mods = try #require(ReanchorProvenance.read(packRoot: root))
        #expect(mods.objectsByTile["+46+008"] == ["objects/tower.obj"])
        #expect(mods.objectsByTile["+46+007"] == ["objects/hangar.obj"])
    }

    @Test func readsPrototypeSidecarDerivingTileFromMeshPath() throws {
        let root = try makePack(sidecar: """
        {"mesh": "/x/Data+35-081.mesh", "objects": ["objects/tower.obj"]}
        """)
        defer { try? FileManager.default.removeItem(at: root) }
        let mods = try #require(ReanchorProvenance.read(packRoot: root))
        #expect(mods.objectsByTile["+35-081"] == ["objects/tower.obj"])
    }

    @Test func noSidecarReadsAsNil() throws {
        let root = try makePack(sidecar: nil)
        defer { try? FileManager.default.removeItem(at: root) }
        #expect(ReanchorProvenance.read(packRoot: root) == nil)
    }

    @Test func restorePutsBackupsBackAndRemovesSidecar() throws {
        let root = try makePack(sidecar: """
        {"version": 1, "objects": {"objects/tower.obj": {"tile": "+46+008"}}}
        """)
        defer { try? FileManager.default.removeItem(at: root) }
        // An orphaned relic must survive untouched.
        let orphan = root.appendingPathComponent(
            "objects/other.obj.anchor_bak.orphaned")
        try "relic\n".write(to: orphan, atomically: true, encoding: .utf8)

        let restored = try ReanchorProvenance.restore(packRoot: root)
        #expect(restored == 1)
        let live = try String(contentsOf:
            root.appendingPathComponent("objects/tower.obj"), encoding: .utf8)
        #expect(live == "VT 0 0.0 0\n")
        // Backup stays (the next bake adopts it); sidecar is gone.
        #expect(FileManager.default.fileExists(atPath:
            root.appendingPathComponent("objects/tower.obj.anchor_bak").path))
        #expect(!FileManager.default.fileExists(atPath:
            root.appendingPathComponent(ReanchorProvenance.sidecarName).path))
        #expect(FileManager.default.fileExists(atPath: orphan.path))
    }
}
