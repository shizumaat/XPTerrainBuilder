import Foundation
import SceneryKit

/// The engine's imagery source list (`imagery_sources`, #1345) kept from
/// the last session, keyed by the engine version that answered (#2301):
/// the map's live imagery draws from its disk tiles the moment the window
/// opens instead of after the engine boots; the engine's own answer
/// replaces it seconds later.
enum ImagerySourcesCache {
    private struct Snapshot: Codable {
        let version: Int
        let engineVersion: String
        let sources: [O4ImagerySource]
    }

    static let version = 1
    static let defaultURL = LaunchCacheFile.url("imagery-sources.json")

    /// The list an engine of `engineVersion` gave, or nil.
    static func load(engineVersion: String, url: URL = defaultURL) -> [O4ImagerySource]? {
        guard let snap = LaunchCacheFile.read(Snapshot.self, from: url),
              snap.version == version, snap.engineVersion == engineVersion,
              !snap.sources.isEmpty
        else { return nil }
        return snap.sources
    }

    static func save(_ sources: [O4ImagerySource], engineVersion: String,
                     url: URL = defaultURL) {
        guard !sources.isEmpty else { return }
        LaunchCacheFile.write(
            Snapshot(version: version, engineVersion: engineVersion, sources: sources),
            to: url)
    }
}
