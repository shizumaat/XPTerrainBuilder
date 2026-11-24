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

/// How one airport uses its custom patch (#2179, RULINGS 2026-11-23d/f):
/// "As made" (the default) or "Our auto patch", with the warning under an
/// airport used as made. Shown in the tile pane's Custom patch row and the
/// Build box's Airports card; the Qt window's twin is
/// `O4_Qt_Custom_Patch_Use.CustomPatchUseList`. Disabled only while its
/// own tile is queued or building (#1922). Observes the activity model so
/// it re-enables when the tile finishes.
struct CustomPatchUsePicker: View {
    let buildModel: BuildModel
    @ObservedObject var activity: BuildActivityModel
    let row: O4CustomPatchUse

    private var tile: BuildModel.TileCoord {
        BuildModel.TileCoord(lat: row.tile.lat, lon: row.tile.lon)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Picker(row.icao, selection: Binding(
                get: { row.use },
                set: { use in
                    if use != row.use {
                        buildModel.setCustomPatchUse(tile: tile, icao: row.icao, to: use)
                    }
                })) {
                Text(O4CustomPatchText.asMadeTitle).tag(O4CustomPatchUse.asMade)
                Text(O4CustomPatchText.autoPatchTitle).tag(O4CustomPatchUse.autoPatch)
            }
            .pickerStyle(.menu)
            .controlSize(.small)
            .fixedSize()
            .scaledFont(.caption)
            .disabled(buildModel.tileInRun(tile))
            .help(O4CustomPatchText.help(of: row.use) + " (" + row.files.joined(separator: ", ") + ")")
            if !row.warning.isEmpty {
                Label(row.warning, systemImage: "exclamationmark.triangle")
                    .scaledFont(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }
}
