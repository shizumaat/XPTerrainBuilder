import Foundation

/// When the Build box adopts the active tile's imagery (#1334): at once
/// when the tile's info is known, else the moment its info arrives (the
/// scan reports it after the selection: at launch, after a rejected scan
/// cache, while a build slows the scan) — unless the user picked a source
/// in between. The Qt window's `_sync_build_controls_to_selection` keys
/// its once-per-selection sync on the same rule.
public struct TileImageryAdoption<Tile: Hashable & Sendable>: Sendable {
    /// The active tile whose info was not known when it was selected.
    public private(set) var pending: Tile?

    public init() {}

    /// The active tile changed; `info` is what `built` holds for it.
    /// Returns the imagery to adopt now, or nil.
    public mutating func select(_ tile: Tile?, info: O4TileInfo?) -> TileImageryChoice? {
        pending = tile
        return arrived(active: tile, info: info)
    }

    /// `built` changed; adopts only for a still-pending active tile whose
    /// info is now known (once: the pending mark clears).
    public mutating func arrived(active: Tile?, info: O4TileInfo?) -> TileImageryChoice? {
        guard let tile = pending, tile == active, let info else { return nil }
        pending = nil
        return TileImageryChoice.resolve(info)
    }

    /// The user chose a source: nothing arriving later overrides it.
    public mutating func userPicked() { pending = nil }
}
