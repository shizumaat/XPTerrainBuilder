import Testing
import Foundation
@testable import SceneryKit

@Suite struct SceneryIndexCacheTests {
    /// Build a minimal install: one pack with an apt.dat and a dummy DSF.
    func makeInstall() throws -> URL {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("scenery-index-\(UUID().uuidString)")
        let pack = root.appendingPathComponent("Custom Scenery/Test Airport/Earth nav data/+10+010")
        try FileManager.default.createDirectory(at: pack, withIntermediateDirectories: true)
        try Data("DSF-not-really".utf8)
            .write(to: pack.appendingPathComponent("+11+011.dsf"))
        let apt = """
        I
        1100 Version
        1 433 0 0 XTST Test Field
        1302 datum_lat 10.5
        1302 datum_lon 10.5
        99
        """
        try Data(apt.utf8).write(to: pack.deletingLastPathComponent()
            .appendingPathComponent("apt.dat"))
        return root
    }

    @Test func cacheReuseAndInvalidation() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }
        let scanner = InstallationScanner(root: root)

        // Cold scan: probes fully, emits a cache entry.
        let cold = scanner.scan(cache: [:])
        let pack = try #require(cold.installation.packs.first)
        #expect(pack.airports.keys.contains("XTST"))
        let entry = try #require(cold.cache[pack.url.path])
        #expect(entry.airports.keys.contains("XTST"))

        // Warm scan with a POISONED cache entry (same signature): the marker
        // surviving proves the probe was skipped and the cache used.
        var poisoned = cold.cache
        poisoned[pack.url.path] = SceneryIndexCache.CachedProbe(
            signature: entry.signature,
            airports: ["ZZZZ": AirportInfo(name: "Marker", latitude: 0, longitude: 1)],
            tiles: entry.tiles,
            isLibrary: entry.isLibrary,
            isOverlay: entry.isOverlay,
            hasTerrain: entry.hasTerrain,
            isPhotoTextured: entry.isPhotoTextured,
            hasPlugins: entry.hasPlugins,
            sizeBytes: entry.sizeBytes,
            modifiedDate: entry.modifiedDate)
        let warm = scanner.scan(cache: poisoned)
        #expect(warm.installation.packs.first?.airports.keys.contains("ZZZZ") == true)

        // Change the pack (different apt.dat size): signature moves, the
        // poisoned entry is ignored, and a fresh probe finds the airport.
        try Data("I\n1100 Version\n1 433 0 0 XTST Test Field Renamed\n99\n".utf8)
            .write(to: pack.url.appendingPathComponent("Earth nav data/apt.dat"))
        let rescan = scanner.scan(cache: poisoned)
        #expect(rescan.installation.packs.first?.airports.keys.contains("XTST") == true)
        #expect(rescan.installation.packs.first?.airports.keys.contains("ZZZZ") == false)
    }

    /// Optimistic launch: the pack list rebuilt from cache alone must match
    /// what the scan produced — airports, tiles, and status included.
    @Test func packsFromCacheMatchesScan() throws {
        let root = try makeInstall()
        defer { try? FileManager.default.removeItem(at: root) }
        let scanner = InstallationScanner(root: root)
        let cold = scanner.scan(cache: [:])
        let scanned = try #require(cold.installation.packs.first)

        let rebuilt = scanner.packsFromCache(cold.cache)
        let pack = try #require(rebuilt.first)
        #expect(rebuilt.count == cold.installation.packs.count)
        #expect(pack.name == scanned.name)
        #expect(pack.status == scanned.status)
        #expect(pack.airports.keys.contains("XTST"))
        #expect(pack.tiles == scanned.tiles)
        #expect(pack.sizeBytes == scanned.sizeBytes)

        // An empty cache yields nothing (cold start falls back to streaming).
        #expect(scanner.packsFromCache([:]).isEmpty)
    }

    @Test func packObjectProbeFindsObjectsOutsideEarthNavData() throws {
        let pack = FileManager.default.temporaryDirectory
            .appendingPathComponent("objprobe-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: pack) }
        let objects = pack.appendingPathComponent("objects")
        try FileManager.default.createDirectory(at: objects, withIntermediateDirectories: true)
        #expect(!PackObjectProbe.hasCustomObjects(at: pack))
        // A DSF-named .obj inside Earth nav data must not count.
        let nav = pack.appendingPathComponent("Earth nav data")
        try FileManager.default.createDirectory(at: nav, withIntermediateDirectories: true)
        try Data("x".utf8).write(to: nav.appendingPathComponent("stray.obj"))
        #expect(!PackObjectProbe.hasCustomObjects(at: pack))
        try Data("OBJ".utf8).write(to: objects.appendingPathComponent("tower.obj"))
        #expect(PackObjectProbe.hasCustomObjects(at: pack))
    }

    @Test func tileTextureAuditFlagsForeignSources() throws {
        let dir = FileManager.default.temporaryDirectory
            .appendingPathComponent("texaudit-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: dir) }
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        for name in ["130768_135904_Arc18.dds", "130768_135920_Arc18.dds",
                     "130768_135904_BI16.dds",
                     "130768_135904_USA_216.dds",   // provider ending in a digit
                     "130768_135904_ZL18.png",      // water mask — not a source
                     "unrelated.txt"] {
            try Data("x".utf8).write(to: dir.appendingPathComponent(name))
        }
        let audit = try #require(TileTextureAudit.scan(texturesDir: dir, currentProvider: "Arc"))
        #expect(audit.hasConflict)
        #expect(audit.sources.map(\.provider).sorted() == ["Arc", "BI", "USA_2"])
        #expect(audit.foreignFiles.count == 2)
        #expect(audit.foreignSources.map(\.provider).sorted() == ["BI", "USA_2"])
        // Same provider only → no conflict.
        let clean = try #require(TileTextureAudit.scan(
            texturesDir: dir, currentProvider: "arc"))
        #expect(clean.sources.contains { $0.provider == "Arc" })
        // Unknown current provider → no audit.
        #expect(TileTextureAudit.scan(texturesDir: dir, currentProvider: "") == nil)

        // Names-only fast path (map badge sweep) agrees with the full scan.
        #expect(TileTextureAudit.hasForeignSources(texturesDir: dir, currentProvider: "Arc"))
        #expect(!TileTextureAudit.hasForeignSources(texturesDir: dir, currentProvider: ""))
        let single = dir.appendingPathComponent("single")
        try FileManager.default.createDirectory(at: single, withIntermediateDirectories: true)
        try Data("x".utf8).write(to: single.appendingPathComponent("1_2_Arc18.dds"))
        #expect(!TileTextureAudit.hasForeignSources(texturesDir: single, currentProvider: "Arc"))
    }

    @Test func persistRoundTripAndRootMismatch() throws {
        let root = try makeInstall()
        defer {
            try? FileManager.default.removeItem(at: root)
            try? FileManager.default.removeItem(at: SceneryIndexCache.cacheURL(for: root))
        }
        let scanned = InstallationScanner(root: root).scan(cache: [:])
        SceneryIndexCache.save(scanned.cache, for: root)
        let loaded = SceneryIndexCache.load(for: root)
        #expect(loaded.count == scanned.cache.count)
        // A different root must not see this cache.
        #expect(SceneryIndexCache.load(
            for: root.appendingPathComponent("elsewhere")).isEmpty)
    }
}
