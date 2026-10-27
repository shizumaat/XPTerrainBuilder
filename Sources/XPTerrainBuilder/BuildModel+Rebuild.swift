import Foundation
import SceneryKit

extension BuildModel {
    /// "Rebuild tile": the Build box's own path — select the tile, build
    /// it with the source and zoom it was built with. During a build the
    /// tile joins it (#1322), unless it is already part of it. Returns the
    /// sentence why it cannot, or nil when the build was asked for. The
    /// patch editor and the tile pane's missing-textures row both end here.
    func rebuildWithItsImagery(_ coord: TileCoord) -> String? {
        if rebuildDecision(for: coord) == .alreadyInRun {
            return "This tile is already in this run."
        }
        click(lat: coord.lat, lon: coord.lon, command: false, shift: false)
        guard canBuild else {
            return xplaneBlockReason
                ?? "This tile can't be rebuilt now. Turn off “Skip tiles already built” and try again."
        }
        let choice = built[coord].flatMap(TileImageryChoice.resolve)
        startBuild(batches: [([coord], choice?.provider ?? buildProvider,
                              choice?.zl ?? buildZL)])
        return nil
    }
}
