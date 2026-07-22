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
            isOverlay: entry.isOverlay,
            hasTerrain: entry.hasTerrain,
            isPhotoTextured: entry.isPhotoTextured)
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
