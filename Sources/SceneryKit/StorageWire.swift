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
    /// The one disk budget (RULINGS 2026-11-10d); nil from an older engine.
    public let budget: O4StorageBudget?
    /// X-Plane's installed `zOrtho4XP_*` entries; nil from an older engine.
    public let installed: O4InstalledTiles?

    private enum CodingKeys: String, CodingKey {
        case root, stores, measured, budget, installed
        case cacheBytes = "cache_bytes", keptBytes = "kept_bytes"
        case autoCleanDays = "auto_clean_days"
    }
}

/// `storage_scan`'s `budget` (`o4_engine/storage_budget.py` `status`).
public struct O4StorageBudget: Decodable, Equatable, Sendable {
    public let budgetBytes: Int64
    public let usedBytes: Int64
    public let floorBytes: Int64
    public let recommendedBytes: Int64
    public let underFloor: Bool
    public let overBudget: Bool
    /// RULINGS 2026-11-11a: `budgetBytes` is the one set, else the default
    /// (`defaultBytes`: the larger of `defaultBaseBytes`, 200 GB, and the
    /// recommended minimum); a clearing stops at `lowWater` of it. nil
    /// from an older engine.
    public let budgetSet: Bool?
    public let defaultBytes: Int64?
    public let defaultBaseBytes: Int64?
    public let lowWater: Double?
    /// RULINGS 2026-11-11h (1): unconfirmed, what the default holds (the
    /// install at the first run, raised when more is in use); 0 once set.
    public let heldBytes: Int64?

    private enum CodingKeys: String, CodingKey {
        case budgetSet = "budget_set", defaultBytes = "default_bytes"
        case defaultBaseBytes = "default_base_bytes", lowWater = "low_water"
        case heldBytes = "held_bytes"
        case budgetBytes = "budget_bytes", usedBytes = "used_bytes"
        case floorBytes = "floor_bytes", recommendedBytes = "recommended_bytes"
        case underFloor = "under_floor", overBudget = "over_budget"
    }
}

/// `storage_scan`'s `installed` (`o4_engine/storage_installed.py`).
public struct O4InstalledTiles: Decodable, Equatable, Sendable {
    public struct Linked: Decodable, Equatable, Sendable {
        public let volume: String
        public let count: Int
        public let mounted: Bool
    }
    public let customScenery: String
    public let localCount: Int
    public let localBytes: Int64
    public let linkedCount: Int
    public let linked: [Linked]
    public let measured: Bool

    private enum CodingKeys: String, CodingKey {
        case linked, measured
        case customScenery = "custom_scenery", localCount = "local_count"
        case localBytes = "local_bytes", linkedCount = "linked_count"
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
    /// The `ondemand` store only (#1992): the favorites, inside the budget.
    public let pinnedBytes: Int64?
    public let pinnedFiles: Int?
    /// Of the counted textures, those near airports (made low-res last).
    public let coreFiles: Int?
    /// What the on-demand tiles hold even low-res, the sharp imagery
    /// limit, and whether the first exceeds the second (the warning).
    public let floorBytes: Int64?
    public let capBytes: Int64?
    public let overAtFloor: Bool?

    public var id: String { kind }
    public var isCache: Bool { policy == "cache" }
    /// Sharp imagery near flown areas (#1992): made low-res, never deleted.
    public var isOnDemand: Bool { kind == "ondemand" }

    private enum CodingKeys: String, CodingKey {
        case kind, label, policy, note, path, bytes, files
        case apparentBytes = "apparent_bytes", lastUsed = "last_used"
        case pinnedBytes = "pinned_bytes", pinnedFiles = "pinned_files"
        case coreFiles = "core_files", floorBytes = "floor_bytes"
        case capBytes = "cap_bytes", overAtFloor = "over_at_floor"
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
    /// Bytes freed per store (`ondemand`: made low-res, not deleted).
    public let kinds: [String: Int64]?
    /// `storage_auto_clean` only: the disk budget's figures when it is set,
    /// else the on-demand tiles' floor against the sharp imagery limit.
    public let budget: O4StorageBudget?
    public let ondemandFloor: OndemandFloor?

    public struct OndemandFloor: Decodable, Equatable, Sendable {
        public let overAtFloor: Bool
        public let floorBytes: Int64
        public let capBytes: Int64
        private enum CodingKeys: String, CodingKey {
            case overAtFloor = "over_at_floor", floorBytes = "floor_bytes", capBytes = "cap_bytes"
        }
    }

    private enum CodingKeys: String, CodingKey {
        case files, stopped, ran, kinds, budget
        case ondemandFloor = "ondemand_floor"
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
