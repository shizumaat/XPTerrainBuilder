import Foundation

/// One JSON file under the user's Caches/XPTerrainBuilder folder that a
/// launch reads before the engine has booted (#2301): the tile scan
/// (`TileScanCache`) and the imagery source list (`ImagerySourcesCache`).
/// A cache, not user state: a missing or unreadable file costs the next
/// launch its head start and nothing else.
enum LaunchCacheFile {
    static func url(_ name: String) -> URL {
        FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first!
            .appendingPathComponent("XPTerrainBuilder", isDirectory: true)
            .appendingPathComponent(name)
    }

    static func read<T: Decodable>(_ type: T.Type, from url: URL) -> T? {
        guard let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }

    static func write<T: Encodable>(_ value: T, to url: URL) {
        guard let data = try? JSONEncoder().encode(value) else { return }
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        try? data.write(to: url, options: .atomic)
    }
}
