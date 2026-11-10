import Foundation

// MARK: - Imagery on demand: pins and "Make all low-res again" (#1992 P4)

/// The engine's `imagery_pin` reply (`o4_engine.imagery_ondemand`): the
/// tile, its new pin, how many full textures the cache landed at once
/// and how many the follow job still fetches.
public struct O4ImageryPinResult: Decodable, Equatable, Sendable {
    public let tile: String
    public let pinned: Bool
    public let served: Int
    public let toFetch: Int
    public let pinnedBytes: Int64

    private enum CodingKeys: String, CodingKey {
        case tile, pinned, served
        case toFetch = "to_fetch", pinnedBytes = "pinned_bytes"
    }
}

/// The engine's `imagery_ondemand_downgrade_all` reply: what was (or, for
/// a dry run, would be) made low-res again, and the space it frees.
public struct O4OnDemandDowngrade: Decodable, Equatable, Sendable {
    public let downgraded: Int
    public let freedBytes: Int64
    public let dryRun: Bool
    public let stopped: Bool

    private enum CodingKeys: String, CodingKey {
        case downgraded, stopped
        case freedBytes = "freed_bytes", dryRun = "dry_run"
    }
}

extension OrthoEngineClient {
    /// "Always keep full resolution" (`pinned`) or "Let it go low-res
    /// again" for one built tile; refused while a build runs.
    public func imageryPin(lat: Int, lon: Int, pinned: Bool,
                           workingDir: String) async throws -> O4ImageryPinResult {
        try await request("imagery_pin", ["lat": lat, "lon": lon, "pinned": pinned,
                                          "working_dir": workingDir])
    }

    /// "Make all low-res again": every unpinned sharp texture back to its
    /// placeholder. `dryRun` changes nothing and answers the space it
    /// would free, which the confirmation names first.
    public func imageryMakeAllLowRes(dryRun: Bool) async throws -> O4OnDemandDowngrade {
        try await request("imagery_ondemand_downgrade_all",
                          dryRun ? ["dry_run": true] : ["confirm": true])
    }
}
