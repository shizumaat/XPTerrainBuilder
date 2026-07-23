import Foundation

/// Persisted scenery index: the expensive per-pack probe results
/// (apt.dat airports, DSF overlay classification, terrain typing) keyed by
/// pack path and guarded by the scanner's content signature. Subsequent
/// launches re-walk metadata for only the files X-Plane's loadable scenery
/// is rooted in — every apt.dat and DSF, plus the pack's top-level listing —
/// and reuse the cached probe whenever the signature is unchanged, skipping
/// both the file-content reads and the deep subtree walks (textures,
/// terrain, objects) that dominate a cold scan.
public enum SceneryIndexCache {
    /// Everything a probe learns by READING FILE CONTENT, plus the size /
    /// freshness totals whose deep walk the warm rescan no longer performs,
    /// plus the cheap flags (tiles, isLibrary, hasPlugins) the scanner
    /// refreshes every scan anyway — carried so packsFromCache can rebuild
    /// a complete pack list for optimistic launch without touching pack
    /// contents at all.
    public struct CachedProbe: Codable, Sendable {
        public let signature: String
        public let airports: [String: AirportInfo]
        public let tiles: Set<String>
        public let isLibrary: Bool
        public let isOverlay: Bool?
        public let hasTerrain: Bool
        public let isPhotoTextured: Bool
        public let hasPlugins: Bool
        public let sizeBytes: Int64
        public let modifiedDate: Date?

        public init(signature: String, airports: [String: AirportInfo],
                    tiles: Set<String>, isLibrary: Bool,
                    isOverlay: Bool?, hasTerrain: Bool, isPhotoTextured: Bool,
                    hasPlugins: Bool, sizeBytes: Int64, modifiedDate: Date?) {
            self.signature = signature
            self.airports = airports
            self.tiles = tiles
            self.isLibrary = isLibrary
            self.isOverlay = isOverlay
            self.hasTerrain = hasTerrain
            self.isPhotoTextured = isPhotoTextured
            self.hasPlugins = hasPlugins
            self.sizeBytes = sizeBytes
            self.modifiedDate = modifiedDate
        }
    }

    private struct FileFormat: Codable {
        let version: Int
        let root: String
        let probes: [String: CachedProbe]
    }

    static let version = 3

    /// One cache file per X-Plane root, under the user's Caches directory.
    public static func cacheURL(for root: URL) -> URL {
        var hash = FNV1a()
        hash.combine(root.standardizedFileURL.path)
        let dir = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first!
            .appendingPathComponent("XPTerrainBuilder", isDirectory: true)
        return dir.appendingPathComponent("scenery-index-\(String(hash.value, radix: 16)).json")
    }

    public static func load(for root: URL) -> [String: CachedProbe] {
        guard let data = try? Data(contentsOf: cacheURL(for: root)),
              let file = try? JSONDecoder().decode(FileFormat.self, from: data),
              file.version == version,
              file.root == root.standardizedFileURL.path
        else { return [:] }
        return file.probes
    }

    public static func save(_ probes: [String: CachedProbe], for root: URL) {
        let url = cacheURL(for: root)
        let payload = FileFormat(version: version,
                                 root: root.standardizedFileURL.path,
                                 probes: probes)
        guard let data = try? JSONEncoder().encode(payload) else { return }
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url, options: .atomic)
    }
}
