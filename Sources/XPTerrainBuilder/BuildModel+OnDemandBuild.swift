import Foundation
import SceneryKit

/// The Build box under imagery on demand (RULINGS 2026-11-10e (1), (2);
/// the Skip half replaced by #2043, owner 2026-11-13T13:09/13:11Z). With
/// `imagery_on_demand` on, the app manages the disk, so every built tile
/// goes straight into Custom Scenery: the Build box hides "When it's
/// done" with its "Install in X-Plane automatically" and "Skip tiles
/// already built". Install behaves as on; Skip behaves as OFF -- a Build
/// or Queue press builds every tile the user selected, a built one
/// rebuilt (an airport list typed in the search field queues all its
/// tiles, a tile picked during a run joins it). Qt mirror:
/// `O4_Qt_Build_OnDemand`.
extension BuildModel {
    /// The world switch is on: the Build box hides its Install and Skip
    /// switches.
    var onDemandBuilds: Bool {
        configValue(for: Self.imageryOnDemandKey) == .bool(true)
    }

    /// Whether a tile that finishes is linked into Custom Scenery.
    var installsBuiltTiles: Bool { onDemandBuilds || linkTiles }

    /// Whether a Build press leaves built tiles out: only the visible
    /// Skip switch, so never under on demand (#2043).
    var skipsBuiltTiles: Bool {
        Self.skipsBuiltTiles(onDemand: onDemandBuilds, skipSwitch: skipBuilt)
    }

    nonisolated static func skipsBuiltTiles(onDemand: Bool, skipSwitch: Bool) -> Bool {
        !onDemand && skipSwitch
    }
}
