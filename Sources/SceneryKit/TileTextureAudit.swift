import Foundation

/// Audit of a built tile's textures folder for imagery-source conflicts.
///
/// Ortho4XP names every texture `{y}_{x}_{Provider}{ZL}.dds`, and a tile's
/// DSF references textures from ONE source — the config's default_website.
/// Files from any other provider are dead weight left over from an earlier
/// build with a different source (imagery zones legitimately mix ZOOM
/// LEVELS, so only the provider token decides foreignness; masks and other
/// non-.dds files are ignored).
public struct TileTextureAudit: Sendable, Equatable {
    public struct Source: Sendable, Equatable, Identifiable {
        /// Provider token exactly as found on disk, e.g. "Arc", "BI".
        public let provider: String
        public let fileCount: Int
        public let bytes: Int64
        public var id: String { provider }
    }

    /// The tile config's provider (default_website), as passed to scan.
    public let currentProvider: String
    /// Every provider found, most files first.
    public let sources: [Source]
    /// Textures whose provider differs from the current one.
    public let foreignFiles: [URL]

    public var hasConflict: Bool { !foreignFiles.isEmpty }
    public var foreignSources: [Source] {
        sources.filter { $0.provider.lowercased() != currentProvider.lowercased() }
    }
    public var foreignBytes: Int64 {
        foreignSources.reduce(0) { $0 + $1.bytes }
    }

    /// `{y}_{x}_{provider}{2-digit zl}` with an optional `_suffix`; the
    /// two-digit ZL anchor lets provider codes that end in digits
    /// ("USA_2" → `…_USA_216.dds`) parse correctly.
    private static let ddsPattern =
        #/^\d+_\d+_(.+?)(\d{2})(?:_[A-Za-z_]+)?$/#

    /// Names-only fast path for sweeping many tiles (map badges): true as
    /// soon as one .dds from a provider other than `currentProvider` is
    /// seen. One directory listing, no per-file stat calls.
    public static func hasForeignSources(texturesDir: URL, currentProvider: String) -> Bool {
        guard !currentProvider.isEmpty,
              let names = try? FileManager.default.contentsOfDirectory(atPath: texturesDir.path)
        else { return false }
        let currentLower = currentProvider.lowercased()
        for name in names where name.lowercased().hasSuffix(".dds") {
            let stem = String(name.dropLast(4))
            guard let match = stem.wholeMatch(of: ddsPattern) else { continue }
            if String(match.1).lowercased() != currentLower { return true }
        }
        return false
    }

    /// Scans `texturesDir` (a built tile's textures folder). Returns nil
    /// when the folder can't be listed or the current provider is unknown
    /// — no conflict call can be made without knowing the current source.
    public static func scan(texturesDir: URL, currentProvider: String) -> TileTextureAudit? {
        guard !currentProvider.isEmpty,
              let entries = try? FileManager.default.contentsOfDirectory(
                  at: texturesDir,
                  includingPropertiesForKeys: [.fileSizeKey],
                  options: [.skipsHiddenFiles])
        else { return nil }
        var counts: [String: (count: Int, bytes: Int64)] = [:]
        var foreign: [URL] = []
        let currentLower = currentProvider.lowercased()
        for file in entries where file.pathExtension.lowercased() == "dds" {
            let stem = file.deletingPathExtension().lastPathComponent
            guard let match = stem.wholeMatch(of: ddsPattern) else { continue }
            let provider = String(match.1)
            let size = Int64((try? file.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0)
            var entry = counts[provider] ?? (0, 0)
            entry.count += 1
            entry.bytes += size
            counts[provider] = entry
            if provider.lowercased() != currentLower {
                foreign.append(file)
            }
        }
        let sources = counts
            .map { Source(provider: $0.key, fileCount: $0.value.count, bytes: $0.value.bytes) }
            .sorted { ($0.fileCount, $1.provider) > ($1.fileCount, $0.provider) }
        return TileTextureAudit(currentProvider: currentProvider,
                                sources: sources,
                                foreignFiles: foreign.sorted { $0.path < $1.path })
    }
}
