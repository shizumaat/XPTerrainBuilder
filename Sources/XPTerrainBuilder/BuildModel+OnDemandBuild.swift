import Foundation
import SceneryKit

/// The Build box under imagery on demand (RULINGS 2026-11-10e (1), (2)).
/// With `imagery_on_demand` on, the app manages the disk, so every built
/// tile goes straight into Custom Scenery and a Build press never
/// rebuilds a built tile: the Build box hides "When it's done" with its
/// "Install in X-Plane automatically" and "Skip tiles already built", and
/// both behave as on, whatever they were left at. An explicit rebuild
/// (the tiles table's Rebuild, "Rebuild tile") still rebuilds. Qt mirror:
/// `O4_Qt_Build_OnDemand`.
extension BuildModel {
    /// Where to rebuild a built tile while the Skip switch is hidden (Qt:
    /// `O4_Qt_Build_OnDemand.REBUILD_HINT`).
    static let onDemandRebuildHint = "use Rebuild in the Library to rebuild one"

    /// The world switch is on: the Build box hides its Install and Skip
    /// switches and both behave as on.
    var onDemandBuilds: Bool {
        configValue(for: Self.imageryOnDemandKey) == .bool(true)
    }

    /// Whether a tile that finishes is linked into Custom Scenery.
    var installsBuiltTiles: Bool { onDemandBuilds || linkTiles }

    /// Whether a Build press leaves built tiles out; never during an
    /// explicit rebuild under on demand.
    var skipsBuiltTiles: Bool {
        onDemandBuilds ? !rebuildRequested : skipBuilt
    }

    /// Run `body` as an explicit rebuild (built tiles stay buildable).
    func asRebuild<T>(_ body: () -> T) -> T {
        rebuildRequested = true
        defer { rebuildRequested = false }
        return body()
    }
}
