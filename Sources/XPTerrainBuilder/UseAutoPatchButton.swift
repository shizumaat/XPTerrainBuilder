import SwiftUI
import SceneryKit

extension BuildModel {
    /// #1922: `coord` is queued or building in the current run. A
    /// per-tile action waits for its own tile only, never for the run.
    func tileInRun(_ coord: TileCoord) -> Bool {
        Self.tileInRun(coord, running: isBuilding, activity: activity)
    }

    static func tileInRun(_ coord: TileCoord, running: Bool,
                          activity: BuildActivityModel) -> Bool {
        running && activity.isBuilding(coord)
    }
}

/// The tile pane's "Use auto patch" button (#1229): disabled only while
/// its own tile is queued or building (#1922; the Qt pane: the same).
/// Observes the activity model so it re-enables when the tile finishes.
struct UseAutoPatchButton: View {
    let buildModel: BuildModel
    @ObservedObject var activity: BuildActivityModel
    let tile: BuildModel.TileCoord

    var body: some View {
        Button(O4CustomPatchText.useAutoPatchTitle) {
            buildModel.useAutoPatch(for: tile)
        }
        .controlSize(.small)
        .disabled(buildModel.tileInRun(tile))
        .help(O4CustomPatchText.useAutoPatchHelp)
    }
}
