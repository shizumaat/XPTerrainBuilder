import SwiftUI
import SceneryKit

extension BuildModel {
    /// #2168: a "Modified airports" row's buttons wait only while the run
    /// builds a tile that writes the pack — the active tile or one the
    /// pack's records name. A run on other tiles, a World pack drape, an
    /// imagery-on-demand or storage job never holds them; the engine
    /// refuses a pack a run is rewriting and says why.
    func packRowBusy(tiles: [String], active: TileCoord) -> Bool {
        Self.packRowBusy(tiles: tiles, active: active, running: isBuilding,
                         activity: activity)
    }

    static func packRowBusy(tiles: [String], active: TileCoord, running: Bool,
                            activity: BuildActivityModel) -> Bool {
        guard running else { return false }
        if tileInRun(active, running: running, activity: activity) { return true }
        return tiles.contains { key in
            TileMath.parse(key).map {
                tileInRun(TileCoord(lat: $0.lat, lon: $0.lon),
                          running: running, activity: activity)
            } ?? false
        }
    }
}

/// The trees / Optimise / Adjust… / Revert buttons of one "Modified
/// airports" row (the Qt row's twin buttons). Observes the activity model
/// so they re-enable when the pack's tiles finish, not when the run does.
struct PackRowButtons: View {
    let buildModel: BuildModel
    @ObservedObject var activity: BuildActivityModel
    let row: BuildPane.ModifiedAirportRow
    let tile: BuildModel.TileCoord
    let revert: () -> Void

    private static let waitHelp =
        "Wait: the current run is building a tile that writes this pack"

    var body: some View {
        let busy = buildModel.packRowBusy(tiles: row.tiles, active: tile)
        // #1360: the pack's 3D trees, undone on their own
        if row.forestCount > 0 {
            Button {
                buildModel.undoPackForests(packPath: row.packPath)
            } label: {
                Image(systemName: "leaf")
            }
            .buttonStyle(.borderless)
            .controlSize(.small)
            .disabled(busy)
            .help(busy ? Self.waitHelp : O4PackOldForestsCopy.undoHelp)
        }
        // #1707: Optimise pack, or its Undo
        Button {
            buildModel.packOptimiseFromRow(
                packPath: row.packPath, undo: row.optimisedCount > 0, tile: tile)
        } label: {
            Image(systemName: row.optimisedCount > 0
                  ? "gauge.with.dots.needle.33percent"
                  : "gauge.with.dots.needle.67percent")
        }
        .buttonStyle(.borderless)
        .controlSize(.small)
        .disabled(busy)
        .help(busy ? Self.waitHelp
              : (row.optimisedCount > 0 ? O4PackOptimiseCopy.undoHelp
                 : O4PackOptimiseCopy.optimiseHelp))
        // owner 2026-11-15T13:12Z: Adjust… — change what is hidden or
        // optimised, beside Revert
        if buildModel.engineCapabilities.supports(O4EngineCapabilities.packAdjustEdit) {
            Button {
                buildModel.adjustPackFromRow(packPath: row.packPath, tile: tile)
            } label: {
                Image(systemName: "slider.horizontal.3")
            }
            .buttonStyle(.borderless)
            .controlSize(.small)
            .disabled(busy)
            .help(busy ? Self.waitHelp : O4PackAdjustCopy.adjustHelp)
        }
        Button(action: revert) {
            Image(systemName: "arrow.uturn.backward.circle")
        }
        .buttonStyle(.borderless)
        .controlSize(.small)
        .disabled(busy)
        .help(busy ? Self.waitHelp
              : "Revert to default: restores \(row.packName)'s original object files from the backups the reseater kept")
    }
}
