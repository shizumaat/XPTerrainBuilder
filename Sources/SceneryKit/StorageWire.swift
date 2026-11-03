import Foundation

// MARK: - Settings ▸ Storage (#1724)

/// The engine's `storage_scan` result (`Ortho4XP/src/o4_engine/storage.py`):
/// every store of the data folder with the bytes deleting it frees
/// (private bytes, so an APFS clone or a hard-linked texture counts ~0),
/// plus the automatic-cleanup settings.
public struct O4StorageScan: Decodable, Equatable, Sendable {
    public let root: String
    public let stores: [O4StorageStore]
    public let cacheBytes: Int64
    public let keptBytes: Int64
    /// "private" (APFS could say) or "allocated" (it could not).
    public let measured: String
    public let autoCleanDays: Double

    private enum CodingKeys: String, CodingKey {
        case root, stores, measured
        case cacheBytes = "cache_bytes", keptBytes = "kept_bytes"
        case autoCleanDays = "auto_clean_days"
    }
}

/// One store: a cache the user may clear, or a kept folder (built tiles,
/// patches, overlays) that is sized and never cleared here.
public struct O4StorageStore: Decodable, Equatable, Identifiable, Sendable {
    public let kind: String
    public let label: String
    /// "cache" or "kept".
    public let policy: String
    public let note: String
    public let path: String
    public let bytes: Int64
    public let apparentBytes: Int64
    public let files: Int
    /// Unix time a file in it was last used; nil when it is empty.
    public let lastUsed: Double?

    public var id: String { kind }
    public var isCache: Bool { policy == "cache" }

    private enum CodingKeys: String, CodingKey {
        case kind, label, policy, note, path, bytes, files
        case apparentBytes = "apparent_bytes", lastUsed = "last_used"
    }
}

/// `storage_clear` / `storage_auto_clean` result: what was (or, for a dry
/// run, would be) freed.
public struct O4StorageCleared: Decodable, Equatable, Sendable {
    public let freedBytes: Int64
    public let files: Int
    public let dryRun: Bool
    public let stopped: Bool
    /// `storage_auto_clean` only: false when both settings are off.
    public let ran: Bool?

    private enum CodingKeys: String, CodingKey {
        case files, stopped, ran
        case freedBytes = "freed_bytes", dryRun = "dry_run"
    }
}

extension OrthoEngineClient {
    public func storageScan() async throws -> O4StorageScan {
        try await libraryRequest("storage_scan", [:])
    }

    /// Clears caches: `kinds` empty is every cache (never built tiles or
    /// patches; the engine refuses those). `dryRun` deletes nothing and
    /// answers what would go, which the confirmation shows first.
    public func storageClear(kinds: [String], olderThanDays: Double?,
                             dryRun: Bool) async throws -> O4StorageCleared {
        var arguments: [String: Any] = ["kinds": kinds, "dry_run": dryRun, "confirm": !dryRun]
        if let olderThanDays { arguments["older_than_days"] = olderThanDays }
        return try await libraryRequest("storage_clear", arguments)
    }

    /// The automatic cleanup the app runs at launch and after a build; the
    /// engine refuses it while a build runs.
    public func storageAutoClean() async throws -> O4StorageCleared {
        try await libraryRequest("storage_auto_clean", [:])
    }
}
