import Foundation

/// Persisted scenery index: the expensive per-pack probe results
/// (apt.dat airports, DSF overlay classification, terrain typing) keyed by
/// pack path and guarded by the scanner's content signature. Subsequent
/// launches re-walk only file metadata — names, sizes, mtimes — and reuse
/// the cached probe whenever a pack's signature is unchanged, skipping the
/// file-content reads that dominate a cold scan.
public enum SceneryIndexCache {
    /// Everything a probe learns by READING FILE CONTENT. Metadata-derived
    /// fields (tiles, sizes, dates) are cheap to rebuild and stay fresh.
    public struct CachedProbe: Codable, Sendable {
        public let signature: String
        public let airports: [String: AirportInfo]
        public let isOverlay: Bool?
        public let hasTerrain: Bool
        public let isPhotoTextured: Bool

        public init(signature: String, airports: [String: AirportInfo],
                    isOverlay: Bool?, hasTerrain: Bool, isPhotoTextured: Bool) {
            self.signature = signature
            self.airports = airports
            self.isOverlay = isOverlay
            self.hasTerrain = hasTerrain
            self.isPhotoTextured = isPhotoTextured
        }
    }

    private struct FileFormat: Codable {
        let version: Int
        let root: String
        let probes: [String: CachedProbe]
    }

    static let version = 1

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
