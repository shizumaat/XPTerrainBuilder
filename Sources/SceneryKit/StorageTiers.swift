import Foundation

/// Settings ▸ Storage ▸ Storage tiers (RULINGS 2026-11-12g, engine
/// `o4_engine/storage_tiers.py`): every mounted volume other than the
/// app's own, and the size each may hold of sharp imagery. A tier set on a
/// drive that is not connected is listed with `mounted` false: its imagery
/// is downloaded again while it is away.
public struct O4StorageTier: Decodable, Equatable, Sendable, Identifiable {
    public let mount: String
    public let name: String
    public let totalBytes: Int64
    public let freeBytes: Int64
    public let sizeGb: Double
    public let usedBytes: Int64
    public let mounted: Bool

    public var id: String { mount }

    public init(mount: String, name: String, totalBytes: Int64 = 0, freeBytes: Int64 = 0,
                sizeGb: Double = 0, usedBytes: Int64 = 0, mounted: Bool = true) {
        self.mount = mount
        self.name = name
        self.totalBytes = totalBytes
        self.freeBytes = freeBytes
        self.sizeGb = sizeGb
        self.usedBytes = usedBytes
        self.mounted = mounted
    }

    private enum CodingKeys: String, CodingKey {
        case mount, name, totalBytes = "total_bytes", freeBytes = "free_bytes",
             sizeGb = "size_gb", usedBytes = "used_bytes", mounted
    }
}

public struct O4StorageTiers: Decodable, Equatable, Sendable {
    public let volumes: [O4StorageTier]

    public init(volumes: [O4StorageTier]) { self.volumes = volumes }
}

extension OrthoEngineClient {
    /// `storage_tiers` (capability `storage_tiers`): sync.
    public func storageTiers() async throws -> O4StorageTiers {
        try await request("storage_tiers", [:])
    }

    /// `storage_tier_set`: the tier on `mount` set to `sizeGb` (0 removes
    /// it; its files stay on the drive). Replies the new list.
    public func storageTierSet(mount: String, sizeGb: Double) async throws -> O4StorageTiers {
        try await request("storage_tier_set", ["mount": mount, "size_gb": sizeGb])
    }
}
