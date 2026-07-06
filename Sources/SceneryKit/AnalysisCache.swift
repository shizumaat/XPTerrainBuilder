import Foundation

/// Per-pack results of the expensive analysis stages, keyed by the pack's
/// content signature. A pack whose signature is unchanged since the cached
/// run reuses everything below without touching its files — after the first
/// full analysis, subsequent runs only pay for what actually changed.
public struct PackCacheEntry: Codable, Sendable {
    public var signature: String
    /// True when the deep per-pack stages ran (health + resource audit).
    /// Entries with only escape refs (Laminar / uninstalled / out-of-scope
    /// packs swept for cross-pack references) must not masquerade as a
    /// full analysis.
    public var hasFullAnalysis: Bool
    public var healthFindings: [Finding]
    public var auditFindings: [Finding]
    public var placementFindings: [Finding]
    /// Pre-verification unused-file candidates (nil = none).
    public var unusedCandidates: UnusedResourceGroup?
    /// Canonical absolute paths this pack references OUTSIDE itself.
    public var escapeRefs: [String]
    public var vramBytes: Int64
    public var objFilesParsed: Int
    public var texturesInspected: Int
    /// Exact map position for small-footprint packs (object-placement
    /// centroid), once DSF geometry has been parsed.
    public var markerLon: Double?
    public var markerLat: Double?

    public init(signature: String, hasFullAnalysis: Bool = false,
                healthFindings: [Finding] = [], auditFindings: [Finding] = [],
                placementFindings: [Finding] = [],
                unusedCandidates: UnusedResourceGroup? = nil, escapeRefs: [String] = [],
                vramBytes: Int64 = 0, objFilesParsed: Int = 0, texturesInspected: Int = 0,
                markerLon: Double? = nil, markerLat: Double? = nil) {
        self.signature = signature
        self.hasFullAnalysis = hasFullAnalysis
        self.healthFindings = healthFindings
        self.auditFindings = auditFindings
        self.placementFindings = placementFindings
        self.unusedCandidates = unusedCandidates
        self.escapeRefs = escapeRefs
        self.vramBytes = vramBytes
        self.objFilesParsed = objFilesParsed
        self.texturesInspected = texturesInspected
        self.markerLon = markerLon
        self.markerLat = markerLat
    }
}

public struct AnalysisCache: Codable, Sendable {
    /// Bump whenever an analyzer's findings change shape or meaning — a
    /// version mismatch discards the whole cache rather than serving stale
    /// results from an older engine.
    public static let schemaVersion = 2

    public var version: Int = schemaVersion
    public var entries: [String: PackCacheEntry] = [:]

    public init() {}

    public static func load(from url: URL) -> AnalysisCache {
        guard let data = try? Data(contentsOf: url),
              let cache = try? JSONDecoder().decode(AnalysisCache.self, from: data),
              cache.version == schemaVersion
        else { return AnalysisCache() }
        return cache
    }

    public func save(to url: URL) {
        try? FileManager.default.createDirectory(
            at: url.deletingLastPathComponent(), withIntermediateDirectories: true)
        if let data = try? JSONEncoder().encode(self) {
            try? data.write(to: url, options: .atomic)
        }
    }

    /// Valid full-analysis entry for the pack's current content, if any.
    public func fullEntry(for pack: SceneryPack) -> PackCacheEntry? {
        guard let entry = entries[pack.name],
              entry.hasFullAnalysis,
              !pack.signature.isEmpty,
              entry.signature == pack.signature else { return nil }
        return entry
    }

    /// Valid entry of any depth (full or escape-refs-only).
    public func anyEntry(for pack: SceneryPack) -> PackCacheEntry? {
        guard let entry = entries[pack.name],
              !pack.signature.isEmpty,
              entry.signature == pack.signature else { return nil }
        return entry
    }
}
