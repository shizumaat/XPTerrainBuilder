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

    /// A tile folder's `textures/` under `root/name`, with an empty
    /// `terrain/` beside it (the audit needs one to make a call).
    private func tileTextures(_ root: URL, _ name: String) throws -> URL {
        let tile = root.appendingPathComponent(name, isDirectory: true)
        try FileManager.default.createDirectory(
            at: tile.appendingPathComponent("terrain"), withIntermediateDirectories: true)
        let textures = tile.appendingPathComponent("textures", isDirectory: true)
        try FileManager.default.createDirectory(at: textures, withIntermediateDirectories: true)
        return textures
    }

    @Test func tileTextureAuditFlagsForeignSources() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("texaudit-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: root) }
        let dir = try tileTextures(root, "a")
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

        // Combined aggregation over several tiles: conflicted tiles only,
        // in-use vs unused split, providers collapse to sets.
        let cleanDir = try tileTextures(root, "clean")
        try Data("xx".utf8).write(to: cleanDir.appendingPathComponent("1_2_BI16.dds"))
        let a = try #require(TileTextureAudit.scan(texturesDir: dir, currentProvider: "Arc"))
        let b = try #require(TileTextureAudit.scan(texturesDir: cleanDir, currentProvider: "BI"))
        let combined = TileTextureAudit.Combined([a, b])
        #expect(combined.tilesAudited == 2)
        #expect(combined.tilesWithConflict == 1)
        #expect(combined.currentProviders == ["Arc"])
        #expect(combined.foreignProviders == ["BI", "USA_2"])
        #expect(combined.foreignFiles.count == a.foreignFiles.count)
        #expect(combined.currentBytes == 2 && combined.foreignBytes == 2)

        // Names-only fast path (map badge sweep) agrees with the full scan.
        #expect(TileTextureAudit.hasForeignSources(texturesDir: dir, currentProvider: "Arc"))
        #expect(!TileTextureAudit.hasForeignSources(texturesDir: dir, currentProvider: ""))
        let single = try tileTextures(root, "single")
        try Data("x".utf8).write(to: single.appendingPathComponent("1_2_Arc18.dds"))
        #expect(!TileTextureAudit.hasForeignSources(texturesDir: single, currentProvider: "Arc"))
    }

    /// 2026-10-25: a stale cfg said NZ while the tile's terrain named Arc;
    /// the Arc textures were offered as unused and went to the Trash. A
    /// texture the terrain names is never foreign; no terrain, no call.
    @Test func tileTextureAuditNeverOffersTexturesTheTerrainUses() throws {
        let root = FileManager.default.temporaryDirectory
            .appendingPathComponent("texaudit-\(UUID().uuidString)")
        defer { try? FileManager.default.removeItem(at: root) }
        let textures = try tileTextures(root, "tile")
        let terrain = textures.deletingLastPathComponent().appendingPathComponent("terrain")
        for name in ["163856_259008_Arc18.ter", "163856_259008_Arc18_sea_overlay.ter",
                     "163872_259024_Arc16_water_overlay.ter"] {
            try Data("x".utf8).write(to: terrain.appendingPathComponent(name))
        }
        for name in ["163856_259008_Arc18.dds", "163872_259024_Arc16.dds",
                     "10240_16144_NZ17.dds"] {
            try Data("x".utf8).write(to: textures.appendingPathComponent(name))
        }
        #expect(TileTextureAudit.terrainTextureNames(texturesDir: textures)
                == ["163856_259008_Arc18.dds", "163872_259024_Arc16.dds"])
        let stale = try #require(TileTextureAudit.scan(texturesDir: textures, currentProvider: "NZ"))
        #expect(stale.foreignFiles.isEmpty)
        #expect(!TileTextureAudit.hasForeignSources(texturesDir: textures, currentProvider: "NZ"))
        let right = try #require(TileTextureAudit.scan(texturesDir: textures, currentProvider: "Arc"))
        #expect(right.foreignFiles.map(\.lastPathComponent) == ["10240_16144_NZ17.dds"])
        #expect(TileTextureAudit.hasForeignSources(texturesDir: textures, currentProvider: "Arc"))
        try FileManager.default.removeItem(at: terrain)
        #expect(TileTextureAudit.scan(texturesDir: textures, currentProvider: "Arc") == nil)
        #expect(!TileTextureAudit.hasForeignSources(texturesDir: textures, currentProvider: "Arc"))
    }

    /// Legacy tile configs quote strings (default_website='Arc'); the
    /// quotes must never reach display or imagery-source comparisons.
    @Test func tileInfoStripsLegacyQuotes() throws {
        let info = try #require(O4TileInfo(json: .object([
            "lat": .int(65), "lon": .int(-21),
            "provider": .string("'Arc'"),
            "high_zl_airports": .string("\"ICAO\""),
            "custom_dem": .string("'dem.tif'"),
        ])))
        #expect(info.provider == "Arc")
        #expect(info.highZLAirports == "ICAO")
        #expect(info.customDEM == "dem.tif")
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
